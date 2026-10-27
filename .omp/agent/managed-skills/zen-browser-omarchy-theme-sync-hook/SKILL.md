---
name: zen-browser-omarchy-theme-sync-hook
description: "Zen Browser follows the Omarchy theme: theme-set hook quits Zen, sets every space's color and light/dark scheme, relaunches only if it was open, on its same Hyprland workspace without stealing focus. For Zen/Omarchy theme sync, light-mode themes, zen.view.window.scheme, Hyprland launch focus rules; not omp."
---

## Goal

Make Zen Browser's spaces (workspaces) and light/dark mode follow the active Omarchy theme, automatically, whenever `omarchy theme set` runs. Same shape as the omp hook (see `omp-omarchy-theme-sync`).

## Layout

- Script: `~/.config/omarchy/hooks/theme-set.d/20-zen-theme-sync.sh`, a real file tracked in dotfiles (mode 100755) and run by Omarchy directly. No symlink, no copy under `~/.omp/` (that dir is runtime data). Do NOT put it under `~/.config/zen/`: that is the browser's profile dir (cookies, sessions) and is not tracked.
- Sibling hooks in the same dir: `omarchy-theme-sync.sh` (omp) and `30-cider-theme-sync.sh`. Fresh machine: check out dotfiles; nothing to link. If `+x` is lost (the watermarks-remover pre-commit can strip it and leave `.bak` files), `chmod +x` it, because Omarchy skips a non-executable hook.
- Palette: `~/.local/state/omarchy/current/theme/colors.toml`. Override with `ZEN_SYNC_COLORS_FILE=<path>` to test any other theme's palette without switching your real one. The hook IGNORES its `$1` theme-name argument and always reads the current palette, so passing a theme name in a test does nothing.

## Palette resolution: use `omarchy-theme-color`, never parse colors.toml yourself

Themes come in two shapes. Stock ones are semantic (`mode`, `dark_background`, ...). Custom/installed ones (e.g. `flexoki-dark`, `ame-quattro`) are terminal-style: only `background`, `foreground`, `color0..color15`, NO `dark_background`, NO `mode`. A hand-rolled parser that requires those keys exits with an error on them, and the hook silently does nothing on theme switch.

`omarchy-theme-color --file <colors.toml> <key>` (on PATH, `/usr/bin/omarchy-theme-color`) is Omarchy's own resolver and handles both: it aliases `colorN`, derives a missing `dark_background` (background mixed 25% toward black), and resolves `mode` as: `mode` key -> `theme_type` -> `light.mode` file beside the toml -> background luminance (sum of RGB > 382 = light) -> dark. Because the whole desktop uses the same resolver, Zen agrees with every other themed app. Do not second-guess it: `spectrum-os` declares `mode = "light"` with a #121212 background, and the helper (correctly, per the file) reports light.

## What the script does

