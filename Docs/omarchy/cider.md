# Cider

Apple Music client on Linux: Omarchy theme-sync hook and manual plugin removal.

## Theme-sync hook (accent + light/dark follow the Omarchy theme)

**Symptom:** Want Cider's accent color and appearance to follow `omarchy theme set` automatically. Sibling of the Zen hook.

**Cause / layout:** Script `~/.config/omarchy/hooks/theme-set.d/30-cider-theme-sync.sh` — real tracked dotfiles file, mode 100755, run directly (no symlink, no `~/.omp/` copy). Siblings: `omarchy-theme-sync.sh` (omp), `20-zen-theme-sync.sh`. Test overrides: `CIDER_SYNC_COLORS_FILE=<colors.toml>`, `CIDER_SYNC_CONFIG=<spa-config.yml>`.

**Fix — where Cider stores config:** data dir is `~/.config/sh.cider.genten/` (NOT `~/.config/Cider` — exists but empty; confirm via `ls -l /proc/<pid>/fd`). Settings in `spa-config.yml`; `themes/` is for CSS files (empty) — the native accent setting is sufficient. Cider writes a timestamped backup to `config-backups/` on every launch. Keys:
```yaml
visual:
  appearance: dark            # dark | light | auto
  ui_custom:
    customAccentColor: true
    customAccentColorValue: "#81a1c1"
```
(Read from Cider's UI bundle `/usr/lib/cider/resources/spa/assets/uiLogic-*.js`: written straight into CSS `--musicKeyColor`/`--keyColor`.) Uses palette `accent`, NOT `dark_background` like Zen — near-black would vanish on a dark UI; the user chose accent.

**Fix — stop Cider before editing:** the main process loads config once at startup, keeps it in memory, and `writeConfig` rewrites the whole file from that copy on any setting change (UI `PUT /_/config` replaces everything) — edits while running get silently overwritten. Safe path verified: Cider does NOT rewrite on exit; an edit made while closed survives startup and migration. (Live `GET /api/v2/config` on 127.0.0.1:10767 needs an app token — don't rely on it.) Script: resolve `accent`+`mode` with `omarchy-theme-color` (non-`#rrggbb` or non-light/dark → exit 1, untouched); if running, record Hyprland workspace name (class `cider`), quit main process only (`pkill -f '^/usr/lib/cider/Cider$'`); edit exactly three lines as text by block/indentation (byte-identical otherwise; diff is two lines); read back; relaunch only if it was running, same workspace, `no_initial_focus=true, suppress_event='activatefocus'` via `hyprctl dispatch "hl.dsp.exec_cmd('uwsm-app -- cider', {...})"`; closed stays closed; missing `spa-config.yml` is a clean no-op.

Verify: run closed + diff (two lines, idempotent on rerun); sweep themes via `CIDER_SYNC_COLORS_FILE`; bad palettes leave file byte-identical (`md5sum -c`); run open and check PID changed + window back on workspace. Don't screenshot off-screen Cider; don't switch the user's workspace to test.

_Migrated from: cider-omarchy-theme-sync-hook_

## Removing a broken plugin manually

**Symptom:** A Cider plugin (e.g. Cider Audio Labs / "CiderAudio Expanded") is broken and in-app uninstall fails.

**Cause:** Plugins live on disk: `~/.config/sh.cider.genten/plugins/<identifier>/` with `plugin.yml` (`identifier`, `name`, `marketplaceID`) + `plugin.js`. Audio Labs id is `sh.cider.audiolabs` (also bundles `cideraudio/impulses/*.wav`). Not registered in `spa-config.yml` (grep shows no references), so deleting the folder suffices.

**Fix:**
1. `ls ~/.config/sh.cider.genten/plugins` + read target `plugin.yml` to confirm.
2. Quit Cider first (`pkill -x Cider`, verify `pgrep -x Cider`) so it can't recreate/lock the folder.
3. `rm -rf ~/.config/sh.cider.genten/plugins/<identifier>`.
4. Grep `spa-config.yml` for the identifier; clean only if present.
5. Relaunch; reinstall from marketplace if wanted. (Confirm data dir via `--user-data-dir=` in `pgrep -a Cider`; verified on Arch cider 4.0.9.1.)

_Migrated from: cider-remove-broken-plugin_
