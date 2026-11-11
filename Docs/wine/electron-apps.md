# Running Windows Electron apps under Wine

Covers unpacked standalone Electron `.exe` apps (no installer): launch scripts, wine-vs-GE-Proton selection, and the three recurring failure modes.

## Plain launch script and prefix setup

**Symptom:** need a minimal self-contained install of an unzipped Electron folder (`App.exe` plus DLLs).

**Cause:** n/a — setup task. Plain system `wine` is sufficient for normal Electron apps; do NOT reach for GE-Proton unless the app embeds WebView2/CEF with real WinRT needs or does anti-VM detection.

**Fix:**
```bash
cd ~/Applications/<App>
WINEPREFIX="$PWD/.pfx" WINEDEBUG=-all wineboot --init >/tmp/wineboot.log 2>&1 &
disown
# poll for .pfx/system.reg to appear (wineboot runs async)
```
`launch.sh` in the app dir:
```bash
#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export WINEPREFIX="$DIR/.pfx"
export WINEDEBUG="${WINEDEBUG:--all}"
export WINEDLLOVERRIDES="windows.ui=d"
setsid nohup wine "$DIR/<App>.exe" "$@" >/dev/null 2>&1 < /dev/null &
disown
echo "<App> launched (detached, pid $!)."
```
`chmod +x launch.sh`. Smoke test: `./launch.sh`, then `ps -eo cmd | grep "[A]pp.exe` to confirm main plus `--type=gpu-process` / `--type=utility` children spawned. Kill with `pkill -f "<App>.exe"`.

Note: if unrecognized CLI switches passed to the `.exe` get swallowed or treated as "file to open", the app has custom argv parsing in `resources/app/main.js` — add `app.commandLine.appendSwitch(...)` directly in `main.js` near existing calls instead of passing flags via argv.

_Migrated from: wine-launch-script-plain-electron-exe_

## Silent self-terminate ~15-17s after launch, no window

**Symptom:** main plus `--type=gpu-process` / `--type=utility --utility-sub-type=network.mojom.NetworkService` / `--type=renderer` children visible in `ps`, no window ever maps (`hyprctl clients` shows nothing), all processes vanish ~15-17s after launch, no coredump (`coredumpctl list` empty), no signal.

**Cause:** the mojo IPC handshake between Electron main and sandboxed child processes never completes. Confirm with `ELECTRON_ENABLE_LOGGING=1 wine app.exe --enable-logging=stderr --v=1` — look for `ChildThreadImpl::EnsureConnected()` (`content\child\child_thread_impl.cc:909`) appearing ~15s after the prior log line; that gap is Chromium's fixed `kConnectionTimeoutS`. GE-Proton's wine-staging build breaks the named-pipe/mojo handle inheritance for this pattern; stock `wine` (e.g. wine-11.15) completes it fine.

**Fix:** use plain system `wine`, not GE-Proton, for bare unpacked Electron `.exe` apps with no DirectX/anticheat needs. Things that do NOT fix it: `--no-sandbox`, `--single-process` (worse — crashes in ~2s), `--disable-gpu`, clearing the Electron userData profile.

Track lifecycle with a polling loop, not a single sleep: `ps -eo cmd | grep -c "[A]pp.exe"` plus `hyprctl clients` once per second for 20-25s. A single `grep -c` count is unreliable (matches parent AND every child); disambiguate main vs child via full cmdline.

_Migrated from: wine-electron-app-launch-recipe, wine-electron-mojo-ipc-timeout-and-uisettings-crash, wine-electron-app-under-wine-full-recipe_

## WinRT UISettings stub stack overflow (~1-2s death)

**Symptom:** log shows thousands of `0024:fixme:ui:uisettings2_get_TextScaleFactor iface ... stub!` lines ending in `err:virtual:virtual_setup_exception stack overflow`.

**Cause:** Wine's `windows.ui.dll` `IUISettings2::get_TextScaleFactor` is an unimplemented stub that Chromium's DPI query calls in a loop until stack overflow.

**Fix:** include in every Electron launch script:
```bash
export WINEDLLOVERRIDES="windows.ui=d"
```
This forces `RoGetActivationFactory` to fail cleanly; Electron falls back to a default text scale. Confirm by grepping the run log for `TextScaleFactor` — count should drop to 0. Independent of the mojo fix above; both may be needed at once (fresh `.pfx` via `wineboot --init` under system wine plus the override).

_Migrated from: wine-electron-app-launch-recipe, wine-electron-mojo-ipc-timeout-and-uisettings-crash, wine-electron-app-under-wine-full-recipe_

## Blank text / tofu icon boxes

**Symptom:** window shows but no text renders anywhere; icon-font glyphs (hamburger menu, toolbar icons) show as small black boxes.

