---
name: zen-browser-omarchy-theme-sync-hook
description: "Zen Browser follows the Omarchy theme: theme-set hook quits Zen, sets every space's color and light/dark scheme, relaunches. For Zen/Omarchy theme sync, light-mode themes, zen.view.window.scheme; not omp."
---

## Goal

Make Zen Browser's spaces (workspaces) and light/dark mode follow the active Omarchy theme, automatically, whenever `omarchy theme set` runs. Same shape as the omp hook (see `omp-omarchy-theme-sync`).

## Layout

- Canonical script: `~/.omp/zen-omarchy-theme-sync.sh` (tracked in dotfiles next to `omarchy-theme-sync.sh`). Do NOT keep it under `~/.config/zen/` — that is the browser's profile dir (cookies, sessions) and is not tracked.
- Hook: symlink `~/.config/omarchy/hooks/theme-set.d/20-zen-theme-sync.sh -> ~/.omp/zen-omarchy-theme-sync.sh`. Machine-specific, untracked; recreate with `ln -sf`.
- Palette: `~/.local/state/omarchy/current/theme/colors.toml` (override with `ZEN_SYNC_COLORS_FILE` to test other themes without switching your real one).

## What the script does

1. Reads `dark_background` and `mode` from `colors.toml`. `mode = "light"` -> scheme 1; anything else (including empty/missing) -> 0. Fails loudly (exit 1, nothing touched) if `dark_background` is not `#rrggbb`.
2. If Zen is running: `pkill -TERM` the main process, wait until gone (30s cap).
3. Writes the color into every space in `zen-sessions.jsonlz4` AND `zen-sessions-backup/clean.jsonlz4` + `recovery.baklz4` (Zen restores from the backups, so skipping them brings the old theme back).
4. Sets `zen.view.window.scheme` in `prefs.js` (0 dark, 1 light, 2 auto — values from Zen's own gradient-generator code).
5. Relaunches Zen only if it was running before.

## Facts that cost time

- Zen rewrites session files and `prefs.js` on exit, so edit them ONLY while Zen is stopped. Never use `user.js` for the scheme: it pins the value and breaks the in-app toggle.
- Profile dir comes from `~/.config/zen/installs.ini` (`Default=`), e.g. `bdgpnptr.Default (release)` — contains a space and parentheses, quote it.
- Session files are mozlz4 (`mozLz40\0` + lz4 block, `store_size=True`). Use `uv run --with lz4 python`; no system lz4 module.
- A flat, exact color needs `isCustom: true` with `c` as a CSS string (`"#161622"`), `opacity: 1`, `texture: 0`. With `isCustom: false` Zen blends the color with white/toolbar base at the theme opacity and it never renders exactly. Verified by sampling pixels: sidebar and top toolbar render exactly the hex.
- `((waited++))` returns exit 1 when `waited` is 0, so under `set -e` it silently aborts the script on the first loop pass. This killed Zen and left it down. Use `waited=$((waited + 1))`.
- Launching from a hook/non-GUI shell: `HYPRLAND_INSTANCE_SIGNATURE` is unset; take the newest dir in `$XDG_RUNTIME_DIR/hypr/`. This Hyprland build uses Lua dispatch syntax: `hyprctl dispatch 'hl.dsp.exec_cmd("zen-browser")'` (the old `exec zen-browser` form errors).
- `pgrep -f '/opt/zen-browser-bin/zen-bin$'` matches only the main process (children carry extra args), so a changed PID proves a real restart.
- Zen's userChrome/userContent are not needed; removing the Catppuccin CSS leaves only Zen's own `chrome/zen-themes*` (mods), which must stay.
- Some Omarchy themes (e.g. custom `ame-quattro`) lack `dark_background`; the script refuses rather than guessing.

## Verifying

Run the hook with Zen running and check: exit 0, main PID changed, `prefs.js` scheme matches the mode, and `grim` + PIL pixel samples of the sidebar/top toolbar equal `dark_background`. Test a light theme with `ZEN_SYNC_COLORS_FILE=~/.local/share/omarchy/themes/catppuccin-latte/colors.toml`, then re-run for the real theme to restore.
