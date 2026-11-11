# WebView2 and Tauri apps under Wine

Embedded WebView2/Edge-WebView apps (installer-based .NET/WinForms/WPF, Tauri/wry) under Wine: the ole32/WinRT crash, missing `input.dll`, and the WebView2 registry-hive gap. Anti-VM silent exits are deliberately out of scope.

## ole32 page fault at startup — switch to GE-Proton

**Symptom:** deterministic crash every launch at the same instruction offset:
```
wine: Unhandled page fault on read access ... at address ...191a8 (in ole32)
Backtrace:
 0 ole32 (+0x391a8)
 1 <app>.exe (+...)
 2 <app>.exe (+...)
 3 user32 ...
```

**Cause:** vanilla Wine's `ole32`/`combase` WinRT gap (`RoGetActivationFactory`-adjacent code hit during WebView2 hosting/drag-drop init, e.g. `RegisterDragDrop`/`CoLockObjectExternal`). Unrelated to missing files — the app usually bundles its own WebView2 copy under `Program Files (x86)\Microsoft\EdgeWebView\Application\<ver>\`.

**Fix:** drop-in binary swap to GE-Proton (wine-staging with extra COM/WinRT patches); reuse the same `WINEPREFIX`, no reinstall:
```bash
curl -s https://api.github.com/repos/GloriousEggroll/proton-ge-custom/releases/latest \
  | grep -E '"browser_download_url".*tar.gz"' | grep x86_64 | cut -d'"' -f4
mkdir -p .ge-proton && cd .ge-proton
curl -sL -o ge.tar.gz "<url from above>"
tar xzf ge.tar.gz && rm ge.tar.gz
```
```bash
GEDIR="$DIR/.ge-proton/GE-Proton<ver>-x86_64"
export WINEPREFIX="$DIR/.pfx"
export PATH="$GEDIR/files/bin:$PATH"
export WINESERVER="$GEDIR/files/bin/wineserver"
export WINEDLLPATH="$GEDIR/files/lib/wine:$GEDIR/files/lib64/wine"
export LD_LIBRARY_PATH="$GEDIR/files/lib:$GEDIR/files/lib64"
wine "$WINEPREFIX/drive_c/Program Files/<App>/<App>.exe"
```
GE-Proton's `files/bin` ships only `wine` (no `wine64`) — use `wine` even for 64-bit prefixes. Kill stray wineservers from the old build first (`pkill -9 -f wineserver; pkill -9 -f winedevice`) — a running wineserver pins the prefix to whichever build started it.

