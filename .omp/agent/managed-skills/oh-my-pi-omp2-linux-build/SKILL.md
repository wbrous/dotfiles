---
name: oh-my-pi-omp2-linux-build
description: "Use when building can1357/oh-my-pi (the omp Rust coding-agent workspace) from source on Linux, especially the omp2 branch — covers the full toolchain bring-up (rustup pinned nightly from rust-toolchain.toml, uv for crates/py/scripts/fetch-python.sh's bundled-package step, cmake/ninja/protoc/clang system deps) and three known Linux-specific compile breaks at commit 2f92f3b5 (and likely nearby commits) that block cargo build -p omp-app: (1) crates/sandbox/src/backends/landlock.rs has prepare/abi/run_child_entry incorrectly marked const fn while their Linux bodies call non-const syscalls/functions — remove the const qualifier (compare to every other backend's plain fn prepare; only capabilities() should stay const since it's used in a real const context and has a trivial body); (2) crates/desktop/src/linux/actor.rs is missing use std::thread;; (3) crates/desktop/src/linux/wayland/libei.rs declares a struct field context: Context that should be context: ei::Context; (4) crates/shell-builtins/src/support/xattr.rs is missing retrieve_xattrs/apply_xattrs/copy_xattrs functions that crates/shell-builtins/src/mv.rs calls — implement them on top of the file's existing raw-libc listxattr/getxattr helpers plus a new setxattr wrapper, returning/taking omp_core::FastHashMapVecu8, Vecu8."
---

## Building oh-my-pi (omp) from source on Linux

Repo: https://github.com/can1357/oh-my-pi, branch `omp2` (as of commit `2f92f3b5`).

### Prerequisites bring-up

The repo pins a specific nightly via `rust-toolchain.toml` (e.g.
`nightly-2026-08-08`). System-package rustc will NOT match; install rustup:

```sh
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs -o /tmp/rustup-init.sh
sh /tmp/rustup-init.sh -y --no-modify-path --default-toolchain none
# cargo build auto-installs the pinned toolchain via the rustup shim on first invocation,
# or force it explicitly:
~/.cargo/bin/rustup toolchain install nightly-2026-08-08 --profile minimal \
  --component rustfmt,clippy,rust-analyzer,rustc-codegen-cranelift-preview
```

System deps needed: `cmake`, `ninja`, `protobuf` (protoc), `clang`, `gcc` — all
typically present via pacman/apt already.

`crates/py/scripts/fetch-python.sh` (no args, run from repo root) vendors a
static embedded CPython into `vendor/python/` and generates
`vendor/python/pyo3-config.txt` (referenced by `.cargo/config.toml`'s
`PYO3_CONFIG_FILE` env). This step needs `uv` on PATH for its "fetching
bundled python packages" sub-step — install via `curl -LsSf
https://astral.sh/uv/install.sh | sh` (lands in `~/.local/bin`). Without uv
you'll see `uv: command not found` then `TMP: unbound variable` and the
script aborts before generating `pyo3-config.txt`.

A late warning `error: release metadata references absent license file
licenses/LICENSE.zlib-ng.txt` from this script is non-fatal — the actual
`vendor/python/pyo3-config.txt` is already written by that point; verify with
`ls vendor/python/pyo3-config.txt`.

Do the checkout/build somewhere with real disk (this workspace + vendor +
target/ can run several GB) — NOT tmpfs `/tmp`.

### Build

```sh
source ~/.cargo/env
cargo build --profile release-dev -p omp-app
```

`release-dev` matches `release` codegen settings but keeps per-crate
incremental units, and is much faster to iterate on than a full `release`
LTO build. Expect ~10 minutes cold on a 24-core machine.

