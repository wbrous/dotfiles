---
name: wine-webview2-tauri-app-crash-fixes
description: "Use when a Wine-installed Windows app crashes with an \"Unhandled page fault\" deep in ole32 near a WebView2/embedded-browser call stack, or a Tauri/wry-based app fails to import \"input.dll\" or immediately exits with code 101 after starting its own service subprocess. Also covers Respondus LockDown Browser specifically: installs cleanly via wine/winetricks (msftedit) per the VT LUUG wiki recipe, but the main .exe silently self-terminates ~7s after launch (clean module-unload trace, exit 0, no window, no error) due to intentional anti-VM/anti-tamper detection — not a compatibility bug. Covers: vanilla Wine's ole32/combase WinRT gap (fixed by switching to GE-Proton's wine-staging build against the same WINEPREFIX), building a stub input.dll (real Win10 TSF dll, not shipped by Wine) via mingw-w64-gcc when only one harmless export like EnumEnabledLayoutOrTip is needed, registering WebView2 Evergreen runtime under the native 64-bit registry hive (HKLM\\\\SOFTWARE\\\\Microsoft\\\\EdgeUpdate\\\\Clients\\\\{GUID}) in addition to the WOW6432Node one, and recognizing when a silent post-service-spawn exit(101) or clean early exit(0) with zero panic/error output is intentional anti-virtualization/anti-cheat behavior in exam-lockdown/proctoring software (LockDown Browser, Digiexam, etc.) rather than a fixable compatibility bug — defeating it would circumvent a deliberate exam-integrity control, which is out of scope to help with."
---

## Symptom cluster

Installing a Windows desktop app (often Tauri/wry or Electron with embedded WebView2, or a native app that bundles its own private WebView2 copy) into a fresh Wine prefix via `msiexec /i ... /qn`, then launching it, produces one or more of:

1. `wine: Unhandled page fault on read access ... starting debugger` with a backtrace through `user32 -> <app>.exe -> ole32 (+0x391a8 or similar)`, reproducible at the **exact same instruction offset** every launch, regardless of `winecfg /v win7|win10` or installing the WebView2 Evergreen runtime standalone.
2. `err:module:import_dll Library input.dll (which is needed by ...) not found` / `loader_init failed, status c0000135`.
3. App loads past both of the above (UI init, `uxtheme`/`uiautomation` fixmes fire normally, a companion lockdown/kiosk service subprocess spawns and writes logs), then the main process **exits cleanly with code 101** — clean `PROCESS_DETACH` unload sequence, zero panic text even under `WINEDEBUG=+module,+loaddll` and `RUST_BACKTRACE=full`.
4. App (e.g. Respondus LockDown Browser) installs and launches with no page fault, no missing-DLL error, no fixme spam of note — module loads cleanly (`LdrGetDllHandleEx` succeeds, .exe maps fine), then within ~5-10s the main thread does a clean `LdrUnloadDll` and the process **exits with code 0**, no window ever shown. This is a different flavor of the same class of behavior as #3.

## Fix 1: ole32/WinRT page fault → switch to GE-Proton's wine-staging build

Vanilla Wine (even recent, e.g. 11.15) has a WinRT gap in `ole32`/`combase` (`RoGetActivationFactory`-adjacent code) that many WebView2-hosting apps hit during window/drag-drop init. GE-Proton ships a wine-staging build with extra COM/WinRT patches that plug this gap, and it's a drop-in binary swap — reuse the **same existing `WINEPREFIX`**, no reinstall:

```bash
curl -s https://api.github.com/repos/GloriousEggroll/proton-ge-custom/releases/latest \
  | grep -oE '"browser_download_url":\s*"[^"]+x86_64\.tar\.gz"' | cut -d'"' -f4
# download + extract to e.g. ./.ge-proton/GE-Proton*-x86_64/

GEDIR=".../.ge-proton/GE-Proton11-5-x86_64"
export WINEPREFIX=".../.pfx"
export PATH="$GEDIR/files/bin:$PATH"
export WINESERVER="$GEDIR/files/bin/wineserver"
export WINEDLLPATH="$GEDIR/files/lib/wine:$GEDIR/files/lib64/wine"
export LD_LIBRARY_PATH="$GEDIR/files/lib:$GEDIR/files/lib64"
wine --version   # should print "wine-11.0 (Staging)" or similar
```