1. Resolves `dark_background` and `mode` via the helper. `light` -> Zen scheme 1, `dark` -> 0; anything else, or a non-`#rrggbb` color, fails loudly (exit 1, nothing touched).
2. If Zen is running: records the Hyprland workspace NAME of Zen's window (`hyprctl clients -j`, class `zen`) BEFORE quitting, then `pkill -TERM` the main process and waits until gone (30s cap). Records `WAS_RUNNING`.
3. Writes the color into every space in `zen-sessions.jsonlz4` AND `zen-sessions-backup/clean.jsonlz4` + `recovery.baklz4` (Zen restores from the backups, so skipping them brings the old theme back).
4. Sets `zen.view.window.scheme` in `prefs.js` (0 dark, 1 light, 2 auto — values from Zen's own gradient-generator code).
5. Relaunches Zen ONLY if `WAS_RUNNING`, onto the recorded workspace, WITHOUT switching the user's workspace or stealing focus. If Zen was closed it stays closed (verified: 0 processes 15s after the hook). The window genuinely closes for about 3s and reopens on the same workspace (Hyprland logs `closewindow` then `openwindow`).

## Relaunching without disturbing the user (Hyprland 0.56, Lua API)

`hyprctl dispatch "hl.dsp.exec_cmd('zen-browser', {workspace='1', no_initial_focus=true, suppress_event='activatefocus'})"`. BOTH focus rules are required. Measured by quitting/relaunching Zen and sampling `hyprctl activewindow` every 250ms for 25s, repeated:

| rules | result |
|---|---|
| `workspace` alone | steals focus, view jumps to Zen's workspace |
| `workspace` + `no_focus` | still switches the view |
| `workspace` + `no_initial_focus` | steals focus AFTER mapping (Zen requests activation once up; `misc:focus_on_activate = true`) |
| `workspace` + `no_initial_focus` + `suppress_event='activatefocus'` | no focus change, 3/3 runs, and in the full hook end to end |

A throwaway `foot` probe window passed with `no_initial_focus` alone because it never requests activation, so a probe window is NOT a valid test: use real Zen. The rules table on `exec_cmd` accepts window-rule keys; `hl.dsp.exec_cmd('cmd', rules)` with a bare `exec_cmd` and no args errors. Use the workspace NAME (not id) and validate it against `^[A-Za-z0-9_:.+-]+$` before interpolating into the Lua string.

## Facts that cost time

- Zen rewrites session files and `prefs.js` on exit, so edit them ONLY while Zen is stopped. Never use `user.js` for the scheme: it pins the value and breaks the in-app toggle.
- Profile dir comes from `~/.config/zen/installs.ini` (`Default=`), e.g. `bdgpnptr.Default (release)` — contains a space and parentheses, quote it.
- Session files are mozlz4 (`mozLz40\0` + lz4 block, `store_size=True`). Use `uv run --with lz4 python`; no system lz4 module.
- A flat, exact color needs `isCustom: true` with `c` as a CSS string (`"#161622"`), `opacity: 1`, `texture: 0`. With `isCustom: false` Zen blends the color with white/toolbar base at the theme opacity and it never renders exactly. Verified by sampling pixels: sidebar and top toolbar render exactly the hex.
- `((waited++))` returns exit 1 when `waited` is 0, so under `set -e` it silently aborts the script on the first loop pass. This killed Zen and left it down. Use `waited=$((waited + 1))`.
- Launching from a hook/non-GUI shell: `HYPRLAND_INSTANCE_SIGNATURE` is unset; take the newest dir in `$XDG_RUNTIME_DIR/hypr/`. This Hyprland build uses Lua dispatch syntax (the old `exec zen-browser` form errors).
- `pgrep -f '/opt/zen-browser-bin/zen-bin$'` matches only the main process (children carry extra args), so a changed PID proves a real restart.
- Watch window lifecycle with `socat -u UNIX-CONNECT:/run/user/1000/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock -` filtered on `openwindow|closewindow|activewindow`.
- Zen's userChrome/userContent are not needed; removing the Catppuccin CSS leaves only Zen's own `chrome/zen-themes*` (mods), which must stay.

## Verifying

Run the hook with Zen running and check: exit 0, main PID changed, `prefs.js` scheme matches the mode, session file spaces equal `omarchy-theme-color dark_background`, and focus sampling shows the user's workspace/window never changed. Do NOT verify colour with `grim` when Zen is on a workspace the user is not viewing: `grim` captures the visible workspace, so you sample a different window (and capturing Zen would mean switching the user's view). Verify via the session file instead, or only screenshot when Zen is on the visible workspace. Sweep every theme with `for d in ~/.local/share/omarchy/themes/*/ ~/.config/omarchy/themes/*/; do ZEN_SYNC_COLORS_FILE=$d/colors.toml ~/.omp/zen-omarchy-theme-sync.sh; done` (28 themes all pass; `osaka-jade` has no colors.toml and is skipped), then re-run the hook for the real theme to restore state. Always capture screenshots to a fresh filename and `ls` it before reading — a stale file gives false readings.
