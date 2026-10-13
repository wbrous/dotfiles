---
name: omarchy-strata-file-manager-setup
description: "Replace Nautilus with Strata (lgse/strata) on Omarchy/Hyprland: pacman install, folder handler, keybinds, FileManager1 D-Bus override, portal file chooser, Follow Omarchy theming; not general file-manager issues."
---

# Replace Nautilus with Strata on Omarchy 4 / Hyprland

Strata (github.com/lgse/strata, MIT, Rust+GTK4) already ships everything; nothing to build. Has no plugin API; theme "hooks" = Follow Omarchy, TOML themes in `~/.config/strata/themes/`, `@strata_*` GTK CSS tokens.

## Steps (all verified working)
1. Back up `~/.config/hypr/bindings.lua` and `~/.config/mimeapps.list`.
2. `sudo pacman -S --needed strata` (repo `omarchy`; pulls gtksourceview5). sudo needs a PTY here (bash `pty: true`; fingerprint prompt). Pacman may be newer than GitHub README tag.
3. `xdg-mime default io.github.lgse.Strata.desktop inode/directory`.
4. Append to `~/.config/hypr/bindings.lua`:
   ```lua
   hl.unbind("SUPER + SHIFT + F")
   hl.unbind("SUPER + ALT + SHIFT + F")
   o.bind("SUPER + SHIFT + F", "File manager", { launch = "strata" })
   o.bind("SUPER + ALT + SHIFT + F", "File manager (cwd)", "uwsm-app -- strata \"$(omarchy-cmd-terminal-cwd)\"")
   ```
   then `hyprctl reload; hyprctl configerrors` (empty). Check for chord collisions (e.g. FilmCraft on SUPER+SHIFT+ALT+F in ~/.config/hypr/apps/filmcraft.lua).
5. "Open file location": copy `/usr/share/strata/io.github.lgse.Strata.FileManager1.service` to `~/.local/share/dbus-1/services/org.freedesktop.FileManager1.service`. **The filename MUST equal the bus name** - dbus-broker silently ignores `io.github.lgse.Strata.FileManager1.service` (journal: "not named after the D-Bus name"). Quit Nautilus first; verify with `busctl --user call org.freedesktop.FileManager1 /org/freedesktop/FileManager1 org.freedesktop.FileManager1 ShowItems ass 1 "file://$HOME/Downloads" ""`.
6. `strata --install-portal` (close file dialogs first). It writes `~/.config/xdg-desktop-portal/hyprland-portals.conf` (not portals.conf) with `FileChooser=strata;hyprland;gtk;`. Undo: `strata --uninstall-portal`.
7. Follow Omarchy is on by default (`mode = "omarchy"` in `~/.config/strata/settings.toml`).

## Verification tricks
- Test portal chooser: `GTK_USE_PORTAL=1 zenity --file-selection` -> window class `io.github.lgse.Strata.FileChooser`. Raw gdbus OpenFile to the frontend shows no window (empty parent/options).
- Test live theming: `omarchy-theme-set <theme>` with a theme whose colors.toml differs (aether and pink share a palette here; use ame-quattro/spectrum-os); sample pixels via `grim -g` + `magick`; restore theme after.
- Bash tool: `( cmd & )` subshell backgrounding silently drops processes; use plain `cmd &` and a poll loop on `hyprctl clients -j`.
- `strata --help` doesn't list --install-portal; it exists (`strings /usr/bin/strata`).
