---
name: ghidra-headless-java-scripts-and-webview2-policy-args
description: "Use when running Ghidra's analyzeHeadless (Ghidra 11+/12) with -preScript/-postScript and getting \"Ghidra was not started with PyGhidra. Python is not available\" for .py scripts, or when auto-analysis on raw/JIT'd (e.g. V8) code dumps produces excessive \"Failed to create function ... contains referring thunk\" errors and slow/broken Decompiler Switch Analysis. Also covers injecting Chromium/CEF command-line flags into a WebView2-hosted app when the WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS env var is set correctly (verified via wine cmd /c echo %VAR%) but never appears in the child process's actual cmdline."
---

## Ghidra headless: .py scripts fail with "not started with PyGhidra"

In Ghidra 12+, `analyzeHeadless -preScript foo.py` / `-postScript foo.py` fails:
`Ghidra was not started with PyGhidra. Python is not available`

Jython-style .py GhidraScripts are no longer supported by the default headless
launcher. Two fixes:
- Write scripts in **Java** instead (`.java`, extends `ghidra.app.script.GhidraScript`,
  placed in a dir passed via `-scriptPath`). The headless analyzer compiles these
  on the fly automatically — no PyGhidra needed, works in any Ghidra version.
- Or explicitly launch via PyGhidra's own entry point if you need real Python.

Common Java-script gotchas:
- `ReferenceManager.getReferencesTo(addr)` returns `ReferenceIterator`, NOT
  `Reference[]` — iterate directly, don't assign to an array.
- To rebase a raw-imported binary (no headers, base 0) to its real runtime
  address before analysis, use a `-preScript` that calls
  `currentProgram.setImageBase(newBaseAddr, true)` — must run in preScript
  (before analysis) so absolute addresses embedded in code resolve correctly.

## Full auto-analysis is wrong tool for JIT'd/interpreter code dumps

Dumping a live process's RWX memory (e.g. `gdb dump memory` on a V8 JIT code
heap) and running Ghidra's full auto-analysis on it produces thousands of
"Failed to create function at X since its body contains referring thunk at Y"
errors and very slow "Decompiler Switch Analysis" — because JIT'd interpreter
dispatch code (V8 Ignition bytecode handlers etc.) uses computed-goto style
`push addr; push addr; ret` trampoline chains that don't have normal function
prologues/epilogues. Ghidra's function-boundary heuristics choke on this.

Also: if the target address disassembles to a stream of `LEA ESP,[ESP+N]` /
`MOV [ESP],REG` / `PUSH addr; PUSH addr; RET` trampolines with periodic
`MOV EAX,[stack_cookie]; XOR EAX,EBP` stack-canary checks, that IS V8's
generic interpreter dispatch loop — it's the same for every JS function in
the process and tells you nothing about the specific JS logic being run.
Decompiling it is a dead end; you'd need the actual V8 bytecode array + a
bytecode-aware disassembler, not x86 disassembly of the interpreter core.

For a quick targeted look instead of full analysis:
- Import with `-noanalysis` (skips the expensive/broken function-creation pass).
- Use a script that just calls `disassemble(addr)` / walks forward instruction
  by instruction over a small window and dumps to a text file. This finishes
  in seconds instead of minutes and avoids all the thunk errors.

## WebView2: env var ignored, use registry policy instead

`WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS` is documented as always-honored by
WebView2Loader.dll, but in practice some apps/loader versions don't apply it
to the actual browser process command line — verify by checking
`/proc/<pid>/cmdline` of the spawned `msedgewebview2.exe`, not just that the
env var propagates into the Wine process environment (confirm separately via
`wine cmd /c echo %VAR%`).

If the env var doesn't show up in cmdline, use the **enterprise policy
registry key** instead, which WebView2Loader reads unconditionally regardless
of app code:

```
wine reg add "HKLM\Software\Policies\Microsoft\Edge\WebView2\AdditionalBrowserArguments" /ve /t REG_SZ /d "--your --flags --here" /f
```

This is a machine-wide policy override (Group Policy ADMX equivalent) and
took effect immediately in testing where the env var was silently dropped.
