---
name: arch-autologin-gnome-keyring-manual-unlock
description: "Use when setting up or debugging automatic gnome-keyring/Secret Service unlock on an autologin (SDDM/GDM autologin, greetd, or similar) Linux system — especially symptoms like apps (gh CLI, Cider, VS Code, Chrome) repeatedly prompting to create/unlock a new keyring, numbered orphan keyring files (Default_Keyring_1..N) piling up in ~/.local/share/keyrings/, or a GUI dialog reading \"The password you use to log in to your computer no longer matches that of your login keyring.\""
---

## Root cause on autologin systems
Autologin (e.g. `/etc/sddm.conf.d/*.conf` with `[Autologin]`) uses a PAM
service (e.g. `/etc/pam.d/sddm-autologin`) whose `auth` stack is `pam_permit`
— no real password is ever captured. But that PAM file typically still ships
stock `pam_gnome_keyring.so` lines in both `auth` and `session` phases. The
session hook always tries to unlock the login keyring using the (empty)
captured password. Consequences:
- If the keyring has a **blank password**, this actually works — blank
  auto-unlocks with the empty string. This is the standard/documented Arch
  Wiki fix for autologin + keyring, and requires no further work.
- If the keyring has **any real password**, this mismatches on *every*
  login, throwing "the password you use to log in no longer matches that of
  your login keyring" — forever, on every session.
- If the daemon fails to unlock/create consistently (e.g. due to prior
  corruption), gnome-keyring creates a **new numbered keyring** file each
  time instead of reusing `login.keyring`/`Default.keyring`, producing dozens
  of `Default_Keyring_N.keyring` orphans over weeks. Every libsecret/Secret
  Service consumer (gh CLI's `gh auth git-credential`, Cider, browsers,
  VS Code) hits this identically since they all go through the same daemon.

## Fix A — blank password (simplest, matches autologin's built-in behavior)
1. Stop the daemon: `pkill -f gnome-keyring-daemon`.
2. Back up (don't delete outright) and remove all
   `~/.local/share/keyrings/Default*.keyring` and the `default` marker file.
3. Restart unlocked with an empty password, replacing whatever owns the bus:
   `echo -n "" | gnome-keyring-daemon --replace --foreground --components=pkcs11,secrets,ssh --unlock &`
4. Verify: `secret-tool store --label=test service s account a <<< val` then
   `secret-tool lookup service s account a` — no prompt, single clean keyring
   file (not numbered).
5. This persists correctly across real reboots via the stock
   `pam_gnome_keyring.so` autologin session hook — no custom service needed.

## Fix B — real passphrase, root-only file, custom boot-time unlock service
For when the user wants actual at-rest encryption (blank password = zero
protection) despite autologin having no typed password to compare against.

**Critical prerequisite**: strip `pam_gnome_keyring.so` from BOTH
`/etc/pam.d/sddm-autologin` and `/etc/pam.d/sddm` (or gdm/greetd
equivalents) first:
```
sudo sed -i -E '/pam_gnome_keyring\.so/d' /etc/pam.d/sddm-autologin /etc/pam.d/sddm
```
Otherwise the stock hook keeps trying its own (empty-password) unlock every
login and throws the mismatch dialog even though your custom mechanism also
runs. This step is easy to miss because the custom mechanism will *appear*
to work in every test — the mismatch dialog only fires on a genuine
autologin session boot, not on manual daemon restarts.

Components:
1. `/etc/keyring-unlock/<user>.key` — the passphrase, root:root mode 600.
2. `/usr/local/bin/keyring-autounlock.sh` — root-owned script:
   ```sh
   #!/bin/bash
   set -euo pipefail
   TARGET_USER="wils"; TARGET_UID="1000"
   BUS_SOCK="/run/user/${TARGET_UID}/bus"
   for _ in $(seq 1 60); do [ -S "$BUS_SOCK" ] && break; sleep 0.5; done
   cat /etc/keyring-unlock/${TARGET_USER}.key | runuser -u "$TARGET_USER" -- env \
     DBUS_SESSION_BUS_ADDRESS="unix:path=${BUS_SOCK}" \
     XDG_RUNTIME_DIR="/run/user/${TARGET_UID}" \
     gnome-keyring-daemon --unlock
   ```
3. A systemd **system** unit, `After=user@<uid>.service`,
   `Requires=user@<uid>.service`, `Type=oneshot`, `RemainAfterExit=yes`,
   `WantedBy=multi-user.target`, `ExecStart=` the script above. Enable it.

To (re)set the keyring's own password to match, there is no CLI
"change password" for Secret Service — you must delete and recreate:
```
pkill -f gnome-keyring-daemon; sleep 1
rm -f ~/.local/share/keyrings/login.keyring ~/.local/share/keyrings/user.keystore ~/.local/share/keyrings/default
printf '%s' 'NewPassphrase' | gnome-keyring-daemon --replace --foreground --components=pkcs11,secrets,ssh --unlock &
```
Then re-add any secrets (e.g. `gh auth login --with-token`).

## Fundamental testing gotcha — cannot mid-session "test" unlock via CLI
`gnome-keyring-daemon --unlock` **only works to pre-seed a daemon that does
not exist yet** (true boot/login timing, before anything socket-activates
`org.freedesktop.secrets`). Once a daemon is already running and its
collection is locked, there is NO CLI/scriptable way to unlock it with a
plain password — the Secret Service D-Bus spec deliberately routes all
`Unlock()` calls through the registered GUI prompter (the "Authentication
required" dialog), by design, as a security boundary. Calling
`gnome-keyring-daemon --unlock` against an already-locked live daemon exits
0 and silently does nothing.

Practical implication: to validate a boot-unlock script/service without
rebooting, you must fully kill the daemon first
(`pkill -f gnome-keyring-daemon`) so `busctl --user list | grep secret`
shows `(activatable)` with no owning PID — THEN run the unlock mechanism, so
it wins the race to be the first daemon instance (unlocked from birth).
Locking an already-running daemon via
`gdbus call --dest org.freedesktop.secrets ... Service.Lock [...]` and then
trying to unlock it programmatically will always fail and will pop a real
GUI dialog on the user's live desktop — don't do this as a "test", it's
disruptive and the failure is expected/by-design, not a bug in your script.

## Verification without touching the live GUI
```
gdbus call --session --dest org.freedesktop.secrets \
  --object-path /org/freedesktop/secrets/collection/login \
  --method org.freedesktop.DBus.Properties.Get org.freedesktop.Secret.Collection Locked
```
Returns `(<false>,)` when genuinely unlocked. Combine with an app-level
check (`gh auth status`, `secret-tool lookup`) for end-to-end proof.

## sudo/fingerprint auth in a non-interactive harness
See `sudo-interactive-tty-via-hub` skill — every privileged step above needs
a real PTY (`hub start ... pty=true`) for the fingerprint prompt to render;
`sudo -n` and the bash tool's non-PTY shell cannot surface it. Fingerprint
scan windows are short (~15-20s); if `hub wait` times out and logs show
"Verification timed out" + a password fallback prompt, kill and restart the
PTY session fresh rather than waiting longer — the scan window has already
expired.