Did NOT fix it (don't retry): standalone WebView2 Evergreen Runtime install (`https://go.microsoft.com/fwlink/p/?LinkId=2124703`, `wine webview2setup.exe /silent /install`), `winetricks vcrun2022 corefonts gdiplus`, `winecfg /v win7`.

_Migrated from: wine-webview2-ole32-winrt-crash-geproton-fix, wine-webview2-tauri-app-crash-fixes_

## Missing input.dll (Tauri/wry)

**Symptom:** `err:module:import_dll Library input.dll (which is needed by ...) not found` / `loader_init failed, status c0000135`.

**Cause:** `input.dll` is a real Windows 10+ TSF/text-input DLL Wine does not ship. Check actual imports first: `winedump -j import <app>.exe | grep -A5 input.dll` — often only one or two harmless exports are referenced.

**Fix:** build a stub PE DLL with mingw-w64-gcc (NOT `winegcc -shared`, which produces a `.dll.so` unixlib hybrid the PE loader in wine-staging 11.x won't resolve):
```bash
sudo pacman -S mingw-w64-gcc
cat > input.c <<'EOF'
#include <windows.h>
typedef struct { LANGID langid; CLSID clsid; GUID guidProfile; } LAYOUTORTIPPROFILE;
__declspec(dllexport) HRESULT WINAPI EnumEnabledLayoutOrTip(
    LPCWSTR pszUserReg, LPCWSTR pszSystemReg, LPCWSTR pszSoftwareReg,
    LAYOUTORTIPPROFILE *pLayoutOrTipProfile, UINT uBufLength, UINT *pFetched)
{ if (pFetched) *pFetched = 0; return S_OK; }
EOF
cat > input.def <<'EOF'
LIBRARY input.dll
EXPORTS
    EnumEnabledLayoutOrTip
EOF
x86_64-w64-mingw32-gcc -shared -o input.dll input.c input.def -Wl,--kill-at
file input.dll   # must say "PE32+ executable ... DLL", not ELF
cp input.dll "$WINEPREFIX/drive_c/windows/system32/input.dll"
```
x64 uses a uniform register-based calling convention, so signature mismatches in a stub are safe as long as the export name matches.

_Migrated from: wine-webview2-tauri-app-crash-fixes_

## WebView2 Evergreen installed but "not found" (WOW6432Node hive gap)

**Symptom:** runtime installed via `webview2setup.exe /silent /install`, app still reports it missing.

**Cause:** the client GUID key `{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}` lands under `HKLM\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\` but not the native 64-bit hive, which a 64-bit WebView2 loader (e.g. Tauri/wry `webview2-com`) checks.

**Fix:** mirror the values into the native path:
```bash
KEY='HKLM\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
wine reg add "$KEY" /v location /t REG_SZ /d "C:\Program Files (x86)\Microsoft\EdgeWebView\Application" /f
wine reg add "$KEY" /v name /t REG_SZ /d "Microsoft Edge WebView2 Runtime" /f
wine reg add "$KEY" /v pv /t REG_SZ /d "<version, e.g. 151.0.4129.107>" /f
```

_Migrated from: wine-webview2-tauri-app-crash-fixes_

## Detached launch script

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
`setsid` + stdio to `/dev/null` + `disown` survives terminal close. Verify with `pgrep -fa <App>.exe`.

_Migrated from: wine-webview2-ole32-winrt-crash-geproton-fix_

## Silent clean exit after full init — intentional anti-VM, stop here

**Symptom:** UI init proceeds normally (`uxtheme`/`uiautomation` fixmes fire, companion service subprocess may spawn and log), then the main process exits cleanly — code 101 with a clean `PROCESS_DETACH` sequence, or code 0 via `LdrUnloadDll` ~5-10s after load — no window, zero panic text even under `WINEDEBUG=+module,+loaddll` and `RUST_BACKTRACE=full`.

**Cause:** intentional anti-virtualization/environment-integrity detection (common in exam-lockdown/proctoring software), not a compatibility bug. Confirmed case: Respondus LockDown Browser installs cleanly under vanilla Wine + winetricks (`msftedit`) per the VT LUUG wiki recipe, then self-terminates ~7s after launch, exit 0 — matching the vendor's own "can't be used in virtual machine software" behavior.

**Fix:** none — defeating it means spoofing CPUID/hardware fingerprints or hex-patching the check, i.e. defeating a deliberate security control. Recommend a real Windows install or contacting the instructor/proctor instead.

_Migrated from: wine-webview2-tauri-app-crash-fixes_

## Debugging gotchas

- `sudo -n` fails on fingerprint-auth machines; use a real PTY for the fingerprint prompt when installing `wine`/`winetricks`.
- `winetricks ... corefonts` can hang forever on `wineserver -w` if a sub-installer (e.g. `andale32.exe`) crashes and spawns headless `winedbg --auto` waiting on a crash dialog. Prevent: `wine reg add "HKCU\Software\Wine\WineDbg" /v ShowCrashDialog /t REG_DWORD /d 0 /f`; unstick: `pkill -9 -f winedbg`.
- Long installers (winetricks, msiexec, GE-Proton downloads) outlive foreground-call timeouts, which kill the whole process group on timeout — run via `nohup ... & disown` and poll with short `sleep N; pgrep ...` checks.

_Migrated from: wine-webview2-ole32-winrt-crash-geproton-fix_
