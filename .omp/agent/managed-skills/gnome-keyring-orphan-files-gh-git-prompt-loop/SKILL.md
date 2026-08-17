---
name: gnome-keyring-orphan-files-gh-git-prompt-loop
description: "Use when git push over HTTPS repeatedly falls back to an interactive username/password prompt despite gh auth status showing a valid logged-in token, especially after running gh auth refresh \"fixes\" it only for one push before the prompt returns. Also relevant when systemd --user status gnome-keyring-daemon.service logs \"keyring was in an invalid or unrecognized format\" and ~/.local/share/keyrings/ contains many numbered files like Default_Keyring_1..N."
---

## Symptom

`git push` (any https remote, incl. a dotfiles bare repo) intermittently drops to a bare `Username for 'https://github.com':` prompt with no password field, even though `gh auth status` shows a valid token. Running `gh auth refresh` fixes it for exactly one push, then the loop repeats.

## Root cause

gh stores the OAuth token in the OS keyring (gnome-keyring / libsecret). If gnome-keyring isn't auto-unlocked at login (PAM `pam_gnome_keyring.so` not wired into the login/lock chain), each new session that touches the keyring can't unlock the real "Default" keyring and instead creates a **new anonymous numbered keyring** (`Default_Keyring_1`, `Default_Keyring_2`, ... `_13`, `Default_1`, `Default_keyring_1`, etc. in `~/.local/share/keyrings/`). The token gh wrote during `gh auth refresh` lives in whichever keyring was active *then*; a later session/process may be pointed at a different (locked/empty) keyring, so `gh auth git-credential` (wired via `git config credential.https://github.com.helper`) silently fails to return credentials, and git falls back to the raw prompt.

Confirm with:
```
systemctl --user status gnome-keyring-daemon.service   # look for "invalid or unrecognized format" spam
ls ~/.local/share/keyrings/                             # many Default*_<N>.keyring files = smoking gun
```

## Fix (no SSH key available / not wanted)

Don't fight PAM keyring auto-unlock (separate, bigger fix). Instead add a plaintext `git credential-store` as a **fallback helper** after gh's keyring-based one, so retrieval never depends on keyring state:

```bash
TOKEN=$(gh auth token)
git config --global --add credential.https://github.com.helper store
printf 'protocol=https\nhost=github.com\nusername=<gh-username>\npassword=%s\n\n' "$TOKEN" \
  | git credential-store --file ~/.git-credentials store
chmod 600 ~/.git-credentials
```

Verify:
```bash
echo "protocol=https
host=github.com" | git credential fill   # should print username+password with no prompt
```

Git tries credential helpers in config order and falls through to the next one if a helper errors or returns nothing — so keeping gh's helper first (for normal cases) with `store` as a second line is safe and non-destructive.

Tradeoff: token sits in plaintext `~/.git-credentials` (mode 600), not keyring-encrypted. Acceptable when there's no SSH key and the keyring itself is unreliable.

If/when the token rotates or is revoked, refresh the plaintext copy with the same `gh auth token | ... git credential-store store` one-liner.

## Real fix (not applied here, bigger job)

Wire `pam_gnome_keyring.so` into the login manager's PAM auth+session stack so the login password auto-unlocks the *same* Default keyring every session, preventing the numbered-keyring pileup at the source. Out of scope for a quick unblock.
