---
name: omacale-omarchy-shell-install
description: "Installing, updating, or fully removing the omacale (Caelestia-style) Omarchy bar plugin; icons show as text, handover/state flags wrong, keybind conflicts, uninstall leftovers."
---

# Installing omacale on Omarchy (reversible, full experience)

Repo: https://github.com/AyushKr2003/omacale. Clone to ~/Documents/Development/omacale.
Do NOT use `omarchy plugin add` alone: icons then render as text because the
Material Symbols font is missing. The repo's own `./install.sh` handles the font.

If the user says "everything" / "full experience", enable every optional piece
(notifications, OSD, cava, keybinds, window styling) instead of skipping them
conservatively. Only the lock screen can be legitimately refused (see below); say so
up front and explain the gate rather than silently skipping.

## Order that works
1. Clone, read `install.sh` -> `scripts/omacale`. Run `scripts/omacale install --dry-run`.
2. Back up first: `~/.config/omarchy/{shell.json,shell.toml,bar.json}`, the plugins list,
   `~/.config/hypr/{bindings,looknfeel}.lua`, and any existing `<user>.notifications` clone.
3. Font + cava need sudo. In the bash tool use `pty: true` and run
   `omarchy pkg add ttf-material-symbols-variable` / `omarchy pkg add cava`
   (fingerprint prompt shows; a non-PTY run fails with "a password is required").
4. Do the real install in ONE pass with every option, so state is recorded:
   `./install.sh --yes --notif-popups --osd --with-cava [--no-lock-screen]`

## State-flag trap (matters for "can I undo this")
`~/.local/state/omacale/state.json` has installedNotifClone / installedOsdClone /
installedLockClone / installedCava / installedFont. `uninstall` only reverses what
these say. An upgrade re-run (`./install.sh` when already installed) IGNORES new flags
and does not set them. Running `scripts/osd-handover install` by hand patches the plugin
but leaves the flag false -> uninstall orphans the clone. Fix: `scripts/osd-handover remove`,
`scripts/notif-popups remove`, `scripts/omacale uninstall --yes`, then a fresh full install.
NOTE: osd-handover `install --dry-run` REALLY APPLIES the patch.

Packages you installed yourself (font, cava) are flagged false on purpose, so uninstall
will not remove them.

## Known problems
- Existing `<user>.notifications` clone (e.g. stale `wils.notifications`) is refused:
  "not an Omacale clone ... edits of its own". Diff it against
  /usr/share/omarchy/shell/plugins/notifications; if only upstream drift, move it aside
  (backup) and let `scripts/notif-popups install` re-clone. `notif-popups remove` deletes
  the clone and restores stock omarchy.notifications, so RESTORE the user's original
  clone + shell.json from backup afterwards if they had one.
- Lock screen refused when Omarchy's lock Service.qml sha256 is not in VERIFIED_SERVICES
  in scripts/lock-screen (only Omarchy 4.0.0-4.0.4 and one older dev build, as of 0.53.1).
  Deliberate security gate (the lock view sees the password field; a bad lock service can
  break `omarchy system lock`). Check with `scripts/lock-screen status` (prints sha).
  Do not bypass by editing the hash list without the user explicitly accepting the risk
  and testing lock/unlock.
- `font_present` used `fc-list | grep -q` under `set -o pipefail` -> SIGPIPE -> false
  "could not install ttf-material-symbols-variable" warning. Fix: capture fc-list output
  into a variable before grepping (scripts/omacale ~line 132). A git pull overwrites it.
- Right after install/upgrade restart, doctor may warn "clone runs the current Omarchy
  daemon/OSD"; wait ~6s and recheck (race with the restart).
- `scripts/upstream-check` fails with Permission denied: `tests/test-facade.sh` is not
  executable (chmod +x or run via bash).
- `status` can say "osd: drawn by Omarchy's own OSD" while osd-handover reports patched.

## Keybinds (append to ~/.config/hypr/bindings.lua, marked block)
Omacale claims keys are free in stock Omarchy, but check `omarchy menu keybindings --print`.
Real conflicts: SUPER+A = "Select all", SUPER+SHIFT+I = "Switch input language back".
Use `o.rebind` for those; `o.bind` for free keys. Window styling: append
`pcall(dofile, os.getenv("HOME") .. "/.config/omarchy/plugins/omacale.bar/omacale.lua")`
LAST in looknfeel.lua (overrides gaps/rounding/shadow/animations). Verify with
`hyprctl configerrors` and `omarchy menu keybindings --print | grep -i omacale`.

## Verify
`scripts/omacale doctor`, `status`, `omarchy-shell omacale <drawer>` for
launcher/dashboard/sidebar/utilities/session/settings/overview/close, `notify-send` and
`hyprctl layers -j` for an `omacale-notifications` layer. Screenshot with `grim` and view it;
the dashboard IPC may not have rendered yet (a screenshot once caught the overview instead),
so don't claim icons were visually confirmed unless the screenshot shows them.

## Full removal (verified procedure)
1. Make sure the shell is running (`omarchy-shell shell ping` = ok). If not,
   `omarchy restart shell` first, otherwise `uninstall` cannot run
   `omarchy plugin remove` and the notification/OSD clones are left behind
   (stock plugins stay in disabledPlugins/cloneSourceRestores).
2. `scripts/omacale uninstall --yes`.
3. If it warned about clones: `scripts/osd-handover remove` and `scripts/notif-popups remove`
   (notif remove restarts the shell; "notification service did not become ready" is a
   transient race: recheck `omarchy-shell notifications ping` and `notify-send`).
4. Restore `~/.config/hypr/bindings.lua` and `looknfeel.lua` from the pre-install backups
   (uninstall never touches them), then `hyprctl configerrors`.
5. Packages via PTY: `sudo pacman -Rns --noconfirm ttf-material-symbols-variable cava`.
6. `rm -r ~/.config/omacale` (settings dir is left behind). Restore any user clone/shell.json
   from backup, then `omarchy restart shell`.
7. Verify: `cmp` shell.json/shell.toml/bar.json/hypr files with backups, plugin list diff,
   `pacman -Q` fails for the packages, `grep -rli omacale ~/.config/omarchy ~/.config/hypr`
   empty, no `omacale*` layers in `hyprctl layers -j`.
