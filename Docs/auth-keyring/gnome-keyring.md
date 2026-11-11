# GNOME Keyring on autologin systems

Autologin (SDDM/GDM autologin, greetd) never captures a password, so the login keyring never auto-unlocks — apps re-prompt and numbered `Default_Keyring_N` orphans pile up.

## Root cause

Autologin PAM services (e.g. `/etc/pam.d/sddm-autologin`) use `pam_permit` in `auth` — no password captured — but still ship stock `pam_gnome_keyring.so` in `auth`+`session`. The session hook unlocks with the empty captured password: works only if the keyring has a blank password, throws "the password you use to log in no longer matches that of your login keyring" forever otherwise, and on repeated failure gnome-keyring creates a new numbered keyring each login instead of reusing `login.keyring`. Every libsecret consumer (gh, Cider, browsers, VS Code) hits this identically through the same daemon.

## Fix A — blank password (simplest, zero at-rest protection)

```sh
pkill -f gnome-keyring-daemon
# back up, then remove ~/.local/share/keyrings/Default*.keyring + the `default` marker
echo -n "" | gnome-keyring-daemon --replace --foreground --components=pkcs11,secrets,ssh --unlock &
secret-tool store --label=test service s account a <<< val
secret-tool lookup service s account a   # no prompt, one stable keyring file
```
Persists across reboots via the stock autologin session hook — no custom service.

_Migrated from: arch-autologin-gnome-keyring-manual-unlock, gnome-keyring-pam-autologin-realpass-boot-unlock_

## Fix B — real passphrase + root-only file + boot unlock service

1. Strip `pam_gnome_keyring.so` from BOTH `/etc/pam.d/sddm-autologin` and `/etc/pam.d/sddm` (or gdm/greetd equivalents) first:
```sh
sudo sed -i -E '/pam_gnome_keyring\.so/d' /etc/pam.d/sddm-autologin /etc/pam.d/sddm
```
Otherwise the stock hook keeps attempting empty-password unlocks every login and the mismatch dialog fires even though the custom mechanism works — only visible on genuine autologin boots, not manual daemon restarts.
2. `/etc/keyring-unlock/<user>.key` (root:root 600); `/usr/local/bin/keyring-autounlock.sh` (root-owned) piping the key into `runuser -u <user> -- env DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/<uid>/bus XDG_RUNTIME_DIR=/run/user/<uid> gnome-keyring-daemon --unlock` (waits up to ~30s for the bus socket); systemd **system** unit `After=user@<uid>.service`, `Requires=user@<uid>.service`, `Type=oneshot`, `RemainAfterExit=yes`, `WantedBy=multi-user.target`. To set the keyring password to match: delete and recreate (no CLI change-password for Secret Service).

**Critical gotcha:** `gnome-keyring-daemon --unlock` (no `--replace`) only pre-seeds at daemon startup — before anything socket-activates `org.freedesktop.secrets`. Locking an already-running daemon (`gdbus ... Service.Lock`) then running the script does NOT reach it; Secret Service routes through the registered prompter (native "login keyring did not get unlocked" dialog) instead. Mid-session tests of the script therefore look broken by design. Validate via full logout/login or reboot (service runs before lazy socket-activation claims the daemon), or add `--replace` to force bus ownership mid-session. Mid-session recovery right now: `sudo cat /etc/keyring-unlock/<user>.key` via PTY and type it into the stuck dialog manually.

Verify without touching the GUI:
```sh
gdbus call --session --dest org.freedesktop.secrets --object-path /org/freedesktop/secrets/collection/login \
  --method org.freedesktop.DBus.Properties.Get org.freedesktop.Secret.Collection Locked
# (<false>,) = genuinely unlocked; plus gh auth status / secret-tool lookup end-to-end
```

_Migrated from: arch-autologin-gnome-keyring-manual-unlock, gnome-keyring-pam-autologin-realpass-boot-unlock_

## gh/git HTTPS prompt loop from numbered keyrings

**Symptom:** `git push` drops to `Username for 'https://github.com':` despite valid `gh auth status`; `gh auth refresh` fixes exactly one push. `systemctl --user status gnome-keyring-daemon.service` shows "invalid or unrecognized format"; `~/.local/share/keyrings/` holds many `Default_Keyring_N` / `Default_1` files.

**Cause:** un-unlocked keyring → each session creates a new anonymous numbered keyring; the token from `gh auth refresh` lives in whichever keyring was active then, and a later session points at a different locked/empty one, so `gh auth git-credential` returns nothing and git falls back to prompting.

**Quick unblock (no SSH key):** add plaintext `store` as a fallback helper after gh's keyring one (git tries helpers in order):
```sh
TOKEN=$(gh auth token)
git config --global --add credential.https://github.com.helper store
printf 'protocol=https\nhost=github.com\nusername=<gh-username>\npassword=%s\n\n' "$TOKEN" \
  | git credential-store --file ~/.git-credentials store
chmod 600 ~/.git-credentials
```
Verify: `printf 'protocol=https\nhost=github.com\n' | git credential fill` prints credentials with no prompt. Tradeoff: token in plaintext mode-600 file. Refresh the copy after token rotation. Real fix (bigger job): wire `pam_gnome_keyring.so` into the login manager's PAM stack so one Default keyring unlocks every session.

_Migrated from: gnome-keyring-orphan-files-gh-git-prompt-loop_
