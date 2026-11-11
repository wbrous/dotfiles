# Debugging and tracing Wine apps

Techniques for finding what a Windows app under Wine is actually checking or crashing on: relay tracing, volatile-registry pitfalls, ptrace limits, Ghidra on memory dumps, and `.pak` string hunting.

## WINEDEBUG=+relay call tracing (do this first)

**Symptom:** app shows a blocking error dialog (anti-VM, environment-integrity) or dies silently and you need the actual signal.

**Fix:**
```bash
export WINEDEBUG="+relay"
timeout 15 wine ./App.exe args > /tmp/trace.log 2>&1
grep -n "MessageBoxA\|MessageBoxW" /tmp/trace.log
```
- `ret=<addr>` after every call is the caller's return address, free of charge.
- Filter to one Wine thread id (`awk -F: '$1=="0024"' /tmp/trace.log > /tmp/thread.txt`) for a clean serial sequence.
- Scan ~200-500 lines before the fatal call for the last *distinctive* API call (skip `RtlAllocateHeap`/`RtlFreeHeap`/`GetProcessHeap`/`EtwEvent*`/critical-section boilerplate) — WSC AV state, registry queries, SCSI/BIOS reads, `RegOpenKeyExA/W`, `RegQueryValueExA/W`, `DeviceIoControl`, WMI `ExecQuery`/`CoCreateInstance`. `retval=00000002` / `c0000034` (`STATUS_OBJECT_NAME_NOT_FOUND`) means "not found" — the fingerprint gap.
- Cross-reference the `ret=` address against `/proc/<pid>/maps` (while the process sits at the dialog) to find which module — or anonymous RWX region (JIT'd/packed code) — contains it.
- If NO distinctive native call precedes the check, it was likely computed inside V8 from cached JS state — pivot to JS-level debugging, not more tracing.

_Migrated from: wine-cef-anti-tamper-check-tracing, wine-hardware-registry-vm-detection-bypass_

## HKLM\HARDWARE is volatile — chain reg fixes with the launch

**Symptom:** `reg add` to `HKLM\HARDWARE\DESCRIPTION\System\...` or `HKLM\HARDWARE\DEVICEMAP\...` reports success but values are gone on the next `wine <exe>` call.

**Cause:** winedevice/plugplay regenerates the `HKLM\HARDWARE` hive fresh on every top-level `wine` invocation; it is never persisted to `system.reg`/`user.reg`.

**Fix:** chain the `reg add` fixes and the target launch in ONE single top-level `wine cmd /c script.bat` invocation. Use a `.bat` file (not inline `cmd /c "..."` — nested bash→wine→cmd quoting breaks on spaces/backslashes), and `cd /d "C:\path"` (plain `cd` won't switch from the `Z:`-mapped Linux cwd to `C:`).

`HKLM\HARDWARE\DEVICEMAP\...` subkeys additionally reject plain `reg add` ("Unable to access or create the specified registry key") — that's `STATUS_CHILD_MUST_BE_VOLATILE`, not ACLs; `reg.exe` has no `REG_OPTION_VOLATILE` flag. Write a tiny helper, compile with `x86_64-w64-mingw32-gcc`, run it as one of the chained `.bat` steps:
```c
// volkey.c — creates/opens a REG_OPTION_VOLATILE key, optionally sets one REG_SZ
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

_Migrated from: wine-hardware-registry-vm-detection-bypass_

## Common missing values apps fingerprint under Wine

All absent by default; confirm via relay trace which exact subkey the app queries before adding:
- `HKLM\SYSTEM\CurrentControlSet\Control\SecurityProviders\SecurityProviders` (REG_SZ) — persists normally (SYSTEM hive, not volatile).
- `HKLM\HARDWARE\DESCRIPTION\System\VideoBiosVersion` and `\SystemBiosVersion` (REG_MULTI_SZ) — directly on `\System`, NOT `\System\BIOS`.
- `HKLM\HARDWARE\DEVICEMAP\Scsi\Scsi Port <N>` value `Driver` (REG_SZ, e.g. `"nvme"`), plus nested `Scsi Bus 0\Target Id 0\Logical Unit Id 0\Identifier`/`Type` — needs the volatile-key helper above.

If `/proc/<pid>/maps` shows the triggering return address in an anonymous RWX region, the check lives in dynamically-generated code (V8 JIT or a packer's payload) — registry patching won't reach it; that means unpacking/anti-anti-debug work, not more reg keys.

_Migrated from: wine-hardware-registry-vm-detection-bypass_

## gdb breakpoints on Wine PE DLLs are unreliable

**Symptom:** breakpoint (`break *addr` or manual ptrace `PTRACE_POKETEXT` `0xCC`) on a Wine-loaded PE export (e.g. `user32.dll!MessageBoxA`, address verified via PE export table + `/proc/PID/maps` base) never fires although the call demonstrably happens (relay trace logs it). gdb warns `Temporarily disabling breakpoints for unloaded shared library` though the mapping never moved; readback shows the `0xCC` was never written (gdb) or was written but `waitpid()` never reports a stop (manual ptrace) — even for a trivial self-written `MessageBoxA()`-only test binary, ruling out app anti-debug.

**Cause (working theory):** Wine's SEH machinery installs its own SIGTRAP/SIGSEGV handlers, interfering with externally-injected ptrace traps.

**Fix:** don't live-breakpoint; use alternatives:
- `WINEDEBUG=+relay` (+`+seh`) as ground truth for what gets called, with args and return addresses.
- `gdb -p PID` static inspection (`x/Ni`, `/proc/PID/mem`, `dump memory`) on an already-idle process (e.g. blocked in a modal dialog) — only *future-point breakpoints* are broken.
- `kill -STOP`/`kill -CONT` polling on `/proc/PID/maps` for coarse milestones ("stop once user32.dll is mapped"); for short-lived processes, loop `pgrep -f "Exe.exe args"` + `kill -STOP` to freeze instantly, avoiding the attach race.
- Don't retry `catch load`, hardware watchpoints, or `follow-fork-mode` variants — the failure is at trap delivery, not placement. Always verify module-base stability via `/proc/PID/maps` before blaming ASLR.

_Migrated from: wine-gdb-ptrace-breakpoint-unreliable, wine-cef-anti-tamper-check-tracing_

## Reliable export-RVA parsing (don't trust objdump columns)

`objdump -p dll.dll` export listings are NOT reliable RVA sources for scripting. Parse the PE export directory directly:
```python
import struct
with open(path,'rb') as f: data = f.read()
e_lfanew = struct.unpack_from('<I', data, 0x3c)[0]
opt_hdr_off = e_lfanew + 24
export_dir_rva, export_dir_size = struct.unpack_from('<II', data, opt_hdr_off + 96)
num_sections = struct.unpack_from('<H', data, e_lfanew+6)[0]
opt_hdr_size = struct.unpack_from('<H', data, e_lfanew+20)[0]
sec_off = e_lfanew + 24 + opt_hdr_size
sections = []
for i in range(num_sections):
    name = data[sec_off:sec_off+8].rstrip(b'\x00')
    vsize, vaddr, rawsize, rawptr = struct.unpack_from('<IIII', data, sec_off+8)
    sections.append((name, vaddr, vsize, rawptr, rawsize)); sec_off += 40
def rva2off(rva):
    for name, vaddr, vsize, rawptr, rawsize in sections:
        if vaddr <= rva < vaddr+vsize: return rawptr + (rva - vaddr)
exp_off = rva2off(export_dir_rva)
num_funcs, num_names = struct.unpack_from('<II', data, exp_off+20)
addr_table_rva, name_table_rva, ord_table_rva = struct.unpack_from('<III', data, exp_off+28)
addr_off, name_off, ord_off = rva2off(addr_table_rva), rva2off(name_table_rva), rva2off(ord_table_rva)
for i in range(num_names):
    name_rva = struct.unpack_from('<I', data, name_off + i*4)[0]
    noff = rva2off(name_rva)
    name = data[noff:data.index(b'\x00', noff)].decode()
    if name == 'TargetFunc':
        idx = struct.unpack_from('<H', data, ord_off + i*2)[0]
        func_rva = struct.unpack_from('<I', data, addr_off + idx*4)[0]
        print(hex(func_rva))
```
Breakpoint address = `dll_base_from_proc_maps + func_rva`.

_Migrated from: wine-cef-anti-tamper-check-tracing_

## Ghidra headless on memory dumps (Java scripts, bounded disassembly)

Dump a live RWX region:
```bash
cat > /tmp/gdb_dump.cmd <<EOF
dump memory /tmp/dump.bin 0xSTART 0xEND
detach
quit
EOF
gdb -q -batch -x /tmp/gdb_dump.cmd -p $PID
```
- Ghidra 12+: `.py` pre/post-scripts FAIL (`Ghidra was not started with PyGhidra`) under plain `analyzeHeadless`. Write scripts in **Java** (extends `GhidraScript`) — always works with the default launcher.
- Full auto-analysis on raw JIT/obfuscated dumps is slow and error-prone (thousands of `Failed to create function ... contains referring thunk`, hangs in Decompiler Switch Analysis). For one known address, skip it:
```
analyzeHeadless proj Name -import dump.bin -processor x86:LE:32:default -noanalysis \
  -scriptPath /path/to/scripts -preScript RebaseScript.java -postScript DisasmWindow.java
```
preScript does `currentProgram.setImageBase(addr, true)`; postScript calls `disassemble()` over a bounded window and dumps the `Instruction` listing (~20s vs minutes). Note `ReferenceManager.getReferencesTo()` returns a `ReferenceIterator`, not `Reference[]`.
- Launch long Ghidra jobs fully detached (`nohup ... &`, `disown`) — foreground-call timeouts kill them.

_Migrated from: wine-cef-anti-tamper-check-tracing, wine-gdb-ptrace-breakpoint-unreliable_

## Recognizing V8 JIT trampolines (stop disassembling)

Chromium/CEF V8 Sparkplug baseline output signature:
```
MOV EAX,[stack_guard_addr]
XOR EAX,EBP
PUSH addr1
PUSH addr2
RET
```
Generic frame-pointer-free dispatch glue with tail-call trampoline chaining — NOT application logic. The decision (`if`, string literals) lives in `BytecodeArray`/String heap objects elsewhere. Stop disassembling; pivot to:
- Chrome DevTools Protocol (`--remote-debugging-port=N --remote-allow-origins=*`) if the app passes argv through to CEF — check `/proc/PID/cmdline` of the browser subprocess, then `curl localhost:PORT/json/version`. Security-conscious kiosk apps often hardcode CEF's `remote_debugging_port` in C++ and strip the flag — no `curl` connection means blocked at app level.
- Static search of `resources.pak` (v5) gzip streams (see below); if that finds nothing, the strings may be obfuscated/split — search shorter brand tokens, not full sentences.
- If that fails too, only V8 heap/bytecode forensics remain — multi-day specialized work (Ghidra has no V8 bytecode support). Say so plainly.

_Migrated from: wine-cef-anti-tamper-check-tracing_

## Chromium resources.pak v5 parsing (Brotli, not gzip)

DataPack v5 header (all little-endian):
```
uint32 version        (=5)
uint8  encoding        (byte offset 4; 0=BINARY,1=UTF8,2=UTF16 — TEXT encoding, not compression)
[3 bytes padding]
uint16 resource_count  (byte offset 8)
uint16 alias_count     (byte offset 10)
```
then `resource_count + 1` entries of `{ uint16 id; uint32 file_offset }` (6 bytes each, sorted; last is a sentinel). Verify `resource_count`/`alias_count` are small sane numbers and offsets increase monotonically to the file size.

Modern Chromium (~M90+) compresses entries with **Brotli, not gzip** — a `\x1f\x8b\x08` magic scan silently finds nothing. Parse the entry table for exact boundaries, then `brotli -d -c entry.bin` per entry (`pacman -S brotli` if the CLI is missing; the `python3-brotli` module often isn't installed). If a string is still absent after Brotli-decoding every entry plus raw ASCII and UTF-16LE search of exe/DLLs (including short 6-10 char fragments), it's constructed dynamically at runtime (V8 heap string, char-code/XOR obfuscation) — no static search will find it.

_Migrated from: wine-gdb-ptrace-breakpoint-unreliable, wine-cef-anti-tamper-check-tracing_

## WSC COM shim gotcha (fake AV presence)

**Symptom:** naive `IWSCProductList`/`IWscProduct` (CLSID `WSCProductList`) stub returns `S_OK` from `WscRegisterForChanges` but the app polls `get_ProductState` repeatedly, then concludes the AV integration is fake.

**Cause:** the caller waits for a real WSC change notification that never comes.

**Fix:** actually invoke the callback on a thread:
```c
typedef struct { LPTHREAD_START_ROUTINE cb; PVOID ctx; } CallbackArgs;
static DWORD WINAPI callback_thread(LPVOID param) {
    CallbackArgs *a = param;
    Sleep(150);
    if (a->cb) a->cb(a->ctx);
    HeapFree(GetProcessHeap(), 0, a);
    return 0;
}
STDAPI WscRegisterForChanges(LPVOID reserved, PHANDLE callback, LPTHREAD_START_ROUTINE cb, PVOID ctx) {
    CallbackArgs *a = HeapAlloc(GetProcessHeap(), 0, sizeof(*a));
    a->cb = cb; a->ctx = ctx;
    HANDLE h = CreateThread(NULL, 0, callback_thread, a, 0, NULL);
    if (callback) *callback = h;
    return S_OK;
}
```
Even fixed, persistent failure means the polled signal wasn't the gate — verify before/after, don't assume causation from trace adjacency. Layer cheapest-first: relay trace → targeted native-API breakpoint → Ghidra static analysis → CDP/live-JS or V8 heap forensics only once native tracing is exhausted.

_Migrated from: wine-cef-anti-tamper-check-tracing_
