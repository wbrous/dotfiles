# Omacale Omarchy shell install

Installing, updating, and fully removing the omacale (Caelestia-style) Omarchy bar plugin. Repo: https://github.com/AyushKr2003/omacale.

## Install order

1. Clone to `~/Documents/Development/omacale`. Read `install.sh` → `scripts/omacale`. Run `scripts/omacale install --dry-run`.
2. Back up first: `~/.config/omarchy/{shell.json,shell.toml,bar.json}`, the plugins list, `~/.config/hypr/{bindings,looknfeel}.lua`, and any existing `<user>.notifications` clone.
3. Font + cava need sudo. In a PTY shell run `omarchy pkg add ttf-material-symbols-variable` / `omarchy pkg add cava` (fingerprint prompt; non-PTY fails with "a password is required"). Do NOT use `omarchy plugin add` alone — icons render as text without the Material Symbols font.
4. Real install in ONE pass with every option so state is recorded: `./install.sh --yes --notif-popups --osd --with-cava [--no-lock-screen]`. If the user says "everything"/"full experience", enable every optional piece (notifications, OSD, cava, keybinds, window styling). Only the lock screen may be refused (see gate below); say so up front.

## State-flag trap

`~/.local/state/omacale/state.json` tracks `installedNotifClone` / `installedOsdClone` / `installedLockClone` / `installedCava` / `installedFont`. `uninstall` only reverses what these say. An upgrade re-run ignores new flags. Running `scripts/osd-handover install` by hand patches the plugin but leaves the flag false → uninstall orphans the clone. Fix: `scripts/osd-handover remove`, `scripts/notif-popups remove`, `scripts/omacale uninstall --yes`, then a fresh full install. NOTE: `osd-handover install --dry-run` REALLY APPLIES the patch. Self-installed packages (font, cava) are flagged false on purpose so uninstall won't remove them.

## Known problems

- Existing `<user>.notifications` clone refused ("not an Omacale clone ... edits of its own"). Diff it against `/usr/share/omarchy/shell/plugins/notifications`; if only upstream drift, move it aside and let `scripts/notif-popups install` re-clone. `notif-popups remove` deletes the clone and restores stock, so restore the user's original clone + shell.json from backup afterwards.
- Lock screen refused when Omarchy's lock `Service.qml` sha256 is not in `VERIFIED_SERVICES` in `scripts/lock-screen` (security gate — the lock view sees the password field; a bad lock service can break `omarchy system lock`). Check `scripts/lock-screen status`. Don't bypass the hash list without explicit user risk acceptance + lock/unlock test.
- `font_present` used `fc-list | grep -q` under `set -o pipefail` → SIGPIPE → false "could not install" warning. Fix: capture `fc-list` output into a variable before grepping (a git pull overwrites it).
- Right after install/upgrade restart, doctor may warn "clone runs the current Omarchy daemon/OSD"; wait ~6s and recheck (restart race).
- `scripts/upstream-check` Permission denied: `tests/test-facade.sh` not executable (chmod +x or run via bash).
- `status` can say "osd: drawn by Omarchy's own OSD" while osd-handover reports patched.

## Keybinds

Append the marked block to `~/.config/hypr/bindings.lua`. Omacale claims keys are free in stock Omarchy, but check `omarchy menu keybindings --print`. Real conflicts: SUPER+A ("Select all"), SUPER+SHIFT+I ("Switch input language back") — use `o.rebind` for those, `o.bind` for free keys. Window styling: append `pcall(dofile, ... "omacale.lua")` LAST in `looknfeel.lua`. Verify with `hyprctl configerrors` and `omarchy menu keybindings --print | grep -i omacale`.

## Verify

`scripts/omacale doctor`, `status`, `omarchy-shell omacale <drawer>` (launcher/dashboard/sidebar/utilities/session/settings/overview/close), `notify-send` and `hyprctl layers -j` for an `omacale-notifications` layer. Screenshot with `grim` — the dashboard IPC may not have rendered yet, so don't claim icons confirmed unless the screenshot shows them.

## Full removal

1. Shell must be running (`omarchy-shell shell ping` = ok); `omarchy restart shell` first or `uninstall` can't run `omarchy plugin remove` and clones are left behind.
2. `scripts/omacale uninstall --yes`.
3. If clone warnings: `scripts/osd-handover remove`, `scripts/notif-popups remove` ("notification service did not become ready" is a transient race — recheck `ping` + `notify-send`).
4. Restore `bindings.lua`/`looknfeel.lua` from pre-install backups (uninstall never touches them), then `hyprctl configerrors`.
5. Via PTY: `sudo pacman -Rns --noconfirm ttf-material-symbols-variable cava`.
6. `rm -r ~/.config/omacale`. Restore user clone/shell.json from backup, `omarchy restart shell`.
7. Verify: `cmp` configs with backups, plugin list diff, `pacman -Q` fails for the packages, `grep -rli omacale ~/.config/omarchy ~/.config/hypr` empty, no `omacale*` layers in `hyprctl layers -j`.

_Migrated from: omacale-omarchy-shell-install_
