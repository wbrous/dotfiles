---
name: rust-windows-check-from-arch-linux
description: "Compile-check or build Windows-only Rust (windows crate, windows-service) from Arch Linux; cargo mixes Arch rustc with rustup nightly, E0514 incompatible rustc, rust-src download failure."
---

# Checking Windows-only Rust from Arch Linux

Arch's `/usr/bin/rustc` has no Windows std. `~/.cargo/bin` holds rustup nightlies that can add it.

## Recipe

1. Add the target to a rustup toolchain (check `~/.cargo/bin/rustup toolchain list` first):
   `~/.cargo/bin/rustup target add x86_64-pc-windows-gnu --toolchain <toolchain>`
   (`mingw-w64-gcc` is already installed for linking.)
2. ALWAYS pin one toolchain for every cargo call, or the build mixes compilers:
   ```
   export RUSTUP_AUTO_INSTALL=0 RUSTUP_TOOLCHAIN=<toolchain>-x86_64-unknown-linux-gnu PATH=$HOME/.cargo/bin:$PATH
   ```
   Symptoms of not pinning: rustup tries to auto-install `stable` / `rust-src` mid-build, then `E0514 found crate ... compiled by an incompatible version of rustc`. Fix: set the env above, `cargo clean`, rebuild.
3. Then: `cargo check|clippy|build --release --target x86_64-pc-windows-gnu`. This produces a real PE32+ `.exe` and type-checks every `#[cfg(windows)]` module. It cannot RUN anything.
4. Keep pure logic (policy, parsing, state) outside `#[cfg(windows)]` in `lib.rs` so `cargo test` runs on Linux.

## Gotchas

- Verify `windows` crate signatures by grepping `~/.cargo/registry/src/*/windows-<ver>/src/Windows/Win32/<Area>/mod.rs` rather than guessing; each API needs its Cargo feature (e.g. `CreateEnvironmentBlock` is `Win32_System_Environment`, SCM calls are `Win32_System_Services`).
- `#[repr(C, packed)]` fields cannot be borrowed (E0793). If the C layout has no padding anyway, use `#[repr(C)]` and pin it with `const _: () = assert!(size_of::<T>() == ...)`.
- ureq 3: use `Agent::config_builder().http_status_as_error(false)` to read status/body yourself.
