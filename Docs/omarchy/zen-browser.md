# Zen Browser

Zen spaces/themes, userChrome CSS install, and the Omarchy theme-sync hook.

## Space themes live in mozlz4 session files

**Symptom:** Space (workspace) themes aren't in places.sqlite or prefs.

**Cause:** They live in `<profile>/zen-sessions.jsonlz4` (mozlz4: 8-byte magic `mozLz40\0` + lz4 block with size header), top-level `spaces[]`, each with a `theme` object. Active profile = the `Default=` path under `[Install...]` in `~/.config/zen/installs.ini` (e.g. `xxxx.Default (release)` — quote it; spaces/parens). `profiles.ini`'s `Default=1` marker may NOT be the active one.

**Fix — rules for every edit:**
- Zen MUST be closed (`pgrep -af zen-bin`, re-check right before writing) — it rewrites the session file on shutdown and overwrites edits.
- No system lz4 python module; use `uv run --with lz4 python`. `omni.ja` is not a normal zip (python zipfile/unzip fail); `strings omni.ja` reveals sources (ZenGradientGenerator, `nsZenThemePicker.getTheme([])`).
- Also patch `zen-sessions-backup/clean.jsonlz4` and `recovery.baklz4` (same format) — restores bring old themes back. Leave dated hourly backups alone.
- Encode with `lz4.block.compress(..., store_size=True)` + magic prefix.

## Setting space colors

**Symptom:** Want spaces themed with exact colors (Catppuccin accent, tab-bar color).

**Fix:** Decode, assert tabs unchanged after edit (compare json of `d["tabs"]`), set each space's `theme`, re-encode, apply to live + two fallback copies, read back names/colors/tab count. Theme shape: `{"type":"gradient","gradientColors":[ENTRY,...],"opacity":0.25,"texture":0.0625}`; ENTRY (non-custom): `{"c":[r,g,b],"isCustom":false,"algorithm":"floating","isPrimary":true,"lightness":"50","type":"explicit-lightness","position":{"x":..,"y":..}}` — only one `isPrimary: true`. `position` mirrors the picker dot: with `h,l,s = colorsys.rgb_to_hls(r/255,g/255,b/255)`, `x=round(190+190*s*cos(h*2π))`, `y=round(190+190*s*sin(h*2π))`. Empty `gradientColors` = no theme (opacity 0.5, texture 0). Catppuccin Mocha reference: tab bar (`#TabsToolbar` in the theme's userChrome.css) = Mantle `#181825`; Mauve `#cba6f7`; Blue `#89b4fa`. When the user says "the tab bar color", read it from chrome/userChrome.css — Mantle is near-black so opacity 0.25 gives a subtle tint. Tell the user it is unverified visually until Zen restarts.

_Migrated from: zen-browser-set-space-theme-color_

## Clearing space themes, keeping spaces

**Symptom:** Remove workspace gradient themes but keep the spaces.

**Fix:** Back up first (`cp -p zen-sessions.jsonlz4 /tmp/...pre-theme-removal`), decode, set every space's theme to Zen's own "no theme" value `{"type":"gradient","gradientColors":[],"opacity":0.5,"texture":0}` (what `nsZenThemePicker.getTheme([])` gives a brand-new space), re-encode, verify spaces keep name/icon/uuid/containerTabId and tab/folder/group counts. Patch the two backup copies too. Can't confirm visually unless Zen is launched — state that limit.

_Migrated from: zen-browser-clear-space-themes_

## Installing a userChrome/userContent CSS theme (e.g. Catppuccin)

**Symptom:** Install a CSS theme into Zen on Linux.

