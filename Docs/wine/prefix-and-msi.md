# Wine prefixes, MSI installs, and stub-DLL shims

Creating a project-local Wine prefix, silently installing an `.msi` into it, and fixing apps that crash on unimplemented Wine DLL stubs (e.g. `powrprof.dll`).

## Creating a prefix and silent-installing an MSI

**Symptom:** need a fresh project-scoped prefix (e.g. `.pfx`) with an `.msi` installed on Arch.

**Fix:**
```bash
sudo pacman -S --noconfirm wine winetricks
export WINEPREFIX="$(pwd)/.pfx"
export WINEARCH=win64
wineboot --init
```
`wineboot --init` prints `err:ole:`, `fixme:`, `err:setupapi:do_file_copyW Unsupported style(s) 0x10` noise — normal boilerplate; exit code 0 means success.
```bash
msiexec /i "$(pwd)/App.msi" /qn /l*v "$(pwd)/install.log"
```
Large MSIs (e.g. bundling Edge WebView runtime) can outrun a ~180s foreground-call timeout — the tool reports "timed out" but msiexec frequently already finished. **Never treat the timeout as failure; verify:**
1. `pgrep -fa msiexec` — empty means it exited.
2. Tail `install.log`: `Action ended ...: INSTALL. Return value 1.` with no `error:`/`Installation failed` nearby.
3. `find "$WINEPREFIX/drive_c/Program Files"* -iname "*<app>*"` confirms binaries landed.

Launch: `WINEPREFIX="$(pwd)/.pfx" wine "$(pwd)/.pfx/drive_c/Program Files/<App>/<App>.exe"`.

_Migrated from: wine-prefix-msi-silent-install_

## Tracing a silent-exit crash to a stub DLL

**Symptom:** Windows binary (often Rust-built; common in exam-lockdown/kiosk software) exits ~101 shortly after launch, no dialog, no useful stderr.

**Cause pattern:** Wine's `powrprof.dll` is largely a stub — `PowerGetActiveScheme` (plus `PowerSetActiveScheme`, `PowerReadACValueIndex`) returns `ERROR_CALL_NOT_IMPLEMENTED` (`0x80070078` as HRESULT); the app unwraps/panics.

**Fix — diagnosis:**
```bash
WINEDEBUG=+relay,+seh wine ./app.exe > relay.log 2>&1
grep -aiE "panicked|panic|exit_process|TerminateProcess|RaiseException" relay.log | tail -40
```
Walk backwards from that line for the last meaningful call — `GetErrorInfo`, `FormatMessageW(0x8007...)`, or `Ret <module>.<Func>() retval=<nonzero HRESULT>`. Confirm the export is a genuine stub by disassembling Wine's own DLL — a one- or two-instruction constant-return is the giveaway.

_Migrated from: wine-powrprof-stub-crash-fix_

## Building and installing a native stub-DLL shim

Wine's DLL search order lets a file in `drive_c/windows/system32/` (or `syswow64` for 32-bit) override the builtin, if it's a valid native PE DLL — set `HKCU\Software\Wine\DllOverrides` to `native` for that name if needed.

1. Minimal C source implementing only the needed exports as always-succeeding stubs:
```c
#include <windows.h>
#include <winnt.h>
#include <powrprof.h>
BOOL WINAPI PowerGetActiveScheme(HKEY UserRootPowerKey, GUID **ActivePolicyGuid) {
    static const GUID BalancedGuid = {0x381b4222, 0xf694, 0x41f0, {0x9,0x85,0xff,0x0,0x0,0x63,0x51,0x6a}};
    *ActivePolicyGuid = CoTaskMemAlloc(sizeof(GUID));
    *(*ActivePolicyGuid) = BalancedGuid;
    return TRUE;
}
BOOL WINAPI DllMain(HINSTANCE h, DWORD reason, LPVOID reserved) { return TRUE; }
```
2. Matching `.def` listing every export the app might touch (missing exports fail import resolution loudly — easier to fix than a silent panic).
3. Cross-compile matching the app's bitness (`pacman -S mingw-w64-gcc` if missing):
```
i686-w64-mingw32-gcc -shared -O2 -o mystub.dll stub.c mystub.def -Wl,--kill-at
# or x86_64-w64-mingw32-gcc for 64-bit apps
```
4. Install and override:
```
cp mystub.dll "$WINEPREFIX/drive_c/windows/system32/powrprof.dll"
wine reg add "HKCU\Software\Wine\DllOverrides" /v powrprof /d native /f
```
5. Relaunch; re-verify via relay trace / process-alive check.

Gotchas: always confirm via the `GetErrorInfo`/`FormatMessageW(0x8007...)` pattern before writing a shim — missing-`input.dll` and missing-WebView2 crashes look similar but need different fixes. And don't conflate "crashes on unimplemented API" (shim-fixable) with "deliberately refuses Wine/VM" (anti-VM — use a real machine instead).

_Migrated from: wine-powrprof-stub-crash-fix_
