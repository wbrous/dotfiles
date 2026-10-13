---
name: omarchy-hypr-app-launch-or-focus-binding
description: "Use when adding a new SUPER+... Hyprland keybinding on Omarchy that launches an app or focuses its existing window (omarchy-launch-or-focus), following this user's ~/.config/hypr/apps/*.lua convention — e.g. \"add a shortcut for X\", \"launch or focus X app\", \"bind tern / default agent / terminal in cwd\"."
---

## Pattern for adding a launch-or-focus app binding under Omarchy/Hyprland (lua config)

Files: `~/.config/hypr/apps/<app>.lua`, required from `~/.config/hypr/hyprland.lua`.

1. Check for collisions BEFORE picking a combo: `grep -rn "<KEY>" /usr/share/omarchy/default/hypr/bindings/ ~/.config/hypr/*.lua`. Omarchy defaults already own many combos (e.g. SUPER+SHIFT+A ChatGPT, +ALT+A Grok, +CTRL+A `omarchy-agent --pick`). Rebinding requires `hl.unbind("<combo>")` first (unbind once per combo, in the same file before `o.bind`).
2. Create `~/.config/hypr/apps/<name>.lua`:
   ```lua
   -- Launch or focus <App>.
   o.bind("SUPER + SHIFT + <KEY>", "<Label>", 'omarchy-launch-or-focus ^<window-class-regex>$ "uwsm-app -- <launch-command>"')
   ```
   - `omarchy-launch-or-focus` (in `/usr/share/omarchy/bin/`) takes `<window-pattern>` (regex vs hyprctl clients `.class`/`.title`, case-insensitive) and `<launch-command>`. Plain launch (no focus toggle): `o.bind(keys, "Label", "uwsm-app -- cmd")`.
   - For autostart-on-boot + workspace pinning, use `o.window(...)` + `hl.on("hyprland.start", ...)` (see `apps/cider.lua`, `apps/pulsemeeter.lua`).
3. Add `require("hypr.apps.<name>")` at the bottom of `~/.config/hypr/hyprland.lua` — creating the file alone does NOT wire it in.
4. Apply with `hyprctl reload`; verify with `hyprctl binds -j | jq` (modmask: SUPER=64, SHIFT=1, CTRL=4, ALT=8).

### Hyprland lua dispatch from the shell
`hyprctl dispatch exec ...` fails (lua config). Use `hyprctl dispatch 'hl.dsp.exec_cmd("uwsm-app -- cmd")'`, `hl.dsp.window.close({ window = "address:0x..." })`, `hl.dsp.focus({ window = "address:0x..." })`.

### Default coding agent key
`omarchy-agent --pick` launches whatever `omarchy default agent` (`~/.config/omarchy/defaults/agent`) is set to, with a picker fallback. Bind that rather than hardcoding an agent.

### "Terminal in cwd" for non-kitty terminals
`omarchy-cmd-terminal-cwd` only understands kitty sockets or a plain shell child of the window pid; it returns $HOME for others. For Tern (class `so.stencil.tern`, binary `~/.local/bin/tern`, `tern [DIR]` opens a tab in DIR): cwd of focused pane = `tern inspect --json | jq -r '[.sessions[].tabs[] | select(.shown) | .blocks[] | select(.focused) | .cwd][0]'`. User's wrapper: `~/.local/bin/tern-launch-cwd` (tern branch if active class is tern, else omarchy-cmd-terminal-cwd). Bindings in `~/.config/hypr/apps/tern.lua`.
- Testing launches via bash tool: launching tern from a tool call can hang the tool (40s timeout) — background it / use `hyprctl dispatch hl.dsp.exec_cmd`, then close test windows by address.

### Finding the right window-class regex and launch command
- No `.desktop` entry doesn't mean no GUI: check the binary's own `--help`/subcommands first (e.g. `hermes desktop`).
- Electron apps: window class usually matches `productName`/`appId` from `package.json`. Otherwise launch it and read `hyprctl clients -j | jq '.[].class'`; or check `StartupWMClass` in the .desktop file.
