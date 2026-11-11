# Reverse Engineering Notes

Ghidra headless scripting, JIT-dump analysis limits, WebView2 flag injection, and checking Windows-only Rust from Arch Linux.

## Ghidra headless: .py scripts fail ("not started with PyGhidra")

**Symptom:** `analyzeHeadless -preScript foo.py` fails: `Ghidra was not started with PyGhidra. Python is not available`.

**Cause:** In Ghidra 12+, Jython-style .py GhidraScripts are no longer supported by the default headless launcher.

**Fix:** Write scripts in **Java** (`.java`, extends `ghidra.app.script.GhidraScript`, dir passed via `-scriptPath`) — the headless analyzer compiles them on the fly, no PyGhidra needed. Or launch via PyGhidra's own entry point for real Python. Java-script gotchas: `ReferenceManager.getReferencesTo(addr)` returns `ReferenceIterator`, not `Reference[]`; to rebase a raw import (no headers, base 0), call `currentProgram.setImageBase(newBase, true)` in a `-preScript` (before analysis) so absolute addresses resolve.

_Migrated from: ghidra-headless-java-scripts-and-webview2-policy-args_

## Full auto-analysis is the wrong tool for JIT'd code dumps

**Symptom:** Dumping live RWX memory (e.g. `gdb dump memory` on a V8 JIT heap) and running full auto-analysis gives thousands of "Failed to create function at X since its body contains referring thunk at Y" errors plus slow/broken Decompiler Switch Analysis.

**Cause:** JIT'd interpreter dispatch code (V8 Ignition handlers) uses computed-goto `push addr; push addr; ret` trampolines with no normal prologues/epilogues — function-boundary heuristics choke. A stream of `LEA ESP,[ESP+N]` / `MOV [ESP],REG` / `PUSH addr; PUSH addr; RET` with periodic stack-canary checks IS V8's generic interpreter dispatch loop — identical for every JS function, tells you nothing about the specific JS logic. Decompiling it is a dead end; you'd need the V8 bytecode array + a bytecode-aware disassembler.

**Fix:** Import with `-noanalysis`, then script a targeted `disassemble(addr)` walk over a small window dumping to text — seconds instead of minutes, no thunk errors.

_Migrated from: ghidra-headless-java-scripts-and-webview2-policy-args_

## WebView2: env var ignored, use registry policy

**Symptom:** `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS` is set correctly (verified via `wine cmd /c echo %VAR%`) but never appears in the child `msedgewebview2.exe` cmdline (check `/proc/<pid>/cmdline`, not just env propagation).

**Cause:** Some apps/loader versions don't apply the env var to the browser process.

**Fix:** Use the enterprise policy registry key, which WebView2Loader reads unconditionally:

```
wine reg add "HKLM\Software\Policies\Microsoft\Edge\WebView2\AdditionalBrowserArguments" /ve /t REG_SZ /d "--your --flags --here" /f
```

Took effect immediately in testing where the env var was silently dropped.

_Migrated from: ghidra-headless-java-scripts-and-webview2-policy-args_

## Checking Windows-only Rust from Arch Linux

**Symptom:** Arch's `/usr/bin/rustc` has no Windows std; unpinned cargo mixes Arch rustc with rustup nightlies → `E0514 found crate ... compiled by an incompatible version of rustc` after rustup tries to auto-install `stable`/`rust-src` mid-build.

**Fix:**

1. `~/.cargo/bin/rustup target add x86_64-pc-windows-gnu --toolchain <toolchain>` (`mingw-w64-gcc` already installed for linking).
2. ALWAYS pin one toolchain per cargo call:
   ```
   export RUSTUP_AUTO_INSTALL=0 RUSTUP_TOOLCHAIN=<toolchain>-x86_64-unknown-linux-gnu PATH=$HOME/.cargo/bin:$PATH
   ```
   Then `cargo clean` and rebuild.
3. `cargo check|clippy|build --release --target x86_64-pc-windows-gnu` — produces a real PE32+ `.exe`, type-checks every `#[cfg(windows)]` module; cannot RUN anything.
4. Keep pure logic outside `#[cfg(windows)]` in `lib.rs` so `cargo test` runs on Linux.

**Gotchas:** verify `windows` crate signatures by grepping `~/.cargo/registry/src/*/windows-<ver>/src/Windows/Win32/<Area>/mod.rs` (each API needs its Cargo feature); `#[repr(C, packed)]` fields can't be borrowed (E0793) — use `#[repr(C)]` + a size assert if the layout has no padding anyway; ureq 3 needs `Agent::config_builder().http_status_as_error(false)` to read status/body yourself.

_Migrated from: rust-windows-check-from-arch-linux_
