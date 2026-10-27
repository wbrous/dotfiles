---
name: zen-browser-omarchy-theme-sync-hook
description: "Zen Browser follows the Omarchy theme: theme-set hook quits Zen, sets every space's color and light/dark scheme, relaunches only if it was open. For Zen/Omarchy theme sync, light-mode themes, zen.view.window.scheme; not omp."
---

## Goal

Make Zen Browser's spaces (workspaces) and light/dark mode follow the active Omarchy theme, automatically, whenever `omarchy theme set` runs. Same shape as the omp hook (see `omp-omarchy-theme-sync`).

## Layout

- Canonical script: `~/.omp/zen-omarchy-theme-sync.sh` (tracked in dotfiles next to `omarchy-theme-sync.sh`). Do NOT keep it under `~/.config/zen/` — that is the browser's profile dir (cookies, sessions) and is not tracked.
- Hook: symlink `~/.config/omarchy/hooks/theme-set.d/20-zen-theme-sync.sh -> ~/.omp/zen-omarchy-theme-sync.sh`. Machine-specific, untracked; recreate with `ln -sf`.
- Palette: `~/.local/state/omarchy/current/theme/colors.toml`. Override with `ZEN_SYNC_COLORS_FILE=<path>` to test any other theme's palette without switching your real one.

## Palette resolution: use `omarchy-theme-color`, never parse colors.toml yourself

Themes come in two shapes. Stock ones are semantic (`mode`, `dark_background`, ...). Custom/installed ones (e.g. `flexoki-dark`, `ame-quattro`) are terminal-style: only `background`, `foreground`, `color0..color15`, NO `dark_background`, NO `mode`. A hand-rolled parser that requires those keys exits with an error on them, and the hook silently does nothing on theme switch.

`omarchy-theme-color --file <colors.toml> <key>` (on PATH, `/usr/bin/omarchy-theme-color`) is Omarchy's own resolver and handles both: it aliases `colorN`, derives a missing `dark_background` (background mixed 25% toward black), and resolves `mode` as: `mode` key -> `theme_type` -> `light.mode` file beside the toml -> background luminance (sum of RGB > 382 = light) -> dark. Because the whole desktop uses the same resolver, Zen agrees with every other themed app. Do not second-guess it: `spectrum-os` declares `mode = "light"` with a #121212 background, and the helper (correctly, per the file) reports light.

## What the script does

1. Resolves `dark_background` and `mode` via the helper. `light` -> Zen scheme 1, `dark` -> 0; anything else, or a non-`#rrggbb` color, fails loudly (exit 1, nothing touched).
2. If Zen is running: `pkill -TERM` the main process, wait until gone (30s cap). Records `WAS_RUNNING`.
3. Writes the color into every space in `zen-sessions.jsonlz4` AND `zen-sessions-backup/clean.jsonlz4` + `recovery.baklz4` (Zen restores from the backups, so skipping them brings the old theme back).
4. Sets `zen.view.window.scheme` in `prefs.js` (0 dark, 1 light, 2 auto — values from Zen's own gradient-generator code).
5. Relaunches Zen ONLY if `WAS_RUNNING`. If Zen was closed it stays closed (verified: 0 processes 15s after the hook).

## Facts that cost time

- Zen rewrites session files and `prefs.js` on exit, so edit them ONLY while Zen is stopped. Never use `user.js` for the scheme: it pins the value and breaks the in-app toggle.
- Profile dir comes from `~/.config/zen/installs.ini` (`Default=`), e.g. `bdgpnptr.Default (release)` — contains a space and parentheses, quote it.
- Session files are mozlz4 (`mozLz40\0` + lz4 block, `store_size=True`). Use `uv run --with lz4 python`; no system lz4 module.
- A flat, exact color needs `isCustom: true` with `c` as a CSS string (`"#161622"`), `opacity: 1`, `texture: 0`. With `isCustom: false` Zen blends the color with white/toolbar base at the theme opacity and it never renders exactly. Verified by sampling pixels: sidebar and top toolbar render exactly the hex.
- `((waited++))` returns exit 1 when `waited` is 0, so under `set -e` it silently aborts the script on the first loop pass. This killed Zen and left it down. Use `waited=$((waited + 1))`.
- Launching from a hook/non-GUI shell: `HYPRLAND_INSTANCE_SIGNATURE` is unset; take the newest dir in `$XDG_RUNTIME_DIR/hypr/`. This Hyprland build uses Lua dispatch syntax: `hyprctl dispatch 'hl.dsp.exec_cmd("zen-browser")'` (the old `exec zen-browser` form errors).
- `pgrep -f '/opt/zen-browser-bin/zen-bin$'` matches only the main process (children carry extra args), so a changed PID proves a real restart.
- Zen's userChrome/userContent are not needed; removing the Catppuccin CSS leaves only Zen's own `chrome/zen-themes*` (mods), which must stay.

## Verifying

Run the hook with Zen running and check: exit 0, main PID changed, `prefs.js` scheme matches the mode, and `grim` + PIL pixel samples of the sidebar/top toolbar equal `dark_background`. Sweep every theme with `for d in ~/.local/share/omarchy/themes/*/ ~/.config/omarchy/themes/*/; do ZEN_SYNC_COLORS_FILE=$d/colors.toml ~/.omp/zen-omarchy-theme-sync.sh; done` (28 themes all pass; `osaka-jade` has no colors.toml and is skipped), then re-run the hook for the real theme to restore state. Always capture screenshots to a fresh filename and `ls` it before reading — a stale file gives false readings.
