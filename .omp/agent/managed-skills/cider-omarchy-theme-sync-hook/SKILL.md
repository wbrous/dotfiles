---
name: cider-omarchy-theme-sync-hook
description: "Cider (Apple Music client) follows the Omarchy theme: theme-set hook sets Cider's accent color and light/dark appearance in spa-config.yml, restarting Cider only if it was running. For Cider theming, accent color, spa-config.yml, sh.cider.genten."
---

## Goal

Make Cider's accent color and light/dark mode follow the active Omarchy theme whenever `omarchy theme set` runs. Sibling of `zen-browser-omarchy-theme-sync-hook`.

## Layout

- Canonical script: `~/.omp/cider-omarchy-theme-sync.sh` (tracked in dotfiles next to the Zen and omp sync scripts).
- Hook: symlink `~/.config/omarchy/hooks/theme-set.d/30-cider-theme-sync.sh -> ~/.omp/cider-omarchy-theme-sync.sh`. Machine-specific, untracked; recreate with `ln -sf`.
- Test overrides: `CIDER_SYNC_COLORS_FILE=<colors.toml>` (try any theme without switching yours) and `CIDER_SYNC_CONFIG=<spa-config.yml>`.

## Where Cider stores config (not where you would guess)

- Data dir is `~/.config/sh.cider.genten/`, NOT `~/.config/Cider` (that one exists but is empty). Find it with `ls -l /proc/<pid>/fd` on the running process.
- Settings: `spa-config.yml`. `themes/` exists but is for CSS theme files and is empty; the native accent setting is simpler and sufficient.
- Cider writes a timestamped backup to `config-backups/` on every launch.

## The keys

```yaml
visual:
  appearance: dark            # dark | light | auto (auto follows system prefers-color-scheme)
  ui_custom:
    customAccentColor: true
    customAccentColorValue: "#81a1c1"   # any #rrggbb, not limited to the preset swatches
```

Read from Cider's own UI bundle (`/usr/lib/cider/resources/spa/assets/uiLogic-*.js`): the value is written straight into the CSS variables `--musicKeyColor` and `--keyColor`.

## Why Cider must be stopped before editing

The main process loads the config once at startup (`merge(defaults, file)`), keeps the whole object in memory, and `writeConfig` rewrites the whole file from that copy whenever any setting changes (the UI's `PUT /_/config` replaces the entire config). Editing the file while Cider runs gets silently overwritten. Verified the safe path: Cider does NOT rewrite the file on exit, and an edit made while it is closed survives startup and its migration pass.

There is a live read endpoint, `GET /api/v2/config` on `127.0.0.1:10767`, but it needs an app token (403 `UNAUTHORIZED_APP_TOKEN` without one), so do not rely on it for the hook and do not go looking for the token to bypass it.

## What the script does

1. Resolves `accent` and `mode` with `omarchy-theme-color` (handles semantic and terminal-style palettes). Non-`#rrggbb` accent or a mode other than light/dark fails loudly, exit 1, file untouched.
2. If Cider is running: records its Hyprland workspace name (window class `cider`), then quits it (main process only: `pkill -f '^/usr/lib/cider/Cider$'`).
3. Edits exactly three lines as text, addressed by block and indentation (`visual` > `appearance`, `visual.ui_custom` > the two accent keys), and reads the file back. Text edit instead of a YAML round trip so the rest of the file is byte-identical; the diff is just two lines when only the accent and mode change.
4. Relaunches only if it was running, on the same workspace, with `no_initial_focus=true, suppress_event='activatefocus'` through `hyprctl dispatch "hl.dsp.exec_cmd('uwsm-app -- cider', {...})"` (see `hyprland-launch-app-in-background-no-focus-steal`). If Cider was closed it stays closed. A missing `spa-config.yml` is a clean no-op.

## Color choice

Uses the palette `accent`, NOT `dark_background` like Zen. Cider's accent colors buttons, the active item and playback controls; `dark_background` is near-black and would vanish on a dark UI. The user chose `accent` when asked.

## Verifying

Run with Cider closed and diff `spa-config.yml` (expect two changed lines, idempotent on rerun); sweep every theme with `CIDER_SYNC_COLORS_FILE`; confirm bad palettes leave the file byte-identical (`md5sum -c`); then run with Cider running and check the PID changed and the window is back on its workspace. 28 themes pass. Do NOT screenshot to verify colors when Cider is on a workspace the user is not viewing, and do NOT switch the user's workspace or dispatch focus to test: the user is usually working. Judge focus from a continuous sample only when they are not interacting, and treat a focus change in the middle of a run as possibly the user.
