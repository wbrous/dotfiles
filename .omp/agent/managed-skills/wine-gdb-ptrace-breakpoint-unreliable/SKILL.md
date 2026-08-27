---
name: wine-gdb-ptrace-breakpoint-unreliable
description: "Use when a gdb or manual-ptrace breakpoint set on a Wine-loaded PE DLL export (e.g. user32.dll!MessageBoxA) never fires despite the call demonstrably happening (visible via WINEDEBUG=+relay trace or the actual UI effect), even though the target address is verified correct and stable and the 0xCC byte is confirmed written. Also covers correctly parsing a Chromium/CEF resources.pak (v5 format, possibly Brotli-compressed per-entry) to search for UI strings statically instead of live-debugging."
---

## Symptom
Set a breakpoint (gdb `break *addr` or manual ptrace `PTRACE_POKETEXT` injecting `0xCC`) at a Win32 API export's entry point inside a Wine-loaded PE DLL (computed correctly from the PE export table: base-from-`/proc/PID/maps` + RVA-from-export-directory). The call is proven to happen (WINEDEBUG=+relay logs it, or the resulting UI/dialog appears), yet:
- gdb: gives `warning: Temporarily disabling breakpoints for unloaded shared library "...user32.dll"` even though the module's mapping never actually moves (verified stable across the whole run via repeated `/proc/PID/maps` checks) — and a readback of the target bytes right after `break` shows the original instruction bytes were **never overwritten with `0xCC`** (gdb silently failed to insert it).
- Manual ptrace: byte-level readback confirms `0xCC` genuinely was written, `PTRACE_CONT` succeeds, but `waitpid()` never returns a stop event — the traced process just keeps running (or exits normally, `status==0`) as if the breakpoint were never hit, even for a **trivial, self-written test program that unconditionally calls MessageBoxA()** (rules out anti-debug in the target app — this is a generic Wine issue, not application-specific).

## Root cause (working theory, unconfirmed in Wine internals)
Wine's own SEH/exception-dispatch machinery installs its own SIGTRAP/SIGSEGV handlers for its internal use (implementing Windows structured exception handling on Linux). This appears to intercept or otherwise interfere with externally-injected ptrace traps in ways that prevent them from reliably reaching the tracer via the normal ptrace-stop protocol. This is NOT specific to any one app — it reproduces with a minimal `MessageBoxA()`-only test binary compiled fresh and run under the same Wine/GE-Proton build.

## What still works
- `WINEDEBUG=+relay` (and `+seh`) traces are reliable ground truth for *what* gets called, with resolved string arguments, return addresses, and register state at the call — use this instead of live breakpoints to inspect a specific call.
- `gdb -p PID` **static** inspection (`x/Ni`, reading `/proc/PID/mem`, `dump memory`) works fine on a process that is already sitting idle (e.g. blocked in a modal dialog's message loop) — only *breakpoint-triggered interruption at a chosen future point* is unreliable.
- Dumping a live memory region to a file (`gdb dump memory /tmp/x.bin <lo> <hi>`) and statically disassembling it in Ghidra (import as **Raw Binary**, correct `-processor x86:LE:32:default`, rebase via a script setting `program.setImageBase()`) works well for post-hoc analysis of JIT'd/dynamically-generated code, once you accept you can't interactively single-step it.
- `kill -STOP`/`kill -CONT` polling on `/proc/PID/maps` to catch a process at a *specific loaded-module* milestone (not a specific instruction) is reliable for coarse-grained synchronization (e.g. "stop me once user32.dll is mapped").

## Don't waste time on
- Retrying with different breakpoint-setting orders, `catch load`, hardware watchpoints, or `set follow-fork-mode` variants — the failure is at the trap-delivery layer, not the breakpoint-placement layer, and none of these change that.
- Assuming ASLR/remapping explains a missed breakpoint before verifying: check `/proc/PID/maps` for the target module's base at multiple time points across the *entire* run duration first — Wine module bases are typically completely stable once mapped.

## Ghidra headless script notes (Wine/32-bit PE dumps)
- Ghidra 12+ requires **PyGhidra** for `.py` pre/post-scripts (`analyzeHeadless` alone errors `Ghidra was not started with PyGhidra`). Write scripts in plain **Java** instead (`GhidraScript` subclass, compiled on the fly by the default headless script provider) — always works without extra setup.
- `ReferenceManager.getReferencesTo()` returns a `ReferenceIterator`, not `Reference[]` — a common compile error when porting old snippets.
- Full auto-analysis (`analyzeAll`) on a raw dump of JIT'd/virtualized code (e.g. V8 Sparkplug output) produces thousands of `Failed to create function ... contains referring thunk` errors and can hang on "Decompiler Switch Analysis" for a long time, with poor results (decompilation of dispatch-trampoline code is meaningless anyway). For inspecting a specific known address, skip analysis entirely: import with `-noanalysis`, then a script that just calls `disassemble()` over a bounded address window and prints the instruction listing. Orders of magnitude faster and avoids the broken heuristics.

## Chromium/CEF resources.pak parsing (v5 format, corrected)
The DataPack v5 header is (all little-endian):
```
uint32 version        (=5)
uint8  encoding        (byte offset 4; 0=BINARY,1=UTF8,2=UTF16 — this is TEXT encoding of entries, not compression)
[3 bytes padding]
uint16 resource_count  (byte offset 8)
uint16 alias_count     (byte offset 10)
```
then `resource_count + 1` entries of `{ uint16 id; uint32 file_offset }` (6 bytes each, sorted, last one is a sentinel giving the end offset of the previous). A naive guess of `version(4)+resource_count(4)+alias_count(4)+encoding(1)` (all as reported by some outdated docs) produces garbage (huge nonsensical `alias_count`, `encoding` byte that isn't 0/1/2) — verify by checking `resource_count`/`alias_count` are small sane numbers and that `entries` offsets are monotonically increasing up to the file size.

Per-entry compression: **modern Chromium (~M90+) uses Brotli by default, not gzip**, for resources.pak entries. A gzip-magic-byte (`\x1f\x8b\x08`) scan across the raw file will silently find nothing if the actual entries are Brotli-compressed (Brotli has no fixed magic-number header to scan for) — you must parse the entry table properly to get exact `[offset, offset)` boundaries per resource ID, then decompress each with the `brotli` CLI (`brotli -d -c entry.bin`); the standalone `python3-brotli` module is often not installed but the CLI usually is (`pacman -S brotli` if not). A string absent from a naive gzip-stream scan may still be present once entries are Brotli-decoded — always confirm which compression is actually in use before concluding a resource pack is "clean" of some string.

If a string still isn't found after correct Brotli decoding of every entry, plus raw search of the exe/DLLs (both ASCII and UTF-16LE, including short 6-10 char fragments to rule out concatenation/obfuscation) — it's very likely constructed dynamically at runtime (e.g. built from a JS string in a V8 heap, or via char-code/XOR obfuscation) and won't be found by any static file search at all.
