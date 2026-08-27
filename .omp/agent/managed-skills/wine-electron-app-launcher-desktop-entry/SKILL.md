---
name: wine-electron-app-launcher-desktop-entry
description: "Use when packaging a standalone Windows Electron .exe (e.g. GeoGebra.exe) to run under Wine on Linux, wiring a detached launch.sh, and/or making it discoverable in app launchers (Omarchy SUPER+SPACE, wofi, rofi, etc.) via a ~/.local/share/applications/*.desktop entry plus an icon extracted from the app's own bundled .ico. Also covers the symptom where the process starts and stays alive (visible in ps/GPU+network subprocesses spawn) but no window ever appears — often fixed by running under a vendored GE-Proton build instead of the system wine package."
---

## Minimal launch.sh (plain wine — try first)

```bash
#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export WINEPREFIX="$DIR/.pfx"
export WINEDEBUG="${WINEDEBUG:--all}"
setsid nohup wine "$DIR/App.exe" "$@" >/dev/null 2>&1 < /dev/null &
disown
echo "App launched (detached, pid $!)."
```

Init prefix once: `WINEPREFIX="$DIR/.pfx" wineboot --init`.

## Symptom: process runs, no window (silent no-op)

Plain system wine (e.g. wine-11.15) can start an Electron app's main process — it
even spawns the expected `--type=gpu-process` / `--type=utility` child processes
visible in `ps` — but never maps a window. No crash, no error in stdout/stderr.
This is a wine/ANGLE GPU-path rendering issue, not an app bug.

**Fix: run it under GE-Proton instead of system wine.** GE-Proton's bundled wine
build (dxvk/vkd3d/wine-staging patches) renders the Electron window correctly
where stock wine silently fails.

Confirm root cause and fix by checking `hyprctl clients` (or `wmctrl -l`) for a
mapped/visible window with the app's title — absence with plain wine, presence
after switching to GE-Proton, confirms this exact failure mode.

### Vendoring GE-Proton into the app's own launch dir

Don't point the launch script at another app's `.ge-proton` copy — vendor it so
the launcher survives that other app being removed:

```bash
mkdir -p "$APPDIR/.ge-proton"
cp -r /path/to/existing/.ge-proton/GE-Proton11-5-x86_64 "$APPDIR/.ge-proton/"
```

(~1.5GB copy; reuse an already-downloaded GE-Proton release dir as the source
instead of re-downloading — check `find / -maxdepth 6 -iname "GE-Proton*" -type d`
first. Verify current latest via GitHub releases before reusing an old one.)

launch.sh with GE-Proton:

```bash
#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GEDIR="$DIR/.ge-proton/GE-Proton11-5-x86_64"

export WINEPREFIX="$DIR/.pfx"
export PATH="$GEDIR/files/bin:$PATH"
export WINESERVER="$GEDIR/files/bin/wineserver"
export WINEDLLPATH="$GEDIR/files/lib/wine:$GEDIR/files/lib64/wine"
export LD_LIBRARY_PATH="$GEDIR/files/lib:$GEDIR/files/lib64"
export WINEDEBUG="${WINEDEBUG:--all}"

setsid nohup wine "$DIR/App.exe" "$@" >/dev/null 2>&1 < /dev/null &
disown
echo "App launched (detached, pid $!)."
```

Re-init the prefix under GE-Proton's own wine binary (don't reuse a prefix
created by a different wine build — mixing produces
`wine client error:0: version mismatch N/M` from a stale wineserver of the
wrong version; kill all wine/winedevice/wineserver processes before switching).

## Desktop entry + icon (Omarchy/Hyprland launcher discovery)

Extract an icon from the app's bundled `.ico` (multi-resolution — pick the
largest real color frame, `magick identify` each extracted frame to check for
bogus grayscale duplicates at the "largest" size):

```bash
mkdir -p ~/.local/share/icons/hicolor/256x256/apps
magick /path/to/app/app.ico ~/.local/share/icons/hicolor/256x256/apps/appname.png
# magick expands multi-frame .ico into appname-0.png .. appname-N.png;
# identify each, keep the biggest true-color one, delete the rest, rename it.
```

`.desktop` entry:

```ini
[Desktop Entry]
Type=Application
Name=App Name
Comment=Short description
Exec=/absolute/path/to/launch.sh %f
Icon=appname
Terminal=false
Categories=Education;Science;
StartupWMClass=app.exe
```

Write to `~/.local/share/applications/AppName.desktop`, then
`update-desktop-database ~/.local/share/applications` and
`desktop-file-validate` it. No reboot/relogin needed — standard XDG
desktop-entry dir is picked up automatically by any launcher, including
Omarchy's default SUPER+SPACE launcher.