Binary lands at `target/release-dev/omp` (a single ~400MB binary; child-role
dispatch for envd/workers/etc. all live behind hidden argv subcommands in the
same executable, per the README's process-model diagram).

### Known Linux-specific compile breaks (at commit 2f92f3b5)

The maintainers appear to build primarily on macOS (config comments reference
Homebrew `ld64.lld` throughout); the following bugs are real source defects,
not toolchain/version mismatches, and reproduce on a fresh clone:

1. **`crates/sandbox/src/backends/landlock.rs`** — `prepare()`, `abi()`, and
   `run_child_entry()` are declared `pub const fn`, but their
   `#[cfg(target_os = "linux")]` branches call genuinely non-const functions
   (`libc::syscall`, `bool::then_some`, `run_child_entry_linux()`). Fix:
   remove `const` from all three. Confirm via `lsp references` / grep that
   none of the three is used in an actual `const` context anywhere in the
   crate (only `capabilities()` — which has a trivial const-compatible body
   with no cfg branches — is genuinely used in a `const` initializer
   elsewhere, e.g. `capability.rs`'s `const LANDLOCK: CapabilitySet = ...`).
   Every sibling backend (`docker.rs`, `bubblewrap.rs`, `gvisor.rs`,
   `macos.rs`, `windows.rs`) declares `prepare` as a plain `fn`, confirming
   `const` was a copy-paste mistake here.

2. **`crates/desktop/src/linux/actor.rs`** — uses `thread::Builder::new()` at
   line ~50 but never imports `std::thread`. Add `use std::thread;`.

3. **`crates/desktop/src/linux/wayland/libei.rs`** — `struct ActorLibei` has
   a field `context: Context` but no `Context` type is in scope; the crate
   uses `reis::ei` extensively elsewhere in the same file (`ei::Context::new`,
   `ei::Context::connect_to_env`), and the return type of
   `Self::portal_context` is already `CoreResult<(ei::Context, ...)>`. Fix:
   change the field to `context: ei::Context`.

4. **`crates/shell-builtins/src/support/xattr.rs`** — `mv.rs`'s directory/file
   copy-fallback paths call `fsxattr::retrieve_xattrs`, `fsxattr::apply_xattrs`,
   and `fsxattr::copy_xattrs`, none of which exist in `xattr.rs` (which only
   ever exported `has_acl`, `has_security_cap_acl`,
   `get_acl_perm_bits_from_xattr` — probes for `ls`/`mkdir`, not full
   copy/preserve support for `mv`). This is a genuinely missing
   implementation, not a naming mismatch. Fix: implement on top of the
   file's existing private `list_xattrs`/`get_xattr` raw-libc helpers
   (`#[cfg(target_os = "linux")]`, using `libc::listxattr`/`libc::getxattr`
   with a size-query-then-fill pattern) by adding:
   - `set_xattr(path: &Path, name: &[u8], value: &[u8]) -> io::Result<()>`
     wrapping `libc::setxattr(..., flags = 0)` (new private helper).
   - `pub(crate) fn retrieve_xattrs(path) -> io::Result<FastHashMap<Vec<u8>, Vec<u8>>>`
     — list names, get each value, build the map.
   - `pub(crate) fn apply_xattrs(path, xattrs: FastHashMap<Vec<u8>, Vec<u8>>) -> io::Result<()>`
     — `set_xattr` each pair.
   - `pub(crate) fn copy_xattrs(from, to) -> io::Result<()>` — compose the
     two above.

   Gate the three new public functions with mv.rs's broader cfg
   (`#[cfg(all(unix, not(any(target_os = "macos", target_os = "redox"))))]`)
   with a `#[cfg(target_os = "linux")]` real-implementation /
   `#[cfg(not(target_os = "linux"))]` no-op-stub split inside each body,
   mirroring the existing `has_acl`/`has_security_cap_acl` dual-cfg pattern
   in the same file. Import `omp_core::FastHashMap` (already a workspace
   dependency, used the same way in `mv.rs`).

### Verifying success

```sh
./target/release-dev/omp --version   # prints "0.1.0"
./target/release-dev/omp --help      # lists subcommands: chat, print, rpc, serve, envd, ...
```

If the build breaks on a different/later commit, first check whether these
same four spots have already been fixed upstream before re-deriving the fix
from scratch — the bugs are narrow and specific to Linux-only code paths
that are easy for a macOS-primary dev workflow to miss.
