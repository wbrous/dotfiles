# Keybindings on Omarchy Hyprland

Adding SUPER launch-or-focus bindings under the Lua config, the Tern terminal setup (agent keys, cwd helpers), and the screensaver terminal-override trap.

## Launch-or-focus binding pattern

**Symptom:** adding a new SUPER+... keybinding that launches an app or focuses its existing window.

**Cause:** the file alone does nothing unless wired into `hyprland.lua`, and Omarchy defaults already own many combos.

**Fix:** files live in `~/.config/hypr/apps/<app>.lua`, required from `~/.config/hypr/hyprland.lua`.

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

Hyprland Lua dispatch from the shell: `hyprctl dispatch exec ...` fails (Lua config). Use `hyprctl dispatch 'hl.dsp.exec_cmd("uwsm-app -- cmd")'`, `hl.dsp.window.close({ window = "address:0x..." })`, `hl.dsp.focus({ window = "address:0x..." })`. `omarchy-agent --pick` launches whatever `omarchy default agent` (`~/.config/omarchy/defaults/agent`) is set to, with a picker fallback — bind that rather than hardcoding an agent.

Finding the window-class regex: no `.desktop` entry doesn't mean no GUI — check the binary's own `--help`/subcommands first (e.g. `hermes desktop`). Electron apps: window class usually matches `productName`/`appId` from `package.json`. Otherwise launch it and read `hyprctl clients -j | jq '.[].class'`; or check `StartupWMClass` in the `.desktop` file.

_Migrated from: omarchy-hypr-app-launch-or-focus-binding_

## Tern as default terminal

**Symptom:** Tern (`so.stencil.tern`) is the default terminal but SUPER+RETURN loses cwd, agent keys collide with Omarchy defaults, or closing a window behaves oddly.

**Cause:** `xdg-terminal-exec` silently drops `--dir` and `--app-id` for Tern (its `.desktop` has only `X-TerminalArgExec=-e`); `omarchy-cmd-terminal-cwd` only understands kitty sockets or a plain shell child, so it returns $HOME for Tern.

**Fix:**

- `~/.config/xdg-terminals.list` lists `so.stencil.tern.desktop` first, `kitty.desktop` as fallback. `omarchy default terminal` only accepts alacritty/foot/ghostty/kitty, so edit the file directly. Verify: `xdg-terminal-exec --print-id`. Never route cwd-sensitive launches through xdg-terminal-exec.
- `~/.config/hypr/apps/tern.lua` (required last in `hyprland.lua`) holds everything: `o.window("so\\.stencil\\.tern", { tag = "+terminal" })` (tag drives clipboard Ctrl+Shift+C/V and transparency); `o.rebind("SUPER + RETURN", "Terminal", "tern-launch-cwd")`. Omarchy defaults on SUPER+SHIFT(+ALT/CTRL)+A (ChatGPT, Grok, `omarchy-agent --pick`) are `hl.unbind`-ed first, then: SUPER+SHIFT+A `omp-launch` (omp from ~/Work); SUPER+SHIFT+CTRL+A `omp-launch-cwd` (omp in active terminal's cwd); SUPER+SHIFT+ALT+A Claude webapp (`{ webapp = "https://claude.ai" }`); SUPER+SHIFT+CTRL+ALT+A ChatGPT webapp (`https://chatgpt.com`).
- Helpers in `~/.local/bin`: `active-terminal-cwd` — focused Tern block cwd via `tern inspect --json | jq '[.sessions[].tabs[]|select(.shown)|.blocks[]|select(.focused)|.cwd][0]'` when active class is `so.stencil.tern`, else `omarchy-cmd-terminal-cwd`. `tern-launch-cwd`: `exec setsid uwsm-app -- tern "$(active-terminal-cwd)"`. `omp-launch`: `cd ~/Work` (else `$HOME`) then `exec setsid uwsm-app -- tern -e omp --auto-approve`. `omp-launch-cwd`: same but `cd "$(active-terminal-cwd)"` first (`tern -e` runs in the caller's cwd, hence the cd).
- Apply: `hyprctl reload && hyprctl configerrors`. From a plain shell `HYPRLAND_INSTANCE_SIGNATURE` is unset: `ls /run/user/$UID/hypr/`.

Webapps: default browser is Zen (no `--app=`), so `omarchy-launch-webapp` falls back to `chromium.desktop`. Chromium cold start takes ~5s before the window maps (class `chrome-claude.ai__-Default`); a check right after dispatch sees nothing — wait before concluding failure.

Tern gotchas: window class `so.stencil.tern`. NEVER use `tern -e bash`. `tern DIR` only sets cwd for a fresh session; once the daemon holds a session it attaches and may ignore DIR. Closing a Tern window with a running shell shows a "Close window?" confirm dialog (an extra Hyprland client, same pid) — closing is not quitting; do NOT automate with wtype Return loops. Tern restores window records from `~/.local/state/tern/daemon.state`; deleting it resets state but kills daemon-held programs — avoid unless asked. Launching Tern from an agent tool call can hang the tool (~40s timeout) — background it or use `hyprctl dispatch hl.dsp.exec_cmd`, then close test windows by address. Verify bindings with `hyprctl binds -j | jq` (modmask 64=S, 65=S+Shift, 73=+Alt, 69=+Ctrl, 77=+Ctrl+Alt), tags via `hyprctl clients -j | jq '.[].tags'`.

_Migrated from: tern-terminal-hyprland-launch-bindings_

## Screensaver with a non-standard default terminal

**Symptom:** screensaver shows `Failed to launch child: omarchy-screensaver / No such file or directory / Press Enter or Esc to exit` in a terminal window.

**Cause:** stale local override. Check the omarchy-dev version first: `pacman -Qi omarchy-dev`, and `cat /usr/bin/omarchy-launch-screensaver`.

**Fix:**

- omarchy-dev >= 4.0 (native Wayland layer-shell screensaver): NO override needed. The wrapper is 2 lines: `exec /usr/lib/omarchy-screensaver/omarchy-screensaver "$@"` — no terminal, no `omarchy-screensaver` child command. The old override (`kitty -e omarchy-screensaver`) no longer exists. Fix: `rm ~/.local/bin/omarchy-launch-screensaver; hash -r`.
- omarchy-dev 3.x (terminal-based): override needed for Tern. `cp /usr/bin/omarchy-launch-screensaver ~/.local/bin/ && chmod +x`, replace terminal detection and bail-out with `terminal=kitty` plus a `command -v kitty` guard. Mark it a LOCAL OVERRIDE; after every omarchy update, diff against the packaged script and delete the override if the package changed architecture.

Testing gotchas (4.x): the binary is single-instance (lock `$XDG_RUNTIME_DIR/omarchy-screensaver.lock`); if one is already showing, further launches exit 0 with no layer — check `pgrep -af omarchy-screensaver` and the screen first. Agent shells lack Hyprland env: export `XDG_RUNTIME_DIR=/run/user/1000`, `WAYLAND_DISPLAY=wayland-1`, `HYPRLAND_INSTANCE_SIGNATURE=$(ls /run/user/1000/hypr/ | head -1)`. Layer check: `hyprctl layers | grep org.omarchy.screensaver`. Clean up with `pkill -f 'omarchy-screensaver/omarchy-screensaver'`. Custom text: `~/.config/omarchy/branding/screensaver.txt`.

_Migrated from: omarchy-screensaver-unsupported-default-terminal_
