---
name: omarchy-cursor-reset-after-accent-plugin
description: "Reset Omarchy/Hyprland cursor to stock default after a theme-recoloring cursor plugin (Omarchy-Accent, cursor-accent) was uninstalled without cleanup."
---

# Reset cursor to default on Omarchy/Hyprland after a cursor-recolor plugin

## Find the real default (don't guess)
- Omarchy records the login cursor: `env | grep -E 'OMARCHY_STARTUP_CURSOR|XCURSOR'` -> theme `default`, size 24.
- `/usr/share/icons/default/index.theme` is `Inherits=Adwaita`; `left_ptr` resolves to Adwaita.
- Stock config lives in `/usr/share/omarchy/default/hypr/envs.lua` (size 24) and `startup-cursor.lua`.

## Find plugin leftovers
- Generated themes: `ls ~/.local/share/icons` (look for non-hicolor, e.g. `Omarchy-Accent`, which has hyprcursors/ and `Inherits=Adwaita`).
- State: `ls ~/.local/state | grep -i cursor` (e.g. `cursor-accent/render.json` listing Bibata variants).
- Check timestamps: leftovers may predate whatever you installed this session; don't blame the wrong tool.
- Also grep `~/.config/hypr`, `~/.config/omarchy/hooks/theme-set.d`, gtk settings.ini, `gsettings get org.gnome.desktop.interface cursor-theme`.

## Fix
1. Move (not delete) leftover theme + state dirs to `~/.local/state/cursor-accent-removed-<ts>/`.
2. `hyprctl setcursor default 24`
3. `gsettings set org.gnome.desktop.interface cursor-theme 'default'` and `cursor-size 24`.
4. Tell the user already-open apps may keep a cached cursor: reopen or relogin.

## Verification gotchas
- `grim -c` screenshots include the cursor but the monitor may be fractionally scaled (e.g. 1.25): screenshot px = `hyprctl cursorpos` x scale. Cursor moves between calls, so crops often miss it; don't claim visual confirmation unless the crop shows the arrow.
- Avoid `read W H < <(magick ...)` in the bash tool; it hung. Use plain sequential commands.