Note: GE-Proton's `files/bin` only ships `wine` (no separate `wine64`) — use `wine` for 64-bit prefixes too.

## Fix 2: missing input.dll

`input.dll` is a real Windows 10+ system DLL (part of the TSF/text-input-framework stack, exports things like `EnumEnabledLayoutOrTip`) that Wine does not implement and does not ship. If `winedump -j import <app>.exe | grep -A5 input.dll` shows only one or two harmless-looking exports actually referenced, build a stub PE DLL with **mingw-w64-gcc** (NOT `winegcc -shared`, which on modern wine-staging produces an old-style `.dll.so` unixlib hybrid that the PE-based loader in wine-staging 11.x will NOT resolve via plain `input.dll` import lookup):

```bash
sudo pacman -S mingw-w64-gcc   # via hub start (fingerprint auth), not sudo -n

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

x64 uses a uniform calling convention (register-based), so exact parameter-count/signature mismatches in a stub are safe as long as the export name matches — no stdcall name-mangling issues to worry about on Win64.

## Fix 3: WebView2 Evergreen runtime registered but still "not found"

After installing the WebView2 Evergreen runtime (`webview2setup.exe /silent /install`), the client GUID key `{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}` gets written under `HKLM\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\` (32-bit/WOW view) but **not** under the native 64-bit hive `HKLM\SOFTWARE\Microsoft\EdgeUpdate\Clients\`. A 64-bit process's WebView2 loader (e.g. `webview2-com` Rust crate used by Tauri/wry) checks the native hive for a 64-bit process and fails to find the runtime even though it's genuinely installed. Fix by mirroring the same `location`/`name`/`pv` values into the native path:

```bash
KEY='HKLM\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
wine reg add "$KEY" /v location /t REG_SZ /d "C:\Program Files (x86)\Microsoft\EdgeWebView\Application" /f
wine reg add "$KEY" /v name /t REG_SZ /d "Microsoft Edge WebView2 Runtime" /f
wine reg add "$KEY" /v pv /t REG_SZ /d "<version, e.g. 151.0.4129.107>" /f
```

## Non-fix: silent exit (code 101 or code 0) after full/near-full init

If, after applying the above, the app's UI initializes fully (fixmes for `uxtheme`, `uiautomation` etc. fire — real init, not an early crash) — possibly with a companion service subprocess (e.g. a "lockdown"/kiosk service for exam-proctoring or DRM-style software) spawning and writing its own logs — and then the **main process exits cleanly** (code 101, or a clean code-0 `LdrUnloadDll` a few seconds after full module load, no window ever shown) with zero panic/error text even under maximal Wine tracing (`WINEDEBUG=+module,+loaddll,err+all`) and `RUST_BACKTRACE=full` — this is very likely **intentional anti-virtualization/environment-integrity detection**, not a compatibility bug. Exam-lockdown and proctoring software is specifically designed to refuse running under Wine/virtualized environments to prevent tampering.

**Confirmed case: Respondus LockDown Browser.** Installs cleanly under vanilla Wine + winetricks (`msftedit`) following the community-documented recipe (e.g. VT LUUG wiki), creates a `.desktop` launcher, `LockDownBrowserOEM.exe` maps and loads with no errors — but self-terminates ~7s after launch, exit code 0, no window. This matches the product's own documented behavior (Respondus KB: "the browser can't be used in virtual machine software"). The software's own vendor page and community wikis for it explicitly note that circumventing this specifically to use it on a real proctored exam is against academic honor codes at most institutions.

Diagnostic/engineering effort should stop here: further "fixing" would mean defeating a deliberate security control (CPUID/hardware-fingerprint spoofing, hex-patching the anti-VM check, hiding Wine's presence from the app), not solving a Wine compatibility gap — decline to go further into that territory. Recommend a real Windows install (dual-boot or licensed VM the institution explicitly permits) for that class of app instead, or contacting the instructor/proctor for an alternative assessment method.
