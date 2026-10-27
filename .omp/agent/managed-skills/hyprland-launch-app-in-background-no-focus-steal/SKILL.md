---
name: hyprland-launch-app-in-background-no-focus-steal
description: "Launch or relaunch a GUI app on a Hyprland workspace without moving the user's view or stealing focus: autostart apps, relaunch after kill, exec_cmd rules table, no_initial_focus, suppress_event activatefocus."
---

## Problem

Apps started at login or relaunched by a script take focus and pull the user's view to their workspace. Window rules like `workspace = "9"` only decide WHERE the window goes, not whether it grabs focus.

## Solution (Hyprland 0.56, Lua config)

Pass a rules table as the second argument of `hl.exec_cmd`:

```lua
hl.exec_cmd(cmd, { workspace = "9", no_initial_focus = true, suppress_event = "activatefocus" })
```

BOTH focus rules are required:
- `no_initial_focus` stops the window being focused when it first maps.
- `suppress_event = "activatefocus"` stops the app taking focus AFTER it maps. Electron (Cider), Firefox-based (Zen) and GTK apps request activation once their window is up, and `misc:focus_on_activate = true` makes Hyprland honour it.

Measured results (sampling `hyprctl activewindow` every 250ms for 20-25s):
- `workspace` alone: steals focus, view jumps.
- `workspace` + `no_focus`: still switches the view.
- `workspace` + `no_initial_focus`: still steals focus after mapping.
- all three rules: no change for Zen, Cider and Pulsemeeter.

## This machine's setup

`~/.config/hypr/apps/background.lua` defines `o.launch_background(command, workspace)` (wraps `o.launch`, i.e. `uwsm-app -- <command>`, plus the three rules). `hyprland.lua` requires it BEFORE the per-app files. `apps/cider.lua` and `apps/pulsemeeter.lua` call it from `hl.on("hyprland.start", ...)` and keep their `o.window(...)` workspace-pinning rules. Use it for any new autostart app.

For the Zen theme-sync hook (outside the Hyprland config) the same table is passed through `hyprctl dispatch "hl.dsp.exec_cmd('zen-browser', {...})"`.

## Testing pitfalls

- A throwaway `foot` window is NOT a valid test: it never requests activation, so it passes even with `no_initial_focus` alone. Use the real app.
- Include a CONTROL run with the old plain launch; it must show the steal, otherwise the test cannot detect the problem.
- Sample focus continuously, not just at the end: a steal can be brief.
- `hyprctl eval "<lua>"` runs Lua in the live config and can call `o.*` helpers; it prints only `ok` and no return value, so write results to a file to inspect them. `hl.exec_cmd` (config API) and `hl.dsp.exec_cmd` (dispatcher) both accept the rules table.
- `hyprctl dispatch` in this build wants Lua syntax (`hl.dsp.focus({workspace="2"})`); `HYPRLAND_INSTANCE_SIGNATURE` is unset in non-GUI shells, take the newest dir under `/run/user/1000/hypr/`.
- `hyprland.start` only fires at compositor start, so the autostart path itself cannot be exercised without logging out; test the helper live and run `hyprctl reload` + `hyprctl configerrors` for syntax.
- NEVER `pkill -f` a pattern that also appears in your own script's arguments: it kills the script (exit 143). Anchor patterns with `^`.
- Edit tool tags must come from a fresh `read`; an invented tag rejects the whole multi-file edit batch.
