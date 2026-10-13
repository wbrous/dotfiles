---
name: tern-terminal-hyprland-launch-bindings
description: "Binding or testing Tern (so.stencil.tern) launch/cwd shortcuts on Omarchy Hyprland; double windows, cwd ignored, Close window dialog."
---

## Tern launch bindings on Omarchy/Hyprland (lua config)

Observed facts (verified in-session):
- Window class is `so.stencil.tern`. `~/.local/bin/tern` is a symlink to `~/.local/opt/tern/tern`. The first launch also spawns `tern daemon` that keeps sessions alive.
- Omarchy defaults already own SUPER+SHIFT+A (ChatGPT), +ALT+A (Grok), +CTRL+A (`omarchy-agent --pick`, launches `omarchy default agent`). `hl.unbind(...)` them in `~/.config/hypr/apps/tern.lua`, then require it from `hyprland.lua`.
- `omarchy-cmd-terminal-cwd` cannot see into Tern (only kitty sockets / shell child of window pid). For Tern, read cwd with `tern inspect --json | jq '[.sessions[].tabs[]|select(.shown)|.blocks[]|select(.focused)|.cwd][0]'` when the active class is `so.stencil.tern`.
- `tern DIR` only honors DIR for a FRESH daemon session. With a running daemon it opens a window on the existing session and ignores DIR. Use `cd DIR && exec setsid uwsm-app -- tern -e "$SHELL"` instead (verified: new window opens at DIR).
- `hyprctl dispatch` takes Lua here: `hyprctl dispatch 'hl.dsp.exec_cmd("...")'`, `hl.dsp.window.close({ window = "address:0x..." })`, `hl.dsp.focus({...})`.

Testing pitfalls:
- Closing a Tern window with a running shell shows a "Close window?" dialog (itself a separate Hyprland client of the same class). Programmatic close only dismisses/adds dialogs, so window counts are inflated and "closed" windows linger. Confirm with Return (wtype) or have the user close them; do not loop-close automatically.
- Killing the daemon / deleting `~/.local/state/tern/daemon.state` resets sessions and kills running programs; avoid without asking.

Unresolved: plain `tern` sometimes opens 2 windows from one process (log shows "window created id=2" with a second "session started"); cause not found. State records accumulate in daemon.state ("window":[w,h]) and may be the restore trigger; unverified.
