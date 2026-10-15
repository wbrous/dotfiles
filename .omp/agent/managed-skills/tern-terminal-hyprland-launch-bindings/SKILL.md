---
name: tern-terminal-hyprland-launch-bindings
description: "Tern (so.stencil.tern) as default terminal on Omarchy Hyprland: xdg-terminals.list, SUPER+RETURN, omp-in-cwd, terminal tag; double windows, wrong cwd, Close window dialog."
---

## Tern is the default terminal (current setup)
- `~/.config/xdg-terminals.list` lists `so.stencil.tern.desktop` first, `kitty.desktop` as fallback. `omarchy default terminal` only accepts alacritty/foot/ghostty/kitty, so edit the file directly. Verify: `xdg-terminal-exec --print-id`.
- **xdg-terminal-exec silently drops `--dir` and `--app-id` for Tern** (its .desktop has only `X-TerminalArgExec=-e`). So Omarchy's `omarchy-launch-terminal` (SUPER+RETURN default) loses cwd, and `omarchy-cmd-terminal-cwd` can't see inside Tern anyway. Never route cwd-sensitive launches through xdg-terminal-exec.
- `~/.config/hypr/apps/tern.lua` (required last in `hyprland.lua`) holds everything: `o.window("so\\.stencil\\.tern", { tag = "+terminal" })` (Omarchy's terminal tag is a fixed class list; the tag drives clipboard Ctrl+Shift+C/V and transparency, `transparent-window` follows automatically), `o.rebind("SUPER + RETURN", "Terminal", "tern-launch-cwd")`, and `o.bind("SUPER + SHIFT + CTRL + ALT + A", "omp (cwd)", "omp-launch-cwd")`.
- No Tern-specific binds on SUPER+SHIFT+A any more: those were redundant with SUPER+RETURN and had required unbinding Omarchy's ChatGPT / Grok / Agent (`omarchy-agent --pick`) defaults, which are restored. Do not re-add the unbinds.
- Apply: `hyprctl reload && hyprctl configerrors`. From a plain shell `HYPRLAND_INSTANCE_SIGNATURE` is unset: `ls /run/user/$UID/hypr/`.

## Helpers in `~/.local/bin`
- `active-terminal-cwd`: focused Tern block cwd via `tern inspect --json | jq '[.sessions[].tabs[]|select(.shown)|.blocks[]|select(.focused)|.cwd][0]'` when active class is `so.stencil.tern`, else `omarchy-cmd-terminal-cwd`.
- `tern-launch-cwd`: `exec setsid uwsm-app -- tern "$(active-terminal-cwd)"`.
- `omp-launch-cwd`: `cd "$(active-terminal-cwd)"` then `exec setsid uwsm-app -- tern -e omp --auto-approve` (`tern -e` runs in the caller's cwd, hence the cd). No Omarchy window rule matches `org.omarchy.agent`, so the dropped app-id costs nothing.

## Tern behaviours / gotchas
- Window class `so.stencil.tern`. NEVER use `tern -e bash` (user explicitly forbade it).
- `tern DIR` only sets cwd for a fresh session; once the daemon holds a session it attaches to it and may ignore DIR (a launched window's shell showed cwd `/home/wils`, not the requested dir). `tern new tab --cwd DIR` + `tern focus <block id>` work via CLI but target the first window.
- Closing a Tern window with a running shell shows a "Close window?" confirm dialog, which Hyprland lists as an extra client (same pid). Closing is not quitting. Do NOT automate this with wtype Return loops (user objected). To remove a test window, `kill` just its pid.
- Tern restores previous window records from `~/.local/state/tern/daemon.state`; many accumulated records make a plain launch reopen many windows. Deleting that file/daemon resets state (kills daemon-held programs) — avoid unless asked.
- Hyprland Lua dispatch: `hyprctl dispatch 'hl.dsp.exec_cmd("...")'`.

## Testing without side effects
Verify bindings with `hyprctl binds -j | jq` (modmask 64=S, 65=S+Shift, 73=+Alt, 69=+Ctrl, 77=+Ctrl+Alt; guard `.description // ""`), check tags via `hyprctl clients -j | jq '.[].tags'`, launch once, kill only that window's pid. When stubbing `tern` on PATH to test a launcher, pass `tern inspect` through to the real binary or `active-terminal-cwd` falls back to `$HOME`.
