---
name: omacale-omarchy-shell-install
description: "Installing, updating, or uninstalling the omacale (Caelestia-style) Omarchy bar plugin; icons show as text, handover/state flags wrong, keybind conflicts."
---

# Installing omacale on Omarchy (reversible, full experience)

Repo: https://github.com/AyushKr2003/omacale. Clone to ~/Documents/Development/omacale.
Do NOT use `omarchy plugin add` alone: icons then render as text because the
Material Symbols font is missing. The repo's own `./install.sh` handles the font.

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
and does not set them. Running `scripts/osd-handover install` or `--dry-run` of a
handover by hand patches the plugin but leaves the flag false -> uninstall orphans the
clone. Fix: `scripts/osd-handover remove`, `scripts/notif-popups remove`,
`scripts/omacale uninstall --yes`, then a fresh full `./install.sh ...`.
NOTE: handover `install --dry-run` for osd-handover REALLY APPLIES the patch.

Packages you installed yourself (font, cava) are flagged false on purpose, so uninstall
will not remove them.

## Known problems
- Existing `<user>.notifications` clone (e.g. stale `wils.notifications`) is refused:
  "not an Omacale clone ... edits of its own". Diff it against
  /usr/share/omarchy/shell/plugins/notifications; if it is only upstream drift, move it
  aside (backup) and let `scripts/notif-popups install` re-clone. `notif-popups remove`
  later restores stock omarchy.notifications and deletes the clone.
- Lock screen is refused when Omarchy's lock Service.qml sha is not in VERIFIED_SERVICES
  ("not one this Omacale was verified against"). Deliberate security gate (lock view sees
  the password field). Do not override; wait for an omacale update.
- `font_present` used `fc-list | grep -q` under `set -o pipefail` -> SIGPIPE -> false
  "could not install ttf-material-symbols-variable" warning. Fixed locally by capturing
  fc-list output into a variable before grepping (scripts/omacale line ~132).
- Right after an install/upgrade restart, doctor may show "clone runs the current
  Omarchy daemon/OSD" warnings; wait ~6s and recheck, it is a race with the restart.
- `status` can print "osd: drawn by Omarchy's own OSD" while osd-handover status says
  patched/health ok; cosmetic.

## Keybinds (append to ~/.config/hypr/bindings.lua, marked block)
Omacale claims keys are free in stock Omarchy, but check `omarchy menu keybindings --print`.
Real conflicts seen: SUPER+A = "Select all", SUPER+SHIFT+I = "Switch input language back".
Use `o.rebind` (provided by Omarchy) for those; `o.bind` for free keys. Window styling:
append `pcall(dofile, os.getenv("HOME") .. "/.config/omarchy/plugins/omacale.bar/omacale.lua")`
LAST in looknfeel.lua (it overrides gaps/rounding/shadow/animations). Verify with
`hyprctl configerrors` and `omarchy menu keybindings --print | grep -i omacale`.

## Verify
`scripts/omacale doctor`, `status`, `omarchy-shell omacale <drawer>` for
launcher/dashboard/sidebar/utilities/session/settings/overview/close, `notify-send` and
check `hyprctl layers -j` for an `omacale-notifications` layer, `grim` a screenshot to
confirm icons are glyphs.

## Undo
`scripts/omacale uninstall` (restores shell.json, removes plugin, gives back handovers
only if the state flags are true). Remove the marked blocks from bindings.lua and
looknfeel.lua by hand.
