---
name: wine-hardware-registry-vm-detection-bypass
description: "Use when a Windows app under Wine/Proton shows a \"can't run in a virtual machine\" (or similar anti-VM/environment-integrity) message, or when populating HKLM\\HARDWARE registry values (SecurityProviders, VideoBiosVersion, SystemBiosVersion, SCSI device map) under Wine to defeat hardware-fingerprint checks. Also covers the general technique of using WINEDEBUG=+relay to ground-truth trace exactly which registry/API call an app's detection logic reads, instead of guessing."
---

## Diagnosing anti-VM / hardware-fingerprint checks under Wine

### Ground-truth tracing (don't guess — trace)
1. Reproduce with `WINEDEBUG=+relay wine ./app.exe [real-args] > trace.log 2>&1`. This produces millions of lines but is searchable.
2. Find the trigger call (e.g. `grep -n "MessageBoxA(" trace.log`) — the printed string args show the exact message.
3. Walk backward on the SAME thread ID (`awk 'NR<=<line> && $0 ~ /^<tid>:/' trace.log`) through `RegOpenKeyExA/W`, `RegQueryValueExA/W`, `DeviceIoControl`, WMI `ExecQuery`/`CoCreateInstance` calls. Check each `Ret ... retval=` — `00000002` / `c0000034` (`STATUS_OBJECT_NAME_NOT_FOUND`) means "not found", which is the fingerprint gap.
4. The `ret=<addr>` field on the failing/triggering API call is the return address INTO the app's own code. Cross-reference against `/proc/<pid>/maps` (while the process is still alive, e.g. sitting at a dialog) to find which module (or an anonymous RWX region = JIT'd/packed code) contains it.

### HKLM\HARDWARE is VOLATILE and gets wiped every top-level `wine` invocation
- `reg add` to `HKLM\HARDWARE\DESCRIPTION\System\...` or `HKLM\HARDWARE\DEVICEMAP\...` appears to succeed but is **gone** on the next `wine <exe>` call — winedevice/plugplay regenerates it fresh per top-level wine process launch (not per child process).
- Fix: chain the `reg add` fixes and the target app launch in **one single top-level `wine cmd /c script.bat`** invocation so nothing regenerates HARDWARE in between. Use a `.bat` file (not inline `cmd /c "..."` — nested quoting through bash → wine → cmd breaks badly with spaces/backslashes).
- `cd` inside a `.bat` does NOT switch drives (we're on `Z:` mapped to the Linux cwd; target is `C:`) — use `cd /d "C:\path"`, not plain `cd`.

### `HKLM\HARDWARE\DEVICEMAP\...` subkeys reject plain `reg add`
- `reg add "HKLM\HARDWARE\DEVICEMAP\Scsi\Scsi Port 1\..."` fails with "Unable to access or create the specified registry key" — NOT an ACL/privilege issue, it's `STATUS_CHILD_MUST_BE_VOLATILE`: you cannot create a non-volatile subkey under a volatile parent, and `reg.exe` has no CLI flag for `REG_OPTION_VOLATILE`.
- Fix: write a tiny native helper (`RegCreateKeyExA(..., REG_OPTION_VOLATILE, ...)`), compile with `x86_64-w64-mingw32-gcc`, run it as one of the chained `.bat` steps. Multi-word registry paths (e.g. "Scsi Port 1") must be passed via a `.bat` file, not inline `cmd /c` args (argv splitting on spaces breaks through nested shells).

```c
// volkey.c — creates/opens a REG_OPTION_VOLATILE key and optionally sets one REG_SZ value
#include <windows.h>
#include <stdio.h>
int main(int argc, char **argv) {
    if (argc < 2) { printf("usage: volkey.exe KeyPath [ValueName ValueData]\n"); return 1; }
    HKEY hKey; DWORD disp;
    LSTATUS st = RegCreateKeyExA(HKEY_LOCAL_MACHINE, argv[1], 0, NULL,
        REG_OPTION_VOLATILE, KEY_ALL_ACCESS, NULL, &hKey, &disp);
    if (st != ERROR_SUCCESS) { printf("RegCreateKeyExA failed: %ld\n", st); return 1; }
    if (argc >= 4) RegSetValueExA(hKey, argv[2], 0, REG_SZ, (const BYTE*)argv[3], strlen(argv[3])+1);
    RegCloseKey(hKey);
    return 0;
}
```

### Common missing values apps check as VM-fingerprint signals under Wine (all absent by default)
- `HKLM\SYSTEM\CurrentControlSet\Control\SecurityProviders\SecurityProviders` (REG_SZ) — persists normally (SYSTEM hive, not volatile).
- `HKLM\HARDWARE\DESCRIPTION\System\VideoBiosVersion` and `\SystemBiosVersion` (REG_MULTI_SZ) — directly on `\System`, NOT `\System\BIOS`. Verify via relay trace which exact subkey handle the app queries — apps vary.
- `HKLM\HARDWARE\DEVICEMAP\Scsi\Scsi Port <N>` value `Driver` (REG_SZ, e.g. `"nvme"`), plus nested `Scsi Bus 0\Target Id 0\Logical Unit Id 0\Identifier`/`Type` — needs the volatile-key helper above.

### When registry fixes don't resolve it: check for packed/JIT'd code
If `/proc/<pid>/maps` shows the triggering return address inside an anonymous RWX region (no backing file), the check is in dynamically-generated code (V8 JS JIT if the app embeds CEF/Chromium, or a commercial anti-tamper packer's unpacked payload). `gdb` breakpoints on the plain `user32.dll!MessageBoxA/W` export address often silently fail to fire in this case (packer hooks/obfuscates the call) — this is a strong signal you've hit a genuinely packed/obfuscated check, not a plain registry gap. Further progress requires real unpacking/anti-anti-debug work, materially more effort than registry patching.

### CEF/Chromium-embedded apps and GPU fallback (dead end observed once, note for next time)
If the app bundles `vk_swiftshader.dll`/`libEGL.dll`/`d3dcompiler_47.dll` (ANGLE + SwiftShader), suspect WebGL/GPU-fingerprint as the signal and try installing GE-Proton's DXVK `d3d11.dll`/`d3d10core.dll`/`dxgi.dll` (from `<GE-Proton>/files/lib/wine/dxvk/{x86_64,i386}-windows/`) into `system32`/`syswow64` with `HKCU\Software\Wine\DllOverrides` set to `native`. Verify effect by checking `/proc/<pid>/maps` for `vulkan`/`libGL` `.so` entries — if NONE load even after this, the app isn't attempting GPU init at all (rules out GPU/WebGL fingerprint as the mechanism; don't waste more time on the DXVK angle in that case).
