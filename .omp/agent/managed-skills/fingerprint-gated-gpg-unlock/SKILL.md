---
name: fingerprint-gated-gpg-unlock
description: "Use when making GPG signing require a fingerprint (or other biometric) before unlocking the key on Linux — covers the polkit/pkexec + hyprpolkitagent + root-only-passphrase-file architecture (the current, correct design), the older fprintd-verify + gnome-keyring approach and why it was replaced, and rotating/migrating the passphrase without leaking it."
---

## Goal
Require a fingerprint (via PAM fprintd) before GPG can unlock a signing key, so commits don't sign without physical presence. On Hyprland/Omarchy use polkit + hyprpolkitagent for the native GUI auth dialog (gpg-agent is a systemd service with NO controlling tty, so terminal prompts and /dev/tty writes silently fail).

## Why this architecture (what changed)
The first approach — a custom `pinentry` script calling `fprintd-verify`, then reading the passphrase from gnome-keyring via `secret-tool` — was bypassable: ANY process running as the user can `secret-tool lookup ...` and read the passphrase directly, skipping the fingerprint entirely. The fix is to store the passphrase in a **root-only file** and gate its release behind `pkexec` (polkit) + PAM fingerprint. Then a non-root process cannot read the passphrase without authenticating.

Remaining honest gaps: the passphrase still transits root→user process memory at signing time (a same-user ptrace/`/proc` attacker could sniff it); polkit/sudo cache auth for a window; and the key is still software on disk (only hardware tokens make it unexportable). State these to the user, don't oversell.

## Components (Omarchy / Hyprland)
- `omarchy setup security fingerprint` — wires `pam_fprintd` into sudo + polkit + lock screen (idempotent).
- `hyprpolkitagent` — the native polkit GUI auth agent for Hyprland. Installed from AUR (`omarchy pkg aur add hyprpolkitagent`), runs as a systemd user service (`systemctl --user enable --now hyprpolkitagent.service`). Do NOT use `exec-once`; it ships a `.service` and is D-Bus-activatable. Note: it logs "An authentication agent already exists" as a benign startup race if started twice — confirm it's the sole agent via `busctl --user list | grep polkit`.
- `polkitd` is the daemon; the *agent* (GUI dialog) must be running separately or `pkexec` prompts fail silently.

## Files
1. `/etc/gpg-fingerprint/passphrase` — the passphrase, mode `600` root:root.
2. `/usr/local/bin/gpg-fingerprint-read` — root-owned `755` reader that just `cat`s that file. Must be non-user-writable (else a user could swap it to exfiltrate).
3. `/usr/share/polkit-1/actions/com.gir0fa.gpg-fingerprint-read.policy` — polkit action with `<allow_active>auth_admin</allow_active>` and the `org.freedesktop.policykit.exec.path` annotation pointing at the reader. `auth_admin` (NOT `auth_admin_keep`) so it prompts every time.
4. `~/.local/bin/pinentry-fprintd` — the custom pinentry (root-owned `755`, since gpg-agent spawns it but it must be non-editable) that calls `pkexec /usr/local/bin/gpg-fingerprint-read` on `GETPIN`.
5. `~/.gnupg/gpg-agent.conf` — `pinentry-program /home/wils/.local/bin/pinentry-fprintd`, plus `default-cache-ttl 0` / `max-cache-ttl 0` to force a prompt every signing op.

## pinentry wrapper (polkit version)
```sh
#!/bin/bash
set -u
printf 'OK Pleased to meet you\n'
while IFS= read -r line; do
  cmd="${line%% *}"
  case "$cmd" in
    GETPIN)
      pin="$(pkexec /usr/local/bin/gpg-fingerprint-read 2>/dev/null)" || {
        printf 'ERR 83886179 cancelled\n'; continue; }
      if [ -n "$pin" ]; then
        esc=$(printf '%s' "$pin" | sed 's/%/%25/g; s/\r/%0D/g')
        printf 'D %s\n' "$esc"; printf 'OK\n'
      else
        printf 'ERR 83886179 No passphrase available\n'
      fi
      unset pin ;;
    BYE) printf 'OK closing connection\n'; exit 0 ;;
    *) printf 'OK\n' ;;
  esac
done
```

## pinentry protocol gotchas (learned the hard way)
- gpg-agent keeps the SAME pinentry process across wrong-passphrase retries, re-issuing `GETPIN`. A per-process flag can latch "fingerprint exhausted" so retries don't restart the biometric loop (only relevant if you hand-roll the loop; the pkexec version delegates all retry logic to polkit, so no latch needed).
- gpg-agent sends `SETERROR` before a retry `GETPIN` after a wrong passphrase.
- Escape `%` → `%25` and CR → `%0D` in the returned pin (`D <escaped>`).
- `83886179` is the correct "cancelled" error code.
- A shell-script pinentry is fine because bash reads it itself; but mode `711` would BREAK it (bash needs read access). Root-owned `755` = readable+executable, only root can write.

## Passphrase rotation + migration WITHOUT leaking
The passphrase must move keyring → root file (or be set fresh) without ever touching stdout or the agent transcript. Critical sequence:
- Switch `gpg-agent.conf` pinentry to `pinentry-gnome3` (GUI) BEFORE `gpg --passwd`, else the fingerprint wrapper intercepts the passphrase-change prompt.
- `gpg --passwd <keyid>` to rotate. Verify it stuck with `gpg --batch --pinentry-mode cancel --export-secret-keys <keyid> >/dev/null; echo $?` — exit 2 = protected.
- Migrate keyring→file without echo: `secret-tool lookup ... | sudo tee /etc/gpg-fingerprint/passphrase >/dev/null`.
- The `<` redirect in `sudo wc -c < file` is opened by the SHELL as the user, not root — use `sudo sh -c 'wc -c < file'` instead.
- NEVER run `gpg-fingerprint-read` directly to "verify" — it echoes the passphrase into the transcript. Verify with length only (`pkexec ... | wc -c`).
- `secret-tool store` does NOT overwrite — it creates a new entry and `lookup` returns the OLDEST. Use `secret-tool clear` first, or you'll match-test against a stale value. Also: users pasting the command text itself into the `Password:` prompt is a real failure mode — tell them to type the passphrase, not paste the command.
- The passphrase DOES leak into transcript if any `D <pin>` or reader output is captured. If it ever does, flag it and require rotation.

## Verification
`pkexec /usr/local/bin/gpg-fingerprint-read | wc -c` should take ~2s (real fingerprint prompt, not instant auto-allow) and return the passphrase length. Then an end-to-end `git commit` in a scoped repo should pop the Omarchy fingerprint dialog, sign, and produce a `Good signature`.
