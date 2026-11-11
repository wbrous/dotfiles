# Apps

Replacing the file manager and syncing the omp coding-agent theme with Omarchy.

## Strata as the file manager

**Symptom:** Replace Nautilus with Strata (lgse/strata) on Omarchy 4 / Hyprland.

**Fix — install:** `sudo pacman -S --needed strata` (repo `omarchy`; pulls gtksourceview5; run sudo with a pty for the fingerprint prompt; seen 0.21.0-2). `xdg-mime default io.github.lgse.Strata.desktop inode/directory`; check with `xdg-mime query default inode/directory` and `xdg-open ~/Documents`.

**Fix — do NOT hand-install FileManager1 or keybinds; use Strata's own installer:** Strata Settings (Ctrl+,) -> General -> Desktop integration -> "System file manager" writes everything itself (opening the panel auto-applied it in testing; "Restore default" undoes it).
- Writes `~/.local/share/dbus-1/services/io.github.lgse.Strata.FileManager1.service` (dbus-broker logs a harmless "not named after the D-Bus name" warning; activation still works).
- Appends a block to `~/.config/hypr/bindings.lua` wrapped in `-- strata-installer: file-manager start/end` markers. Hand-made copies (a service named `org.freedesktop.FileManager1.service`, or a bind block without markers) make the panel show "Another per-user FileManager1 provider is already installed" — delete them first, then let Strata write its own.
- `strata --install-portal` (Open/Save dialogs) writes `~/.config/xdg-desktop-portal/hyprland-portals.conf` (not portals.conf) with `FileChooser=strata;hyprland;gtk;`, plus `strata.portal` and an `org.freedesktop.impl.portal.desktop.strata.service`. Close open file dialogs first. Undo: `strata --uninstall-portal`.

**Theming:** Settings `mode = "omarchy"` (Follow Omarchy, default) recolors live on `omarchy-theme-set`, no restart. Beware: `pink` and `aether` have identical colors.toml — use `ame-quattro`/`spectrum-os` to see a change. No plugin API; real hooks are custom TOML themes in `~/.config/strata/themes/` and `@strata_*` GTK CSS tokens.

**Verification recipes:** background GUI launches via `( cmd & )`/`setsid` silently die in some shells — use plain `cmd &` + probe, or foreground `timeout`. Window probe: `hyprctl clients -j | jq` on class `io.github.lgse.Strata` / `io.github.lgse.Strata.FileChooser`. Portal test with a real client: `GTK_USE_PORTAL=1 zenity --file-selection` (raw `gdbus FileChooser.OpenFile` with empty options shows no window). FileManager1 test: quit nautilus and strata, then `busctl --user call org.freedesktop.FileManager1 /org/freedesktop/FileManager1 org.freedesktop.FileManager1 ShowItems ass 1 "file://$HOME/Downloads" ""` — a Strata window must appear, `pgrep nautilus` stays empty. Back up `~/.config/hypr/bindings.lua` and `~/.config/mimeapps.list` before editing; per-app binds live in `~/.config/hypr/apps/*.lua` required from `hyprland.lua`. Not default: `strata --install-udiskie-unlock`.

_Migrated from: omarchy-strata-file-manager-setup_

## Syncing the omp coding-agent theme with Omarchy

**Symptom:** Want the omp (oh-my-pi) theme to follow the active Omarchy theme.

**Cause / design:** Two parts, one shared script. Source of truth: `~/.local/state/omarchy/current/theme/colors.toml` (NOT `~/.config/omarchy/current/...` — that path doesn't exist) and slug `~/.local/state/omarchy/current/theme.name`.
1. Shared conversion script at `~/.config/omarchy/hooks/theme-set.d/omarchy-theme-sync.sh` (real tracked executable file, mode 100755 — Omarchy skips non-executable hooks; keep out of `~/.omp/` runtime data and `~/.local/share/omp/`). It reads colors.toml, writes `~/.omp/agent/themes/omarchy.json` (derived state, NOT tracked), and updates `~/.omp/agent/config.yml`.
2. The script IS the Omarchy `theme-set` hook (runs in name order beside `20-zen-theme-sync.sh`, `30-cider-theme-sync.sh`).
3. omp extension (`~/.omp/agent/extensions/omarchy-theme-sync.ts`, tracked mode 100644): on `session_start`, `spawnSync` the same script (`join(homedir(), ".config/omarchy/hooks/theme-set.d/omarchy-theme-sync.sh")`; update the constant if the script moves), then if `ctx.hasUI` call `await ctx.ui.setTheme("omarchy")`.

**Fix — both `theme.dark` AND `theme.light` must be `"omarchy"`:** Omarchy has one active theme; omp's OSC11 auto-detection can pick a stale slot if only one is updated. Always set both unconditionally:
```bash
yq -i -y '.theme.dark = "omarchy" | .theme.light = "omarchy"' "$CONFIG_FILE"
```
On Arch this is **python-yq** 4.1.2 (jq wrapper), not go-yq — `-y` is required; go-yq syntax `yq -i '...'` fails with `-i/--in-place can only be used with -y/-Y/-t/-T/-x`.

**Fix — color mapping:** omp needs 51 tokens (see `omp://theme.md`; validate generated JSON keys against `theme-schema.json` under an installed `@earendil-works/pi-coding-agent` package). Mapping: accent/borderAccent/mdHeading/mdLink/mdListBullet→`accent`; border→`muted`; borderMuted/selectedBg→`selection`; success/toolDiffAdded/syntaxString→`green`; error/toolDiffRemoved→`red`; warning/statusLineGitDirty/statusLineDirty→`yellow`; text/toolTitle/syntaxVariable/mdCode*→`foreground`; dim/syntaxComment/thinkingOff→`dark_foreground`; userMessageBg/customMessageBg/tool*Bg→`lighter_background`; statusLineBg→`dark_background`; syntaxKeyword/thinkingHigh/pythonMode/statusLineModel/statusLineSubagents→`magenta`; syntaxFunction/thinkingLow/statusLinePath→`blue`; syntaxType/thinkingMedium/bashMode/statusLineContext/statusLineSpend→`cyan`; syntaxNumber/statusLineCost→`orange`; syntaxOperator→`foreground`; syntaxPunctuation/toolDiffContext/mdQuote*/mdHr/mdLinkUrl/toolOutput/thinkingMinimal/statusLineSep→`muted`; thinkingXhigh/statusLineUntracked→`red`; statusLineGitClean/statusLineStaged→`green`; statusLineOutput→`foreground`. `thinkingMax` may be omitted (falls back to `thinkingXhigh`).

**Gotchas:** `~/.local/share/omp/` is NOT the agent dir — real data is `~/.omp/agent/`; remove a stray empty `~/.local/share/omp/` (it causes "No model selected"). Launching `omp` for a smoke test may recreate it — clean up after. Verify with `bash -n`, double-run for idempotency, `python3 -m json.tool` on the JSON, schema-key diff; back up/restore `config.yml` around mutating tests. An `omp -p` smoke run failing on missing API keys before `session_start` is expected and not an extension bug.

_Migrated from: omp-omarchy-theme-sync_
