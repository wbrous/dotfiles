---
name: wine-webview2-ole32-winrt-crash-geproton-fix
description: "Use when a Windows app with an embedded WebView2/Edge WebView control (e.g. installer-based .NET/WinForms/WPF apps) crashes under vanilla Wine with \"Unhandled page fault ... in ole32\" during startup, with a backtrace through user32 - app - ole32, especially reproducible at the exact same instruction offset every launch. Also covers detached-from-terminal launch scripts for wine apps."
---

## Symptom
App built with an embedded WebView2/Chromium Edge WebView (bundled under `Program Files (x86)\Microsoft\EdgeWebView\Application\<ver>\`) reliably crashes on launch under vanilla Wine:

```
wine: Unhandled page fault on read access ... at address ...191a8 (in ole32)
Backtrace:
 0 ole32 (+0x391a8)
 1 <app>.exe (+...)
 2 <app>.exe (+...)
 3 user32 ...
```

Same crash address every run — deterministic, not a race.

## Root cause
Vanilla Wine's `ole32`/`combase` has a WinRT gap: calls like `RoGetActivationFactory` (used internally by WebView2 hosting/drag-drop init, e.g. `RegisterDragDrop`/`CoLockObjectExternal` on WinRT-backed objects) aren't fully implemented. This is unrelated to missing files — the app already bundles its own WebView2 runtime copy.

## What did NOT fix it
- Installing the standalone Microsoft Edge WebView2 Evergreen Runtime (`https://go.microsoft.com/fwlink/p/?LinkId=2124703`, run `wine webview2setup.exe /silent /install`) — app uses its own bundled copy regardless.
- `winetricks vcrun2022 corefonts gdiplus` — vcrun2022 is good practice generally but didn't touch this bug.
- `winecfg /v win7` (forcing Windows 7 compat mode) — didn't change the crash.

## What DID fix it
Swap the Wine build for **GE-Proton** (GloriousEggroll/proton-ge-custom), which ships a wine-staging build with extra COM/WinRT patches. Same existing `WINEPREFIX` works unmodified — no prefix rebuild needed.

```bash
# Fetch latest GE-Proton release URL
curl -s https://api.github.com/repos/GloriousEggroll/proton-ge-custom/releases/latest \
  | grep -E '"browser_download_url".*tar.gz"' | grep x86_64 | cut -d'"' -f4

# Download + extract (~530MB)
mkdir -p .ge-proton && cd .ge-proton
curl -sL -o ge.tar.gz "<url from above>"
tar xzf ge.tar.gz && rm ge.tar.gz
# -> .ge-proton/GE-Proton<ver>-x86_64/files/bin/{wine,wineserver,msidb,xrandr}
```

Run/launch with env pointed at the GE-Proton build instead of system wine:

```bash
GEDIR="$DIR/.ge-proton/GE-Proton<ver>-x86_64"
export WINEPREFIX="$DIR/.pfx"                 # existing prefix, unchanged
export PATH="$GEDIR/files/bin:$PATH"
export WINESERVER="$GEDIR/files/bin/wineserver"
export WINEDLLPATH="$GEDIR/files/lib/wine:$GEDIR/files/lib64/wine"
export LD_LIBRARY_PATH="$GEDIR/files/lib:$GEDIR/files/lib64"
wine "$WINEPREFIX/drive_c/Program Files/<App>/<App>.exe"
```

Note: GE-Proton's `files/bin` only ships `wine` (not `wine64`) — use `wine` directly, it's the 64-bit build.

Before switching, kill any stray wineserver from the old build (`pkill -9 -f wineserver; pkill -9 -f winedevice`) — a running wineserver pins the prefix to whichever wine build started it.

## Detached launch script (survives closing the terminal)
```bash
#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GEDIR="$DIR/.ge-proton/GE-Proton<ver>-x86_64"
export WINEPREFIX="$DIR/.pfx"
export PATH="$GEDIR/files/bin:$PATH"
export WINESERVER="$GEDIR/files/bin/wineserver"
export WINEDLLPATH="$GEDIR/files/lib/wine:$GEDIR/files/lib64/wine"
export LD_LIBRARY_PATH="$GEDIR/files/lib:$GEDIR/files/lib64"

setsid nohup wine "$WINEPREFIX/drive_c/Program Files/<App>/<App>.exe" \
  >/dev/null 2>&1 < /dev/null &
disown
echo "Launched (detached, pid $!)."
```
Key points: `setsid` gives a new session (immune to terminal HUP), stdio redirected to `/dev/null`, `disown` drops shell job control. Verify with `pgrep -fa <App>.exe` after closing/backgrounding the terminal.

## Debugging gotchas hit along the way
- `sudo -n` fails on fingerprint-auth machines; use the `sudo-interactive-tty-via-hub` skill (hub `start` with a real PTY) to get past the fingerprint prompt for `pacman -S wine winetricks`.
- `winetricks ... corefonts` can hang forever on `wineserver -w` if a triggered sub-installer (e.g. `andale32.exe`) itself crashes and spawns `winedbg --auto` — headless, no display, hangs indefinitely waiting for a crash-dialog interaction that never comes. Fix/prevent: `wine reg add "HKCU\Software\Wine\WineDbg" /v ShowCrashDialog /t REG_DWORD /d 0 /f` before running winetricks, and `pkill -9 -f winedbg` to unstick an already-hung run.
- Foreground bash tool calls with a timeout will kill the whole process group on timeout — long-running installers (winetricks, msiexec, GE-Proton downloads) should be run via `nohup ... & disown` and polled with short `sleep N; pgrep ...` checks instead of one long blocking foreground call.
