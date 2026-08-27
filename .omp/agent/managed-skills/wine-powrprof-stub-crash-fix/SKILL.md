---
name: wine-powrprof-stub-crash-fix
description: "Use when a Windows app under Wine/Proton crashes with a Rust panic or \"not implemented\" error immediately after calling into power management APIs (PowerGetActiveScheme, PowerReadACValueIndex, etc.), especially exam-lockdown/kiosk software like Digiexam that self-terminates on any unsupported API. Also covers the general recipe for tracing a Wine app crash to a specific stub DLL via WINEDEBUG=+relay and building a minimal replacement DLL."
---

## Symptom
A Windows binary running under Wine (including Proton/GE-Proton builds) exits with code 101 (or similar) shortly after launch, no visible crash dialog, no useful stderr — just a silent self-terminate. Common in Rust-built Windows apps (panics on `Result::unwrap()` of a failed WinAPI call) and especially in exam-lockdown/kiosk/proctoring software that treats any unexpected API failure as a security violation.

## Root cause pattern
Wine's `powrprof.dll` is largely a stub: `PowerGetActiveScheme` (and siblings like `PowerSetActiveScheme`, `PowerReadACValueIndex`) return `ERROR_CALL_NOT_IMPLEMENTED` (`0x80070078` as an HRESULT) instead of succeeding. Apps that call `GetErrorInfo` → `FormatMessageW(0x80070078)` right before raising an exception/panicking are hitting this exact stub.

## Diagnosis recipe
1. Reproduce with full relay tracing to a log file (expect huge output, tail/grep it):
   ```
   WINEDEBUG=+relay,+seh wine ./app.exe > relay.log 2>&1
   ```
2. Find the panic/exit point:
   ```
   grep -aiE "panicked|panic|exit_process|TerminateProcess|RaiseException" relay.log | tail -40
   ```
3. Walk backwards from that line (`sed -n 'STARTLINE,ENDLINEp' relay.log`) looking for the last meaningful WinAPI call before the unwind/exit — specifically look for `GetErrorInfo`, `FormatMessageW(0x8007...)`, or any `Ret <module>.<Func>() retval=<nonzero HRESULT-looking value>`.
4. Confirm the culprit function is a genuine Wine stub by checking its export and disassembling the wine build's own `powrprof.dll`/whatever module — a one- or two-instruction function that just returns a constant is the giveaway.

## Fix: build and install a native stub DLL shim
Wine's DLL search order lets a file dropped directly into `drive_c/windows/system32/` (or syswow64 for 32-bit) override the wine-builtin version, IF it's a valid native PE DLL (not diverted by Wine's own builtin-override list — check/set `HKCU\Software\Wine\DllOverrides` to `native` for that DLL name if needed).

1. Write a minimal C source implementing only the needed exports as always-succeeding stubs, e.g.:
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
   /* stub any other called-but-unimplemented exports similarly, returning TRUE/success */
   BOOL WINAPI DllMain(HINSTANCE h, DWORD reason, LPVOID reserved) { return TRUE; }
   ```
2. Write a matching `.def` file listing every export the real DLL has that the app might touch (missing exports the app calls will just fail import resolution loudly, which is easier to fix than a silent panic).
3. Cross-compile with the mingw-w64 toolchain matching the app's bitness:
   ```
   i686-w64-mingw32-gcc -shared -O2 -o mystub.dll stub.c mystub.def -Wl,--kill-at
   # or x86_64-w64-mingw32-gcc for 64-bit apps
   ```
   Install `mingw-w64-gcc` via pacman if missing (may need to kill/restart a stuck prior pacman invocation via `hub op=stop` + fresh `hub op=start` if a sudo pty install seems to hang on a queued/skipped user message).
4. Copy the built DLL into the prefix's system32/syswow64 (matching bitness) and set the override:
   ```
   cp mystub.dll "$WINEPREFIX/drive_c/windows/system32/powrprof.dll"
   wine reg add "HKCU\Software\Wine\DllOverrides" /v powrprof /d native /f
   ```
5. Relaunch the app and re-verify via relay trace / process-alive check that it no longer panics.

## Gotchas
- Don't guess at the panic cause from a single log line — always confirm via the `GetErrorInfo`/`FormatMessageW(0x8007...)` pattern or an explicit stub-returning-error before committing to writing a shim; other panics (e.g. missing `input.dll` TSF export, WebView2 runtime not installed) look superficially similar but need different fixes.
- `HKLM\HARDWARE\...` is a **volatile** Wine registry hive — never persisted to `system.reg`/`user.reg`, regenerated fresh by winedevice/plugplay on every wineserver start. `wine reg add` writes to it are immediately lost across wine invocations. Do NOT try to "fix" VM-detection-style checks that read `HKLM\HARDWARE\DESCRIPTION\System` or `HKLM\HARDWARE\DEVICEMAP\Scsi` this way — it will appear to succeed (`reg add` reports success) but never actually take effect.
- Genuine anti-cheat/anti-VM checks (e.g., proctoring/exam-lockdown browsers checking for VM artifacts, checking WSC/AV product registration, etc.) are a different problem class from stub-DLL crashes — don't conflate "app crashes because Wine doesn't implement an API" (fixable via stub shim) with "app deliberately detects and refuses to run under Wine/Proton/VM" (a losing battle to patch around; use a real VM via `virt-manager`/libvirt instead if you actually need that software to run).
