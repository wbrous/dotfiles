---
name: omarchy-strata-file-manager-setup
description: "Replace Nautilus with Strata (lgse/strata) on Omarchy/Hyprland: pacman install, folder handler, FileManager1, portal chooser, keybinds, Follow Omarchy theming, and installer-marker gotchas."
---

# Strata as the Omarchy file manager (verified on Omarchy 4 / Hyprland)

## Install
- `sudo pacman -S --needed strata` (repo `omarchy`; pulls gtksourceview5). Run sudo through bash with `pty: true` (fingerprint prompt). Seen: 0.21.0-2.
- `xdg-mime default io.github.lgse.Strata.desktop inode/directory`; check with `xdg-mime query default inode/directory` and `xdg-open ~/Documents`.

## Do NOT hand-install FileManager1 or keybinds: use Strata's own installer
Strata Settings (Ctrl+,) -> General -> Desktop integration -> "System file manager" writes everything itself. Opening that panel auto-applied it in testing; "Restore default" undoes it.
- It writes `~/.local/share/dbus-1/services/io.github.lgse.Strata.FileManager1.service` (this name is what it looks for; dbus-broker logs a harmless "not named after the D-Bus name" warning, activation still works).
- It appends a block to `~/.config/hypr/bindings.lua` wrapped in `-- strata-installer: file-manager start/end` markers (hl.unbind + o.bind using `/usr/bin/strata`).
- Hand-made copies (a service file named `org.freedesktop.FileManager1.service`, or a bind block without the markers) make the panel show "Another per-user FileManager1 provider is already installed" and mark Reveal/Keyboard shortcuts as unchecked. Delete them first, then let Strata write its own.
- `strata --install-portal` (Open/Save dialogs) writes `~/.config/xdg-desktop-portal/hyprland-portals.conf` (not portals.conf) with `FileChooser=strata;hyprland;gtk;`, plus `strata.portal` and a `org.freedesktop.impl.portal.desktop.strata.service`. Close open file dialogs first (it restarts the portal frontend). Undo: `strata --uninstall-portal`.

## Theming
Settings `mode = "omarchy"` = Follow Omarchy, on by default. Strata recolors live on `omarchy-theme-set`, no restart. Beware: `pink` and `aether` have identical colors.toml; use `ame-quattro` / `spectrum-os` to see a change. No plugin API exists; real hooks are custom TOML themes in `~/.config/strata/themes/` and `@strata_*` GTK CSS tokens.

## Verification recipes (tool quirks)
- Background launch with `( cmd & )` or `setsid` silently drops GUI processes in this bash tool; use a plain `cmd &` job and probe in the same call, or run in foreground with `timeout`.
- Window probe: `hyprctl clients -j | jq` on class `io.github.lgse.Strata` (main) / `io.github.lgse.Strata.FileChooser` (portal). Screenshot: `grim -g "x,y WxH"`.
- Portal test with a real client: `GTK_USE_PORTAL=1 zenity --file-selection`. Raw `gdbus ... FileChooser.OpenFile` with empty options shows no window.
- FileManager1 test: quit nautilus and strata, then `busctl --user call org.freedesktop.FileManager1 /org/freedesktop/FileManager1 org.freedesktop.FileManager1 ShowItems ass 1 "file://$HOME/Downloads" ""`; a Strata window must appear and `pgrep nautilus` stay empty.
- Open Settings via `wtype -M ctrl -k comma -m ctrl` after focusing the window with `hyprctl dispatch 'hl.dsp.focus({window="address:0x..."})'`.

## Related
- Back up `~/.config/hypr/bindings.lua` and `~/.config/mimeapps.list` before editing.
- Personal per-app bind files live in `~/.config/hypr/apps/*.lua` and are `require`d from `hyprland.lua`; remove both when dropping a bind. Chords can collide (SUPER+SHIFT+ALT+F was shared with a launcher bind).
- Not enabled by default: `strata --install-udiskie-unlock` (edits udiskie config).
