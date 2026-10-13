---
name: tern-terminal-hyprland-launch-bindings
description: "Binding or testing Tern (so.stencil.tern) launch/cwd shortcuts and omp-in-cwd on Omarchy Hyprland; double windows, wrong cwd, Close window dialog."
---

## Setup that works (Omarchy, Lua Hyprland config)
- Bindings in `~/.config/hypr/apps/tern.lua`, required from `~/.config/hypr/hyprland.lua`; apply with `hyprctl reload`. Omarchy defaults on SUPER+SHIFT(+ALT/CTRL)+A (ChatGPT, Grok, `omarchy-agent --pick`) must be `hl.unbind`-ed first.
- Helpers in `~/.local/bin`: `active-terminal-cwd` (focused Tern block cwd via `tern inspect --json | jq '[.sessions[].tabs[]|select(.shown)|.blocks[]|select(.focused)|.cwd][0]'` when active class is `so.stencil.tern`, else `omarchy-cmd-terminal-cwd`, which can't see inside Tern), `tern-launch-cwd` (`exec setsid uwsm-app -- tern "$(active-terminal-cwd)"`), `omp-launch-cwd` (`xdg-terminal-exec --app-id=org.omarchy.agent --dir="$cwd" -e omp --auto-approve`; kitty gets `--working-directory`).
- Plain shortcut: `uwsm-app -- tern "$HOME"` (user wanted ~). `o.bind` commands run via a shell, so `$HOME` expands.

## Tern behaviours / gotchas
- Window class `so.stencil.tern`. NEVER use `tern -e bash` (user explicitly forbade it).
- `tern DIR` only sets cwd for a fresh session; once the daemon holds a session it attaches to it and may ignore DIR. `tern new tab --cwd DIR` + `tern focus <block id>` work via CLI but target the first window.
- Closing a Tern window with a running shell shows a "Close window?" confirm dialog, which Hyprland lists as an extra client (same pid). Test harnesses that "close all" leave windows and inflate counts: closing is not quitting. Do NOT automate this with wtype Return loops (user objected).
- Tern restores previous window records from `~/.local/state/tern/daemon.state`; many accumulated records make a plain launch reopen many windows. Deleting that file/daemon resets state (kills daemon-held programs) — avoid unless asked.
- Hyprland Lua dispatch: `hyprctl dispatch 'hl.dsp.exec_cmd("...")'`, close via `hl.dsp.window.close({ window = "address:0x.." })`.

## Testing without side effects
Verify bindings with `hyprctl binds -j | jq` (modmask 65=S+Shift? 73=+Alt, 69=+Ctrl, 77=+Ctrl+Alt), check launcher commands with `xdg-terminal-exec --print-cmd ...`, launch once, inspect `/proc/<child>/cwd`, kill only that window's pid. Prefer read-only inspection when the user is hand-testing.
