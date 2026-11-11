# Fingerprint-gated GPG signing

Requiring a fingerprint tap before GPG unlocks the signing key on Linux.

## Current architecture: polkit + root-only passphrase (use this)

gpg-agent runs as a systemd service with no controlling tty, so terminal prompts and `/dev/tty` writes silently fail — the GUI prompt must come from a polkit agent (hyprpolkitagent on Hyprland/Omarchy). The older `fprintd-verify` + `secret-tool`/gnome-keyring design was bypassable: any same-user process can `secret-tool lookup ...` and skip the fingerprint entirely. The fix stores the passphrase in a root-only file gated by `pkexec` + PAM fingerprint.

Components: `omarchy setup security fingerprint` (pam_fprintd into sudo+polkit+lock, idempotent); `hyprpolkitagent` from AUR as a systemd user service (`systemctl --user enable --now hyprpolkitagent.service`, never `exec-once`; benign "authentication agent already exists" double-start race — confirm sole agent via `busctl --user list | grep polkit`); `/etc/gpg-fingerprint/passphrase` (root:root 600); `/usr/local/bin/gpg-fingerprint-read` (root:root 755, just `cat`s the file); polkit action `com.gir0fa.gpg-fingerprint-read` (`auth_admin`, NOT `auth_admin_keep`, so it prompts every time); `~/.local/bin/pinentry-fprintd` (root:root 755 — shell scripts need read access, so 755 not 711); `~/.gnupg/gpg-agent.conf` (`pinentry-program .../pinentry-fprintd`, `default-cache-ttl 0`, `max-cache-ttl 0`).

pinentry wrapper: greet `OK Pleased to meet you`, on `GETPIN` run `pkexec /usr/local/bin/gpg-fingerprint-read`, percent-escape (`%`→`%25`, CR→`%0D`), reply `D <esc>` + `OK`; on polkit denial reply `ERR 83886179 cancelled`; `BYE` → `OK closing connection`. gpg-agent reuses one pinentry process across retries (sends `SETERROR` before retry `GETPIN`); the pkexec version delegates retry logic to polkit so no latch is needed.

**Never** run `gpg-fingerprint-read` from an agent session (prints the secret into the transcript) — verify length only (`pkexec ... | wc -c`, expect ~2s for a real prompt). Never put the passphrase in argv (`rg -F "$S"` leaks via kernel audit journal). Rotation without leaking: switch pinentry to `pinentry-gnome3` GUI first, `gpg --passwd <keyid>`, verify with `gpg --batch --pinentry-mode cancel --export-secret-keys <keyid>` (exit 2 = protected), migrate keyring→file via `secret-tool lookup ... | sudo tee /etc/gpg-fingerprint/passphrase >/dev/null` (`sudo sh -c 'wc -c < file'` — `<` redirect is opened by the user shell, not root; `secret-tool store` doesn't overwrite — `clear` first). Journal leaks can't be sed-ed out — `journalctl --rotate` + `--vacuum-time=1s`.

Honest gaps (state to the user): passphrase still transits root→user memory (ptrace/`/proc` sniffable); polkit/sudo cache auth briefly; software key on disk stays exportable — only hardware tokens (YubiKey Bio) make it unexportable.

_Migrated from: fingerprint-gated-gpg-unlock_

## Older design: fprintd-verify + keyring pinentry (superseded)

Kept for machines still on it: wrapper loops `fprintd-verify` (with `notify-send` prompts, no `/dev/tty` — the supervised agent has none and `GPG_TTY` may be literally "not a tty"), fetches the passphrase via `secret-tool lookup`, falls back to `zenity --entry --hide-text`; `gpg-agent.conf` same shape with `ttl 0`; `gpgconf --kill gpg-agent` to reload. Two dominant gotchas: no passphrase = no pinentry = gate never fires (check `gpg --batch --pinentry-mode cancel --export-secret-keys KEYID`; exit 0 means unprotected — `gpg --passwd KEYID` adds protection without changing the key); and `gpg --passwd` while the wrapper is active hangs — temporarily point at `pinentry-gnome3`, rotate, restore. Same-user bypass (`secret-tool lookup` + `--pinentry-mode loopback`) and auto-unlocked keyring mean this is a UX/convenience gate, not a security boundary; trailers are cosmetic and `--no-verify` skippable.

_Migrated from: gpg-fingerprint-pinentry-gating_

## Diagnosing a signing hang: stale lock vs live prompt

When `git commit -S` hangs on a fingerprint-gated pinentry, don't blindly retry:
1. `ps -eo pid,etimes,args | grep -E "[p]inentry-fprintd|[g]pg-fingerprint-read"` — a live `pkexec` pid = real polkit prompt on the user's screen, only their scan unblocks it (~40s, then ask if a dialog appeared). An old pid (>5 min) = stale lock from a timed-out attempt: `pkill -f pinentry-fprintd; pkill -f gpg-fingerprint-read`, `gpgconf --kill gpg-agent`, retry.
2. `journalctl --user --since "-3min" | grep -iE "gpg-agent|pinentry"` — `failed to acquire the pinentry lock: Timeout` confirms a stale holder.
3. Live prompt but no dialog on screen → polkit agent suspect: `systemctl --user is-enabled hyprpolkitagent`, check the desktop's own agent registration.
4. Never stack retries — each timeout leaves another stale holder.

_Migrated from: gpg-fingerprint-signing-hang-diagnosis_

## Re-enrolling a worn fingerprint

Old enrollment still matches but with degraded confidence; `fprintd-delete $USER` fails `AlreadyInUse: Device was already claimed` (stale claim — don't chase it). Skip delete: `fprintd-enroll -f <finger-name>` overwrites that finger directly. Run interactively in a real PTY (`hub start`, `pty: true`); `Enroll result: enroll-completed` is the goal, `enroll-stage-passed`/`finger-not-centered`/`retry-scan` are normal. Verify: `fprintd-verify` → `verify-match (done)`. No sudo needed for your own account.

_Migrated from: fprintd-re-enroll-stale-claim_
