---
name: wine-cef-anti-tamper-check-tracing
description: "Use when reverse-engineering why a Wine-hosted CEF/Chromium/WebView2 kiosk app (e.g. Respondus LockDown Browser, exam-lockdown/anti-cheat software) shows an environment-integrity or \"can't be used in virtual machine software\" error, or similar native-code+embedded-browser anti-tamper check that needs tracing under Wine. Covers the full toolchain: WINEDEBUG=+relay call tracing, gdb SIGSTOP-then-attach to avoid races with short-lived processes, PE export RVA parsing for reliable breakpoint addresses, Ghidra headless raw-binary analysis of JIT/RWX memory dumps, recognizing V8 JIT trampoline code (dead end for static analysis), and WSC/COM shim implementation gotchas."
---

## Context
Kiosk/exam-lockdown apps (e.g. Respondus LockDown Browser) embed CEF/Chromium or WebView2 and run anti-tamper/environment-integrity checks (VM detection, AV presence, hardware fingerprinting) that show a blocking error dialog if unsatisfied. Under Wine, defeating these requires a layered investigation since the check logic is often split between native Win32 API calls (traceable) and embedded JavaScript running in V8 (not statically traceable).

## Toolchain, in order of effort

### 1. WINEDEBUG=+relay call tracing (cheapest, do this first)
```bash
export WINEDEBUG="+relay"
timeout 15 wine ./App.exe args > /tmp/trace.log 2>&1
grep -n "MessageBoxA\|MessageBoxW" /tmp/trace.log   # find the error dialog call
```
- Relay traces print `ret=<addr>` after every call — this is the caller's return address, free of charge.
- Filter to one Wine "thread" (their own hex thread-id prefix, e.g. `0024:`) to get a clean serial call sequence for that logical thread:
  `awk -F: '$1=="0024"' /tmp/trace.log > /tmp/thread.txt`
- Scan the ~200-500 lines immediately before the fatal call for the last *distinctive* (non-boilerplate: skip RtlAllocateHeap/RtlFreeHeap/GetProcessHeap/EtwEvent*/critical-section calls) API call — this is often the actual signal being checked (WSC AV state, registry queries, SCSI/BIOS reads, etc).
- To find what native API a check queries even when the JS logic is opaque: this trace-adjacency method works because the JS ultimately must call into real Win32 APIs for anything OS-observable (AV status, hardware IDs, registry). If NO native API call precedes the check by anything distinctive, the check is likely computed entirely inside V8 from already-cached JS state — see step 5.

### 2. gdb SIGSTOP-then-attach (avoids races with fast-dying/short-lived processes)
Naive `pgrep` + `gdb -p PID` races against the process continuing or exiting. Instead:
```bash
for i in $(seq 1 100); do
  PID=$(pgrep -f "TargetExe.exe uniqueargs" | head -1)
  if [ -n "$PID" ]; then kill -STOP "$PID" && break; fi
done
```
This freezes the process the instant it's found. Then attach gdb, which can `continue` safely without losing the race. If you need a specific DLL loaded first (e.g. user32.dll for a MessageBoxA breakpoint), `kill -CONT`, poll `/proc/$PID/maps` for the DLL, then `kill -STOP` again once it appears — THEN compute breakpoint addresses from the now-stable base.

Note: gdb attaching to a Wine process can behave erratically (spurious "Temporarily disabling breakpoints for unloaded shared library" warnings, breakpoints firing at wrong addresses) — this can look like anti-debug evasion but is often just Wine/gdb PIE-tracking flakiness. Don't over-interpret it as proof of active anti-debug without other evidence.

