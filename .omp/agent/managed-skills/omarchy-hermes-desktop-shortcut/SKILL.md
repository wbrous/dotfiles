---
name: omarchy-hermes-desktop-shortcut
description: "Use when adding a Hyprland launch-or-focus keybinding and/or a .desktop app-launcher shortcut for the Hermes AI agent's Electron desktop app on this machine (~/.hermes install) — covers the hermes desktop CLI subcommand, its bundled icon location, and the desktop-file Exec quoting gotcha with omarchy-launch-or-focus."
---

## Context

Hermes (Nous Research agent, installed at `~/.hermes/hermes-agent`, CLI at `~/.local/bin/hermes`) ships an Electron desktop app launched via:

```
hermes desktop
```

(subcommand of the `hermes` CLI — builds/launches the packaged app; add `--skip-build` to skip the npm install/package step if already built).

Window class/title for focusing: matches `^[Hh]ermes$` (Electron `productName: "Hermes"`, `appId: com.nousresearch.hermes`).

Bundled icon (1024x1024 PNG, no need to search online): `~/.hermes/hermes-agent/apps/desktop/assets/icon.png`.

## Recipe

1. Install icon into the standard hicolor theme path:
   ```
   mkdir -p ~/.local/share/icons/hicolor/512x512/apps
   cp ~/.hermes/hermes-agent/apps/desktop/assets/icon.png ~/.local/share/icons/hicolor/512x512/apps/hermes.png
   ```

2. Create a plain wrapper script — **do not** put `omarchy-launch-or-focus` with its regex/args directly in a `.desktop` file's `Exec=`. The Desktop Entry spec forbids unescaped `$` and unbalanced quotes in `Exec`, and `desktop-file-validate` will reject it (`reserved character '$'`, `reserved character '''`). Instead:
   ```
   # ~/.local/bin/hermes-launch-or-focus
   #!/usr/bin/env bash
   exec omarchy-launch-or-focus '^[Hh]ermes$' 'uwsm-app -- hermes desktop'
   ```
   `chmod +x` it, confirm it's on PATH.

3. `.desktop` file (`~/.local/share/applications/hermes.desktop`) just calls the wrapper with no args/specials:
   ```
   [Desktop Entry]
   Type=Application
   Name=Hermes
   Comment=Launch or focus the Hermes desktop app
   Exec=hermes-launch-or-focus
   Icon=hermes
   Terminal=false
   Categories=Utility;
   StartupNotify=true
   ```
   Validate with `desktop-file-validate`, then `update-desktop-database ~/.local/share/applications` and `gtk-update-icon-cache ~/.local/share/icons/hicolor`.

4. For the matching Hyprland keybind (project convention: one file per app under `~/.config/hypr/apps/*.lua`, `require`d from `hyprland.lua`), reuse the same wrapper instead of duplicating the omarchy-launch-or-focus call:
   ```lua
   -- ~/.config/hypr/apps/hermes.lua
   o.bind("SUPER + SHIFT + H", "Hermes", "hermes-launch-or-focus")
   ```
   Add `require("hypr.apps.hermes")` in `hyprland.lua` alongside the other app requires, then `hyprctl reload`.

5. Smoke test: run the wrapper directly (`hermes-launch-or-focus &`), confirm it prints `Launching packaged Hermes Desktop: .../release/linux-unpacked/Hermes` and a window appears; kill with `pkill -9 -f "release/linux-unpacked/Hermes"` when done testing (plain `pkill` may not land — the Electron main process ignores SIGTERM briefly).

## Why the shared wrapper matters

Keeping the actual `omarchy-launch-or-focus <pattern> <cmd>` invocation in exactly one wrapper script (not copy-pasted into both the Lua keybinding and the `.desktop` Exec) avoids drift if the window-class regex or launch command ever needs to change, and sidesteps the Desktop Entry Exec quoting restrictions entirely.