**Cause:** fresh `wineboot --init` prefix ships `drive_c/windows/Fonts` completely empty (0 files); Chromium/Skia has no font to rasterize with. Check: `find "$WINEPREFIX/drive_c/windows/Fonts" -maxdepth 1 | wc -l` → `1` means empty.

**Fix:** one-time, persisted in the prefix:
```bash
export WINEPREFIX="$APPDIR/.pfx"
winetricks -q corefonts
```
Verify count goes from 1 to 30+. Don't chase GPU/PNG-alpha theories before ruling this out.

_Migrated from: wine-electron-app-blank-text-clipped-window, wine-electron-app-launch-recipe, wine-electron-app-under-wine-full-recipe_

## Window off-screen / bottom toolbar clipped

**Symptom:** window opens partly off-screen; bottom buttons unclickable; resizing doesn't help.

**Cause:** many Electron apps persist window bounds via `electron-store` into `$WINEPREFIX/drive_c/users/$USER/AppData/Roaming/<AppName>/config.json` (`winBounds: {x,y,width,height}`) and blindly `Object.assign()` them onto the `BrowserWindow` options. A prior crashed run can save garbage (e.g. `{"y": -30, "width": 2888, "height": 1954}` vs a `2880x1920` workArea).

**Fix:** (1) immediate: delete the stale `config.json` (or just the `winBounds` key); (2) durable — if `resources/app/main.js` is unpacked (not `app.asar`), patch `createWindow()` to compute size as ~0.95 of `screen.getPrimaryDisplay().workArea`, centered, instead of trusting saved bounds (95%, not 100% — window-frame overhead under Wine can still clip at exactly 100%). Leave any `config.set('winBounds', ...)` in close handlers alone if other `config.` calls remain.

_Migrated from: wine-electron-app-blank-text-clipped-window, wine-electron-app-under-wine-full-recipe_

## No window but process stays alive (GPU-path issue) — try GE-Proton

**Symptom:** main process plus gpu/utility children stay alive in `ps`, but no window ever maps. Distinct from the 15s-death above (nothing dies).

**Cause:** a wine/ANGLE GPU-path rendering gap in stock wine for some Electron builds.

**Fix:** run under a GE-Proton build vendored into the app dir (don't point at another app's copy):
```bash
mkdir -p "$APPDIR/.ge-proton"
cp -r /path/to/existing/.ge-proton/GE-Proton11-5-x86_64 "$APPDIR/.ge-proton/"
```
Launch script with GE-Proton:
```bash
export WINEPREFIX="$DIR/.pfx"
export PATH="$GEDIR/files/bin:$PATH"
export WINESERVER="$GEDIR/files/bin/wineserver"
export WINEDLLPATH="$GEDIR/files/lib/wine:$GEDIR/files/lib64/wine"
export LD_LIBRARY_PATH="$GEDIR/files/lib:$GEDIR/files/lib64"
```
Re-init the prefix under GE-Proton's own wine binary (mixing builds gives `wine client error:0: version mismatch`); kill all wine/wineserver processes before switching. Note this contradicts the mojo section: try plain wine first, GE-Proton second — which build works depends on the failure mode (IPC handshake vs GPU path).

_Migrated from: wine-electron-app-launcher-desktop-entry_

## Desktop entry and icon for the launcher

**Symptom:** app runs from `launch.sh` but isn't discoverable in SUPER+SPACE / wofi / rofi.

**Fix:** extract the largest true-color frame from the app's bundled `.ico` (`magick app.ico out.png` expands to `out-0.png..N`; `magick identify` each, keep the biggest true-color one) into `~/.local/share/icons/hicolor/256x256/apps/appname.png`, then write `~/.local/share/applications/AppName.desktop`:
```ini
[Desktop Entry]
Type=Application
Name=App Name
Exec=/absolute/path/to/launch.sh %f
Icon=appname
Terminal=false
Categories=Education;Science;
StartupWMClass=app.exe
```
Then `update-desktop-database ~/.local/share/applications` and `desktop-file-validate` it. No reboot needed.

_Migrated from: wine-electron-app-launcher-desktop-entry_

## Verification toolbox

- `hyprctl clients -j` + `grim -g "<x>,<y> <WxH>" out.png`, then view the PNG — ground truth for text/clipping without guessing from logs. Beware same-titled unrelated windows (e.g. a file manager on a same-named folder).
- `coredumpctl list` — empty means clean self-exit, not SIGSEGV/SIGABRT.
- `ps -eo pid,cmd | grep '[p]attern'` snapshots over time, not `kill -0 <pid>` (PID reuse gives false "alive") and not single `grep -c` counts across Electron's multi-process tree.

_Migrated from: wine-electron-app-blank-text-clipped-window, wine-electron-app-launch-recipe, wine-electron-app-under-wine-full-recipe_
