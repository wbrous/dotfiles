---
name: omarchy-sudo-installer-user-units
description: Use when an omarchy omarchy:requires-sudo=true installer enables/disables user systemd units
---

# Sudo omarchy installer managing user units

## When this applies
Installer header has `omarchy:requires-sudo=true` (runs as root via sudo)
AND it must `enable/disable/daemon-reload` `systemctl --user` units.

## The two bugs to avoid
1. **Root cannot reach the user bus.** `sudo` wipes
   `$DBUS_SESSION_BUS_ADDRESS`/`$XDG_RUNTIME_DIR`, so bare
   `systemctl --user ...` as root fails with
   `Failed to connect to user scope bus via local transport`.
2. **Units never deployed.** `systemctl --user enable foo.service` is a
   no-op if the unit file only exists in the repo. Copy it to
   `~/.config/systemd/user/` first (omarchy's `default/systemd/user/`
   convention: `install`, not symlink).

## Pattern
```bash
user=${SUDO_USER:-$USER}
runtime=/run/user/$(id -u "$user")

# deploy
unit_dir=/home/$user/.config/systemd/user
sudo -u "$user" mkdir -p "$unit_dir"
for unit in foo.service bar.service; do
  sudo install -o "$user" -g "$user" -m 644 "$SRC/default/systemd/user/$unit" "$unit_dir/$unit"
done

# enable / reload as the invoking user, not root
sudo -u "$user" XDG_RUNTIME_DIR=$runtime systemctl --user daemon-reload
sudo -u "$user" XDG_RUNTIME_DIR=$runtime systemctl --user enable foo.service bar.service
```

Remover mirrors it: `disable --now` as `$user`, then
`sudo -u "$user" rm -f /home/"$user"/.config/systemd/user/foo.service ...`,
plus root-owned pieces (`/usr/local/bin/...`, polkit policy) with `sudo rm -f`.
Root's own `$XDG_RUNTIME_DIR` is unset under sudo, so use `$runtime` (not
`${XDG_RUNTIME_DIR:?}`) for RAM-state cleanup.

## Verify
- `bash -n` + `shellcheck -S warning` both scripts.
- Dry-run the deploy loop into `mktemp -d` with `install -o "$user"`.
- Re-run under `sudo` and confirm no `user scope bus` error.
