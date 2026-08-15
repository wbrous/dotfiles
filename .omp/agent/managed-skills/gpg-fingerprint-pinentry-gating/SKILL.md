---
name: gpg-fingerprint-pinentry-gating
description: "Use when the user wants to require a fingerprint (fprintd) before GPG can sign/decrypt with their key, i.e. gate gpg-agent's pinentry on a biometric scan instead of/in addition to a typed passphrase on Linux. Covers the custom pinentry wrapper (fprintd-verify + secret-tool + GUI fallback), wiring it into a systemd-supervised gpg-agent, the no-passphrase key gotcha, the no-controlling-tty gotcha (use notify-send/zenity, not /dev/tty), and the fundamental security limitations (software gating is not a real boundary vs. hardware tokens)."
---

## Goal
Require a fingerprint scan (fprintd) before GPG can use a key to sign/decrypt, by intercepting gpg-agent's pinentry. Goal is usually "tap my finger instead of typing my passphrase" with a typed-passphrase fallback after N failed scans.

## Two real gotchas that dominate this work

### 1. No passphrase = no pinentry = no gate
gpg-agent only invokes pinentry when the key is actually passphrase-protected. A key with no passphrase signs instantly and the wrapper never runs. Check with:
```sh
gpg --batch --pinentry-mode cancel --export-secret-keys KEYID >/dev/null 2>&1; echo $?
# exit 2 => protected (good); exit 0 => NO passphrase (gate will silently never fire)
```
If unprotected, add one via `gpg --passwd KEYID` — this changes only the secret-key protection, NOT the fingerprint, signingkey config, uploaded pubkeys, or any past signature. Do NOT create a new key just to add a passphrase.

### 2. systemd-supervised gpg-agent has NO controlling tty
On systems where gpg-agent runs as `gpg-agent.service --supervised` (check `systemctl --user list-units | grep gpg`), every manual `gpg-agent --daemon ...` is rejected ("already running") because systemd owns the socket and respawns instantly, re-reading `~/.gnupg/gpg-agent.conf` each time. That's actually the desired source of truth.

More importantly, the pinentry child inherits NO controlling tty, and `GPG_TTY` may be the literal broken string "not a tty" (check `echo "$GPG_TTY"`). So any wrapper that writes to `/dev/tty` or does `read < /dev/tty` will **silently do nothing** — blank screen, then gpg reports "signing failed: Operation cancelled" / "PINENTRY_LAUNCHED". Do NOT build tty-based prompting.

Fix: prompt via desktop notification (`notify-send`) for the fingerprint prompt, and GUI dialog (`zenity --entry --hide-text`) for the typed fallback. Both work with no tty. Also have the user set `export GPG_TTY=$(tty)` in their shell rc anyway, to avoid confusing gpg-agent's own handoff.

## Wrapper script (~/.local/bin/pinentry-fprintd)
Minimal Assuan protocol handler (pinentry's line-based protocol; no off-the-shelf tool does fingerprint-first-then-passphrase). Key points:
- Respond `OK Pleased to meet you` on start, `OK` to every unknown command, `OK closing connection` + exit on `BYE`.
- On `GETPIN`: loop `fprintd-verify` up to N times. Before each attempt, `notify-send` a "place your finger" prompt (so the user isn't staring at a blank screen). `fprintd-verify` blocks until a scan or failure.
- On fingerprint success: `secret-tool lookup service <svc> account "$USER"` to fetch the real passphrase.
- If no passphrase after N failures: `zenity --entry --hide-text` GUI dialog for typed fallback.
- Reply with `D <escaped-passphrase>` then `OK`; escape `%` -> `%25` and `\r` -> `%0D`. On empty pin, `ERR 83886179 No passphrase available`.
- Do NOT hardcode the passphrase in the script; seed it once via `secret-tool store --label=... service <svc> account "$USER"` in the user's own terminal (never ask them to paste it into chat).

## Wiring
`~/.gnupg/gpg-agent.conf`:
```
pinentry-program /home/wils/.local/bin/pinentry-fprintd
default-cache-ttl 0
max-cache-ttl 0
```
(The ttl=0 forces a re-prompt every operation — matches "tap every commit".) Then `gpgconf --kill gpg-agent` (systemd respawns it fresh, picking up the new pinentry-program).

Verify the stored secret actually matches the key without reading it aloud:
```sh
secret-tool lookup service <svc> account "$USER" | gpg --batch --pinentry-mode loopback --passphrase-fd 0 --export-secret-keys KEYID >/dev/null 2>&1; echo $?
# exit 0 => stored value is the correct passphrase
```

## Root-locking the files (tamper-hardening only)
`sudo chown root:root` + `chmod 755` on the wrapper and hook scripts, `644` on configs. Use 755 (not 711) — shell scripts MUST be readable by the interpreter, so 711 breaks execution for non-root. This stops a same-user process from *editing* the gate to disable it. It does NOT stop reading the passphrase via `secret-tool lookup` directly (see limitations).

## Honest security framing — surface this, don't silently build a fake control
- `Signed-off-by:` / `Co-authored-by:` trailers are plaintext and cosmetic; forgeable by hand, and the adding hook is skipped by `git commit --no-verify` or `git -c core.hooksPath=/dev/null commit`.
- The fingerprint gate is a user-space script. Any same-user process can bypass it entirely: `secret-tool lookup service <svc> account "$USER"` then `gpg --pinentry-mode loopback --passphrase-fd 0 --sign`. The wrapper only gates the *interactive* pinentry flow, not the key material.
- gnome-keyring (via secret-tool) is encrypted at rest but auto-unlocked at login, so any process running as the user in an unlocked session can read it. Protects against offline disk theft, not against same-user processes.
- Anyone with the user's finger or sudo already has the machine.
- Real biometric-gated signing requires the private key in HARDWARE (YubiKey Bio), where the key can't be exported and the check runs in token firmware. Software wrapper + keyring-stored passphrase is a UX/convenience gate, not a security boundary.

## Operational cautions
- The passphrase can leak into tool output during gpg-connect-agent probes (agent replies `D <passphrase>`). Avoid probes that would echo it, and if it leaks, tell the user to treat it as compromised and rotate (`gpg --passwd` + re-`secret-tool store`).
- A `gpg --passwd` run while the fingerprint wrapper is active will hang (wrapper blocks on fprintd-verify during the passphrase-change itself). Temporarily point `gpg-agent.conf` at `pinentry-gnome3` (a GUI pinentry that works without tty), reload, do `gpg --passwd`, then restore the wrapper.
