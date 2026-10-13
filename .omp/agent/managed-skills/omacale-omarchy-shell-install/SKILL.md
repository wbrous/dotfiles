---
name: omacale-omarchy-shell-install
description: "Installing, updating, or uninstalling the omacale (Caelestia-style) Omarchy bar plugin; icons missing or show as text; Material Symbols font needs sudo."
---

# Installing omacale on Omarchy (reversible)

Repo: https://github.com/AyushKr2003/omacale. Clone location used: `~/Documents/Development/omacale`.

## Why icons break
All icons are Material Symbols glyphs. If `fc-list : family | grep -i "Material Symbols Rounded"` is empty (as with a plain `omarchy plugin install`), icons render as text. Fix: `omarchy pkg add ttf-material-symbols-variable`, then `omarchy-restart-shell`.

## Procedure
1. `git clone https://github.com/AyushKr2003/omacale.git ~/Documents/Development/omacale`
2. Optional manual backup of `~/.config/omarchy/{shell.json,shell.toml,bar.json}` (installer also snapshots to `~/.local/state/omacale/pre-install`).
3. Preview: `scripts/omacale install --dry-run`.
4. Install without the invasive extras:
   `./install.sh --yes --no-notif-popups --no-osd --no-lock-screen --no-cava`
5. The installer's font step calls sudo and FAILS in the bash tool (no TTY, fingerprint auth: "Verification timed out"). Plugin and bar still install fine. Re-run the font step with the bash tool's `pty: true`: `omarchy pkg add ttf-material-symbols-variable` (fingerprint prompt appears; works). See also skill sudo-interactive-tty-via-hub.
6. `omarchy-restart-shell`, then `scripts/omacale doctor` and `scripts/omacale status`.

## Undo / update
- Undo: `scripts/omacale uninstall` (restores shell.json so bar.id is unset -> built-in omarchy.bar, removes plugin dir and the font package it installed).
- Update: `git pull && ./install.sh`.
- Keybinds are not installed by default: `scripts/omacale binds --try` (session only) or paste `keybinds.lua` into `~/.config/hypr/bindings.lua`.
- Optional takeovers (notifications, OSD, lock screen) are separate and can be enabled later in Settings; user's own `wils.notifications` plugin was left untouched.
