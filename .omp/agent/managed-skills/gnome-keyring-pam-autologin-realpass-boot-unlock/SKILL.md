---
name: gnome-keyring-pam-autologin-realpass-boot-unlock
description: "Use when a gnome-keyring \"login\" collection needs to auto-unlock at boot with a real (non-blank) passphrase on an autologin (sddm-autologin or similar) system, especially storing the passphrase in a root-only file unlocked by a privileged systemd service — covers why gnome-keyring-daemon --unlock only works at true daemon-startup (pre-seeding before the socket-activated daemon claims org.freedesktop.secrets on the session bus), and fails silently/prompts the native \"login keyring did not get unlocked\" GUI dialog if run against an already-running, already-bus-owning daemon. Also covers the related symptom where numbered keyring files (Default_Keyring_1..N) proliferate because autologin's PAM auth phase never captures a real password for pam_gnome_keyring to hand to the session phase."
---

## Symptom chain
1. System uses display-manager autologin (e.g. `/etc/sddm.conf.d/autologin.conf` with `[Autologin] User=... Session=...`).
2. `/etc/pam.d/<dm>-autologin` has `pam_gnome_keyring.so` correctly wired in both `auth` and `session` phases (this is already correct per Arch Wiki) — but autologin's auth phase uses `pam_permit.so`, so no real password is ever captured for `pam_gnome_keyring` to relay to the session-phase unlock call.
3. Result: `~/.local/share/keyrings/` accumulates `Default_Keyring_1.keyring`, `Default_Keyring_2.keyring`, ... `_N` — a new anonymous keyring every login, because the daemon never successfully unlocks the persistent one.
4. Any libsecret-consuming app (gh, Cider, etc.) intermittently loses its stored secret and re-prompts/re-creates.

## Fix path 1 — blank-password keyring (works, but zero at-rest protection)
Since autologin has no captured password, the standard fix is a **blank-password** login keyring — it auto-unlocks with an empty string, which is exactly what the uninformed session-phase unlock call provides.

```
systemctl --user stop gnome-keyring-daemon.service gnome-keyring-daemon.socket
pkill -f gnome-keyring-daemon; sleep 1
# back up and remove ALL Default*.keyring / default marker / user.keystore files
echo -n "" | gnome-keyring-daemon --replace --foreground --components=pkcs11,secrets,ssh --unlock &
# first secret-tool store/lookup call lazily creates the fresh keyring file
secret-tool store --label=x service x account x <<< val
```
This collapses the numbered-file pileup into one stable file and survives reboots (PAM session hook repeats the same empty-password unlock every login).

## Fix path 2 — real passphrase in a root-only file + privileged boot unlock (what the user actually wants for at-rest protection)
Mirrors the existing GPG fingerprint-gated pattern (`/etc/gpg-fingerprint/passphrase`, root:root 600) but WITHOUT the polkit/fingerprint gate — this is meant to be zero-interaction at boot.

Components:
- `/etc/keyring-unlock/<user>.key` — root:root 600, the real passphrase.
- `/usr/local/bin/keyring-autounlock.sh` — root-owned, reads the file (root can, user can't) and pipes it into `runuser -u <user> -- env DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/<uid>/bus XDG_RUNTIME_DIR=/run/user/<uid> gnome-keyring-daemon --unlock`.
- systemd **system** unit, `After=user@<uid>.service`, `Requires=user@<uid>.service`, `Type=oneshot`, `RemainAfterExit=yes`, `WantedBy=multi-user.target`.

### The critical gotcha (why a mid-session test looked broken)
`gnome-keyring-daemon --unlock` (without `--replace`) only pre-seeds/unlocks a keyring **at the moment the daemon itself starts** — i.e. before anything has socket-activated `org.freedesktop.secrets` and claimed the session-bus name. If you test this by manually locking an **already-running** daemon mid-session (e.g. via `gdbus call ... org.freedesktop.Secret.Service.Lock [...]`) and then invoking the unlock script, it does NOT reach the live bus-owning daemon — Secret Service's `Unlock()` on an already-locked, already-running collection always routes through the registered **prompter** (the native GNOME "The login keyring did not get unlocked when you logged into your computer" GUI dialog), not a scriptable passphrase channel. This makes the fix look broken when it actually just wasn't tested correctly.

**Correct validation:** either (a) add `--replace` to the unlock invocation so it force-takes bus ownership even mid-session, or (b) validate via an actual full logout/login or reboot, where the boot service genuinely runs before the desktop's own lazy socket-activation claims the daemon.

### If mid-session recovery is needed right now
The stuck GUI dialog's password field *does* accept the real passphrase directly — fetch it with `sudo cat /etc/keyring-unlock/<user>.key` (via a PTY on fingerprint-gated sudo machines) and type it manually into the dialog. This is the one legitimate way to unlock an already-running, already-locked, bus-owning daemon without a code path — GUI prompter is authoritative once the daemon owns the bus name.

## Sudo caveat on fingerprint machines
Each new PTY-launched `sudo` invocation (via `hub start ... pty=true`) tends to require its own fresh fingerprint scan even if another sudo call recently succeeded — don't assume `sudo -n` will work in a plain bash tool call just because an earlier `hub`-launched sudo succeeded; the credential cache appears tty/session scoped here. Always re-launch through `hub` with a PTY for each privileged call and prompt the user to scan again.
