---
name: wine-launch-script-plain-electron-exe
description: "Use when creating a launch script for a standalone/unzipped Windows Electron-based .exe app (e.g. GeoGebra.exe) under Wine on Linux, with no installer needed and no anti-cheat/anti-VM checks — covers the minimal wineboot --init + detached wine launch pattern, as opposed to the heavier GE-Proton + WEBVIEW2 setup needed for kiosk/exam-lockdown apps like Digiexam."
---

## When to use
App ships as a raw unzipped Windows folder (e.g. `~/Applications/<App>/<App>.exe` plus DLLs, no `.msi` installer) and is a normal Electron/Chromium app (no anti-VM/anti-cheat, no WebView2 hard requirement). Plain system `wine` is sufficient — do NOT reach for GE-Proton or a WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS workaround unless the app actually needs it (see wine-webview2-tauri-app-crash-fixes / wine-prefix-msi-silent-install skills for that heavier case, e.g. Digiexam/LockdownBrowser).

## Steps
1. Create a prefix scoped to the app dir (keeps it self-contained, deletable):
   ```
   cd ~/Applications/<App>
   WINEPREFIX="$PWD/.pfx" WINEDEBUG=-all wineboot --init >/tmp/wineboot.log 2>&1 &
   disown
   ```
   Poll for `.pfx/system.reg` to appear (wineboot runs async) rather than blocking — avoids bash tool timeout.

2. Write `launch.sh` in the app dir:
   ```bash
   #!/usr/bin/env bash
   set -euo pipefail

   DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

   export WINEPREFIX="$DIR/.pfx"
   export WINEDEBUG="${WINEDEBUG:--all}"

   setsid nohup wine "$DIR/<App>.exe" "$@" \
     >/dev/null 2>&1 < /dev/null &
   disown

   echo "<App> launched (detached, pid $!)."
   ```
   `chmod +x launch.sh`. `setsid nohup ... & disown` fully detaches so the launcher can exit without killing the app or leaving it as a job of the calling shell.

3. Smoke test: run `./launch.sh`, then `ps aux | grep -i <exe-name>` to confirm the main process plus Electron's `--type=gpu-process` / `--type=utility` children spawned (proof the app didn't crash on startup). Kill with `pkill -f "<App>.exe"` after verifying.

## Why not GE-Proton here
GE-Proton + custom WEBVIEW2 args + wine-staging is only needed when the app embeds a real WebView2/CEF control that vanilla Wine's ole32/combase WinRT gap breaks (see wine-webview2-* skills), or when the app does anti-VM detection requiring registry/hardware spoofing. A plain Electron app bundles its own Chromium and doesn't hit that gap — vanilla `wine` on a freshly booted prefix works.
