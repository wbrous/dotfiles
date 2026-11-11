# Launching Apps on Hyprland

How to start GUI apps on Omarchy/Hyprland (Lua config) without stealing focus, plus the launch-or-focus pattern and the driving-mode launcher contract.

## Launch in background without stealing focus

**Symptom:** apps started at login or relaunched by a script take focus and pull the view to their workspace. `workspace = "9"` window rules only decide WHERE the window goes, not whether it grabs focus.

**Cause:** Electron (Cider), Firefox-based (Zen), and GTK apps request activation after mapping, and `misc:focus_on_activate = true` makes Hyprland honour it.

**Fix:** pass a rules table as the second argument of `hl.exec_cmd` (Hyprland 0.56, Lua config). Both focus rules are required:

```lua
hl.exec_cmd(cmd, { workspace = "9", no_initial_focus = true, suppress_event = "activatefocus" })
```

- `no_initial_focus` stops the window being focused when it first maps.
- `suppress_event = "activatefocus"` stops the app taking focus AFTER it maps.
- `workspace` alone steals focus; `workspace` + `no_focus` still switches the view; `workspace` + `no_initial_focus` still steals focus after mapping. All three rules: no change for Zen, Cider, Pulsemeeter (measured by sampling `hyprctl activewindow` every 250ms for 20-25s).

This machine's setup: `~/.config/hypr/apps/background.lua` defines `o.launch_background(command, workspace)` (wraps `o.launch`, i.e. `uwsm-app -- <command>`, plus the three rules). `hyprland.lua` requires it BEFORE the per-app files. `apps/cider.lua` and `apps/pulsemeeter.lua` call it from `hl.on("hyprland.start", ...)` and keep their `o.window(...)` workspace-pinning rules. For the Zen theme-sync hook (outside the Hyprland config) the same table is passed through `hyprctl dispatch "hl.dsp.exec_cmd('zen-browser', {...})"`.

Testing pitfalls: a throwaway `foot` window never requests activation, so it passes even with `no_initial_focus` alone — use the real app. Include a CONTROL run with the old plain launch (it must show the steal). Sample focus continuously, not just at the end. `hyprctl eval "<lua>"` prints only `ok` and no return value, so write results to a file. `hyprland.start` only fires at compositor start, so the autostart path itself cannot be exercised without logging out; test the helper live and run `hyprctl reload` + `hyprctl configerrors`. NEVER `pkill -f` a pattern that also appears in your own script's arguments (kills the script, exit 143); anchor patterns with `^`.

_Migrated from: hyprland-launch-app-in-background-no-focus-steal_

## Driving-mode launch-or-focus onboarding

**Symptom:** onboarding a GUI app that has an agent control port (e.g. another Craft app with `--control PORT`) onto Omarchy: need single-instance launch-or-focus, `.desktop` override, Hyprland bind, `mcp.json` bridge entry.

**Cause:** each app differs in control flags, auth, sandboxing, and windowing backend; copying flags blindly breaks things.

**Fix:** templates at `~/.local/bin/photocraft-launch-or-focus`, `~/.local/bin/filmcraft-launch-or-focus` — copy the closer one.

1. Survey the app FIRST: `<app>-cli --help` and `<app>-cli mcp --help`; docs at `/usr/share/doc/<pkg>/README.md`. Does `--control` take a token file? Are there `--automation-read/write-root` flags? (PhotoCraft yes; FilmCraft NO: unauthenticated, unsandboxed.) Native Wayland or XWayland? Compare `hyprctl clients -j` (`xwayland`) and window size vs monitor scale; only XWayland needs `WINIT_X11_SCALE_FACTOR`. Window class from `hyprctl clients -j` of a throwaway instance. Pick a free port (`ss -ltn`), unique per app. NEVER run the GUI binary with `--help` (it opens a window). Probe instances with an isolated `--data-dir`/`PHOTOCRAFT_CONFIG_DIR` and a different port. A second instance with a taken port may NOT exit (FilmCraft stays as duplicate window) — that makes the guard load-bearing.

2. Launcher script contract: at most ONE GUI. States: none running -> `exec setsid uwsm-app -- <app> --control PORT ... "$@"`; running with `--control PORT` -> focus, exit 0; running without -> focus, notify-send, exit 1. Detect driving mode from `/proc/<pid>/cmdline` containing `--control PORT`, NOT from the listening port alone (port opens 1-2s after start, so port-only gives a false warning on a quick double launch). If cmdline matches, poll the port up to ~10-15s. Focus with `omarchy-launch-or-focus '^<exact\.window\.class>$' true` (anchored; helper also matches titles, so browser tabs would match). Pass `true` as the launch command so it never spawns. `pgrep -x <app>` (exact; excludes `<app>-cli`). File args cannot be forwarded to a running GUI: print that they are ignored. `bash -n` + `shellcheck` clean.

3. Wire it: `~/.local/share/applications/<id>.desktop` — copy of the /usr one with `Exec=<launcher> %F` and `TryExec=<launcher>` (user override beats package, survives updates). `desktop-file-validate`, `update-desktop-database`. `~/.config/hypr/apps/<app>.lua` with `o.bind("SUPER + SHIFT + ALT + <KEY>", ...)`; check the key is free (SUPER+ALT+F is taken by Omarchy); `require("hypr.apps.<app>")` in `hyprland.lua` (re-read it before editing, other agents change it); `hyprctl reload`; verify with `hyprctl binds -j`. `~/.omp/agent/mcp.json`: `<App>-Bridge` (`--bridge 127.0.0.1:PORT`, timeout 120000, enabled) and headless `<App>` (disabled). Same-app entries share tool names: enable one.

4. Test matrix: cold launch; 3 immediate re-runs (race); re-run with a file arg; plain GUI on isolated config (expect exit 1, still 1 GUI); `gio launch <desktop>` cold and warm (pid set unchanged); bridge round-trip (inspect, edit, undo, screenshot, bogus id). Never kill the user's open GUI: ask them to close it.

5. Cleanup: `pkill`ed or `app.quit` GUIs can leave recovery journals that prompt on the user's next launch; use isolated data dirs, delete only journals you created, remove temp files and test outputs.

_Migrated from: gui-app-driving-mode-launcher_