### 3. Compute reliable breakpoint addresses via PE export table parsing
`objdump -p dll.dll` export listings are NOT reliable RVA sources for scripting (columns don't always mean what they look like). Parse the PE export directory directly:
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

### 4. Ghidra headless analysis of a dumped memory region
Dump a live RWX region (JIT code, unpacked payload, etc):
```bash
cat > /tmp/gdb_dump.cmd <<EOF
dump memory /tmp/dump.bin 0xSTART 0xEND
detach
quit
EOF
gdb -q -batch -x /tmp/gdb_dump.cmd -p $PID
```
**Ghidra 12+ gotcha:** `.py` postScript/preScript files FAIL with "Ghidra was not started with PyGhidra. Python is not available" under plain `analyzeHeadless`. Write scripts in **Java** (`.java`, extends `GhidraScript`) instead — these always work with the default headless launcher, no PyGhidra setup needed.

**Auto-analysis on raw JIT'd/obfuscated code is slow and error-prone**: V8-JIT'd or virtualized/obfuscated code full of thunks/trampolines produces thousands of "Failed to create function ... contains referring thunk" errors and can take minutes with the default analyzer (Decompiler Switch Analysis especially). If you only need a disassembly window around one known address, skip full analysis:
```
analyzeHeadless proj Name -import dump.bin -processor x86:LE:32:default -noanalysis \
  -scriptPath /path/to/scripts -preScript RebaseScript.java -postScript DisasmWindow.java
```
Use a preScript to `currentProgram.setImageBase(addr, true)` to the real runtime base before disassembling, and a postScript that just calls `disassemble()` across a bounded address window and dumps `Instruction` listing text — this finishes in ~20s vs. minutes/hangs for full analysis, and sidesteps function-boundary heuristic failures entirely.

Launch long Ghidra jobs fully detached (`nohup ... &`, `disown`) rather than as a foreground bash call — the bash tool's own ~300s timeout can kill a still-useful background analysis before you've had a chance to fix something and rerun against the same project.

### 5. Recognize V8 JIT trampoline code (the dead end for static analysis)
Chromium/CEF's V8 Sparkplug baseline compiler emits highly repetitive, frame-pointer-free dispatch code with this signature:
```
MOV EAX,[stack_guard_addr]
XOR EAX,EBP              ; stack-canary style check
PUSH addr1
PUSH addr2
RET                       ; tail-call trampoline chaining
```
If a captured return address disassembles to code like this, **you are looking at generic V8 interpreter/JIT dispatch glue, not application logic**. The actual decision (the `if` statement, the string literals) lives in a `BytecodeArray`/String heap object elsewhere in the V8 heap, not in this machine code. Do not spend further time disassembling this region — pivot to:
- Chrome DevTools Protocol (`--remote-debugging-port=N --remote-allow-origins=*`) if the host app honors argv passthrough to CEF settings (test by checking `/proc/PID/cmdline` of the actual browser subprocess, then `curl localhost:PORT/json/version`). Many security-conscious kiosk apps set CEF's `remote_debugging_port` via their own C++ settings struct and ignore/strip this flag entirely — if `curl` never connects despite the flag reaching argv, this is blocked at the app level, not a syntax issue.
- Static text search of resource files: check for gzip-compressed entries in Chromium `.pak` resource packs (format v5: many small gzip streams concatenated with `\x1f\x8b\x08` magic — scan for magic bytes and `zlib.decompressobj(16+MAX_WBITS)` each one rather than trying to hand-parse the pak directory header exactly).
- If plain-text/gzip search finds nothing, the check content may be an obfuscated/split JS string (defeats substring search by design) — try searching for shorter, harder-to-split brand/keyword tokens instead of full sentences.
- If none of the above pan out, the only remaining lever is full V8 heap/bytecode forensics (walking heap object graphs, decoding `BytecodeArray` contents) — genuinely multi-day specialized work, not tractable with Ghidra (no V8 bytecode support). Say so plainly rather than continuing to guess.

### 6. WSC (Windows Security Center) COM shim gotcha
If faking `IWSCProductList`/`IWscProduct` (CLSID `WSCProductList`) to satisfy an AV-presence check, a naive stub that returns `S_OK` from `WscRegisterForChanges` without ever invoking the caller's callback can cause the *caller* to poll `get_ProductState` repeatedly (waiting for a real WSC change notification) and eventually give up, concluding the AV integration is fake. Fix: actually spawn a thread and call the provided `LPTHREAD_START_ROUTINE` callback:
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
Even with this fix, a persistent check failure means the polled signal wasn't the actual gate — don't assume causation from adjacency in a trace; verify by testing before/after.

## Key lesson
Layer the investigation cheapest-first: relay trace → gdb breakpoint on a specific native API → Ghidra static analysis of any captured code region → only escalate to CDP/live-JS-debugging or V8 heap forensics once native-API-level tracing is conclusively exhausted (no distinctive API call precedes the check, and disassembly reveals generic V8 dispatch glue rather than app logic).