**Fix:**
1. Active profile: `~/.config/zen/installs.ini` `Default=` path (not `profiles.ini`'s `Default=1`).
2. In that profile, `chrome/` may exist from Zen's mod manager (`zen-themes.css`, `zen-themes/`, regenerated — don't edit/overwrite). Add `userChrome.css`, `userContent.css`, assets next to them.
3. Enable stylesheets by appending to `<profile>/user.js`: `user_pref("toolkit.legacyUserProfileCustomizations.stylesheets", true);` (create if absent; don't touch `prefs.js` — rewritten while running).
4. Fetch with `curl -fsSL` from `raw.githubusercontent.com/<repo>/main/...`; for catppuccin/zen-browser: `themes/<Flavor>/<Accent>/{userChrome.css,userContent.css,zen-logo-<flavor>.svg}`. Flavors: Latte, Frappe, Macchiato, Mocha (14 accents incl. Mauve, Blue). Check the CSS references the saved logo filename (`grep zen-logo`). Latte needs light mode, others dark; for OS-setting following, concatenate Latte CSS with a dark flavor's CSS.
5. Tell the user to restart Zen (usually running: `pgrep -a zen`). Rendering can't be checked without restart — say so.

_Migrated from: zen-browser-userchrome-theme-install_

## Omarchy theme-sync hook (spaces + light/dark follow the Omarchy theme)

**Symptom:** Want Zen's spaces and light/dark mode to follow `omarchy theme set` automatically.

**Cause / layout:** Script `~/.config/omarchy/hooks/theme-set.d/20-zen-theme-sync.sh` — real tracked dotfiles file, mode 100755 (Omarchy skips non-executable hooks), run directly, no symlink, no copy under `~/.omp/` (runtime data). Never under `~/.config/zen/` (browser profile, untracked). Siblings: `omarchy-theme-sync.sh` (omp), `30-cider-theme-sync.sh`. Palette: `~/.local/state/omarchy/current/theme/colors.toml`; override `ZEN_SYNC_COLORS_FILE=<path>` to test another theme. The hook IGNORES its `$1` argument — always reads the current palette.

**Fix — resolve palette with `omarchy-theme-color`, never hand-parse:** themes come in two shapes — semantic (has `mode`, `dark_background`) vs terminal-style (only `background`/`foreground`/`color0..15`, e.g. `flexoki-dark`, `ame-quattro`). A hand-rolled parser requiring those keys errors and the hook silently does nothing. `/usr/bin/omarchy-theme-color --file <colors.toml> <key>` handles both (aliases `colorN`, derives missing `dark_background` as background mixed 25% toward black; mode = `mode` key → `theme_type` → `light.mode` file → background luminance sum>382 → dark). Don't second-guess: `spectrum-os` declares light with a #121212 background and the helper (correctly) reports light.

**Fix — what the script does:** resolve `dark_background` + `mode` via the helper (`light`→scheme 1, `dark`→0; anything else or non-`#rrggbb` fails loudly, exit 1, nothing touched). If Zen runs: record its Hyprland workspace NAME (`hyprctl clients -j`, class `zen`), `pkill -TERM` the main process, wait (30s cap). Edit ONLY while stopped (Zen rewrites session files + `prefs.js` on exit; never `user.js` for scheme — pins it). Write color into every space in all three session files (flat exact color needs `isCustom: true`, `c` as CSS string, `opacity: 1`, `texture: 0`; `isCustom: false` blends and never renders exactly). Set `zen.view.window.scheme` in `prefs.js` (0 dark, 1 light). Relaunch ONLY if it was running, onto the recorded workspace, without stealing focus; if closed it stays closed (verified 0 processes 15s after).

**Fix — relaunch without disturbing the user (Hyprland 0.56 Lua API):** `hyprctl dispatch "hl.dsp.exec_cmd('zen-browser', {workspace='1', no_initial_focus=true, suppress_event='activatefocus'})"` — BOTH focus rules required (measured: `workspace` alone steals focus+view; +`no_initial_focus` still steals after mapping since Zen requests activation with `misc:focus_on_activate = true`; both rules = no change 3/3 runs). A `foot` probe passing with `no_initial_focus` alone is NOT valid (never requests activation) — test with real Zen. Validate workspace NAME against `^[A-Za-z0-9_:.+-]+$` before interpolating into Lua.

**Gotchas:** `pgrep -f '/opt/zen-browser-bin/zen-bin$'` matches only the main process (children carry args) — a changed PID proves restart. Hook/non-GUI shells lack HYPRLAND_INSTANCE_SIGNATURE — use newest dir in `$XDG_RUNTIME_DIR/hypr/`; this build uses Lua dispatch syntax (old `exec zen-browser` errors). `((waited++))` returns 1 when `waited` is 0 and silently aborts under `set -e` — use `waited=$((waited + 1))`. Watch lifecycle with `socat -u UNIX-CONNECT:.../.socket2.sock -` filtered on `openwindow|closewindow|activewindow`. userChrome/userContent not needed; Zen's own `chrome/zen-themes*` mods must stay. Verify via session file, not `grim`, when Zen is off-screen (`grim` captures the visible workspace). Sweep all themes with `for d in ...; do ZEN_SYNC_COLORS_FILE=$d/colors.toml <hook>; done`, then re-run for the real theme. Capture screenshots to fresh filenames and `ls` before reading.

_Migrated from: zen-browser-omarchy-theme-sync-hook_
