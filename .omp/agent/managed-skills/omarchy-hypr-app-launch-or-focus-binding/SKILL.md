---
name: omarchy-hypr-app-launch-or-focus-binding
description: "Use when adding a new SUPER+... Hyprland keybinding on Omarchy that launches an app or focuses its existing window (omarchy-launch-or-focus), following this user's ~/.config/hypr/apps/*.lua convention — e.g. \"add a shortcut for X\", \"launch or focus X app\"."
---

## Pattern for adding a launch-or-focus app binding under Omarchy/Hyprland (lua config)

Files: `~/.config/hypr/apps/<app>.lua`, required from `~/.config/hypr/hyprland.lua`.

1. Check `~/.config/hypr/bindings.lua` for already-used SUPER+... combos before picking a new one (avoid collisions; some Omarchy defaults are unbound there via `hl.unbind`).
2. Create `~/.config/hypr/apps/<name>.lua`:
   ```lua
   -- Launch or focus <App>.
   o.bind("SUPER + SHIFT + <KEY>", "<Label>", 'omarchy-launch-or-focus ^<window-class-regex>$ "uwsm-app -- <launch-command>"')
   ```
   - `omarchy-launch-or-focus` (in `/usr/share/omarchy/bin/`) takes `<window-pattern>` (regex matched against hyprctl clients' `.class`/`.title`, case-insensitive, word-boundary) and `<launch-command>`. If launch-command omitted it defaults to `uwsm-app -- <pattern>`.
   - For autostart-on-boot + workspace pinning (not focus-toggle), instead use the `o.window(...)` + `hl.on("hyprland.start", function() hl.exec_cmd(o.launch("<name>")) end)` pattern (see `apps/cider.lua`, `apps/pulsemeeter.lua`) — that's a different use case (always running) vs. launch-or-focus (on-demand toggle).
3. Add `require("hypr.apps.<name>")` in `~/.config/hypr/hyprland.lua` near the other app requires — creating the file alone does NOT wire it in.
4. Apply with `hyprctl reload` (no need to relogin/restart Hyprland).

### Finding the right window-class regex and launch command
- No `.desktop` entry doesn't mean no GUI: check the binary's own `--help`/subcommands first (e.g. `hermes desktop` launches an Electron app bundled inside a Python CLI venv).
- For Electron apps, window class usually matches Electron's `productName`/`appId` from the app's `package.json` (grep for `"productName"`/`"appId"`) — use that (case-insensitively) as the regex.
