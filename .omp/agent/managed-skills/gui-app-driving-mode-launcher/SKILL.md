---
name: gui-app-driving-mode-launcher
description: "Use when onboarding a GUI app that has an agent control port (e.g. another Craft app: --control PORT) onto Omarchy: single-instance launch-or-focus script, .desktop override, Hyprland bind, mcp.json bridge entry."
---

# Driving-mode launch-or-focus onboarding (worked for PhotoCraft and FilmCraft)

Templates: `~/.local/bin/photocraft-launch-or-focus`, `~/.local/bin/filmcraft-launch-or-focus`. Copy the closer one. See skills `photocraft`, `filmcraft`, `omarchy-hypr-app-launch-or-focus-binding`.

## 1. Survey the app FIRST (they differ; do not copy flags)
- `<app>-cli --help` and `<app>-cli mcp --help`; docs at `/usr/share/doc/<pkg>/README.md`, upstream `docs/control-protocol.md` and `docs/agents.md` (raw.githubusercontent.com/storytold/<app>/main/docs/).
- Does `--control` take a token file? Are there `--automation-read/write-root` flags? (PhotoCraft yes; FilmCraft NO: unauthenticated, unsandboxed.) Check with `<app>-cli mcp --automation-read-root /tmp` (unknown option = unsupported).
- Native Wayland or XWayland? Compare `hyprctl clients -j` (`xwayland`) and window size vs monitor scale; only XWayland needs `WINIT_X11_SCALE_FACTOR`.
- Window class from `hyprctl clients -j` of a throwaway instance. Pick a free port (`ss -ltn`), unique per app.
- NEVER run the GUI binary with `--help`; it opens a window. Probe instances with an isolated `--data-dir`/`PHOTOCRAFT_CONFIG_DIR` and a different port.
- Does a second instance with a taken port exit? (FilmCraft: no, stays as duplicate window.) That makes the guard load-bearing.

## 2. Launcher script contract
At most ONE GUI. States: none running -> `exec setsid uwsm-app -- <app> --control PORT ... "$@"`; running with `--control PORT` -> focus, exit 0; running without -> focus, notify-send, exit 1.
- Detect driving mode from `/proc/<pid>/cmdline` containing `--control PORT`, NOT from the listening port alone: the port opens 1-2s after start, so port-only gives a false warning on a quick double launch. If cmdline matches, poll the port up to ~10-15s.
- Focus with `omarchy-launch-or-focus '^<exact\.window\.class>$' true` (anchored; helper also matches titles, so browser tabs would match). Pass `true` as the launch command so it never spawns.
- `pgrep -x <app>` (exact; excludes `<app>-cli`). File args cannot be forwarded to a running GUI: print that they are ignored.
- `bash -n` + `shellcheck` clean; use `local _` for unused loop vars.

## 3. Wire it
- `~/.local/share/applications/<id>.desktop`: copy of the /usr one with `Exec=<launcher> %F` and `TryExec=<launcher>` (user override beats package, survives updates). `desktop-file-validate`, `update-desktop-database`.
- `~/.config/hypr/apps/<app>.lua` with `o.bind("SUPER + SHIFT + ALT + <KEY>", ...)`; check the key is free (SUPER+ALT+F is taken by Omarchy); `require("hypr.apps.<app>")` in `hyprland.lua` (re-read it before editing, other agents change it); `hyprctl reload`; verify with `hyprctl binds -j`.
- `~/.omp/agent/mcp.json`: `<App>-Bridge` (`--bridge 127.0.0.1:PORT`, timeout 120000, enabled) and headless `<App>` (disabled). Same-app entries share tool names: enable one. Client needs reload.

## 4. Test matrix (all three states + .desktop)
Cold launch; 3 immediate re-runs (race); re-run with a file arg; plain GUI on isolated config (expect exit 1, still 1 GUI); `gio launch <desktop>` cold and warm (pid set unchanged); bridge round-trip (inspect, edit, undo, screenshot, bogus id). Never kill the user's open GUI: ask them to close it.

## 5. Cleanup
`pkill`ed or `app.quit` GUIs can leave recovery journals that prompt on the user's next launch; use isolated data dirs, delete only journals you created, remove temp files and test outputs.
