---
name: mise-spinner-looks-like-loop
description: "Use when a captured/pasted terminal transcript shows a mise status line (e.g. \"mise ~/.config/mise/config.toml tools: gh@2.97.0\" with a spinner glyph like ◜) repeated hundreds of times, looking like an infinite reinstall/reconfig loop."
---

## Symptom
A pasted/captured terminal transcript shows a line like:
```
mise ~/.config/mise/config.toml tools: gh@2.97.0                                                                     ◜
```
repeated hundreds of times in a row, as if mise (or Orca, or omp) is stuck reinstalling/reconfiguring a tool in a loop.

## It is not a loop
This is a single mise progress spinner animating for ~1-2 seconds. Spinners redraw in place using `\r` (carriage return) when stdout is a real TTY. When the capture path is not a TTY (e.g. a non-PTY log/read, `orca terminal read`, a piped capture, a markdown paste tool), the spinner library can't overwrite in place, so it falls back to appending a fresh line per animation frame. One brief flicker becomes hundreds of "duplicate" lines in the transcript. The live/interactive pane never actually showed this — only the captured text does.

## Do not blame Orca or omp for this
Verified by direct source inspection (both apps unrelated to this string):
- `~/Applications/orca-ide-extracted/squashfs-root` (Orca's extracted app.asar) has **zero** references to `~/.config/mise/config.toml`, no code that spawns `mise`, and no periodic tool-manifest reconciliation loop. (There was a since-deleted managed skill claiming an "Orca stomps the global mise config every ~2s" root cause — that theory was checked against source and is wrong; do not resurrect it.)
- omp's compiled binary (`~/.cache/.bun/bin/omp`, found via `which omp`) contains no occurrence of the spinner string or mise-config-writing logic either.
- Orca's real terminal panes render through xterm.js + `SerializeAddon`, which is cursor/row-aware and correctly collapses `\r`-driven redraws into a single line — a genuinely interactive pane would never dump this duplication.

## Fix
Disable mise's progress spinner outright so it can't produce this regardless of TTY detection:
```
mise settings set quiet true
```
Verify with `mise settings get quiet` → `true`.
