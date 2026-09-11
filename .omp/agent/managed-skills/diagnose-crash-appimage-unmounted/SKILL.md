---
name: diagnose-crash-appimage-unmounted
description: "Use when diagnose-crash's gdb symbolization step fails with \"Can't open file /tmp/.mount_XXXXXXXX/...\" warnings and unresolved (n/a / ??) frames because the crashed process was an AppImage — systemd/the AppImage runtime unmounts its squashfs at /tmp/.mount_random/ the moment the process dies, so the executable and its bundled shared libs referenced in the core's file-backed mappings no longer exist at that path."
---

## Symptom

`coredumpctl info <pid>` shows `binary: /tmp/.mount_XXXXXXXX/usr/bin/<name>`, and by the
time you investigate, `/tmp/.mount_XXXXXXXX` no longer exists (`ls` on it fails —
`journalctl` will show a `tmp-.mount_XXXXXXXX.mount: Deactivated successfully` line right
after the coredump was written). Following the base `diagnose-crash` skill's gdb recipe
against a bare `coredumpctl dump` core produces unresolved frames and dozens of
`warning: Can't open file /tmp/.mount_XXXXXXXX/usr/lib/*.so during file-backed mapping
note processing` — none of the app's own libraries resolve, even though libc/system libs
do.

## Fix: re-extract the AppImage and substitute the path

1. Find the original `.AppImage` file (check `~/Downloads`, `~/.local/share/<app-id>`
   dirs referenced by the crashed binary's data directory, or `find ~ -iname '*.appimage'`).
2. Extract it to a scratch dir — this reconstructs the exact filesystem layout that was
   mounted at `/tmp/.mount_XXXXXXXX`:
   ```bash
   cd /tmp && mkdir stmarks_extract && cd stmarks_extract
   chmod +x /path/to/app.AppImage
   /path/to/app.AppImage --appimage-extract   # produces ./squashfs-root/
   ```
3. Dump the core and run gdb with `set substitute-path` mapping the dead mount path to
   the extracted tree, *before* loading the core file (not as a `-batch -ex` after
   `core-file`, which is too late for shared-library note processing on some gdb
   versions — safest to do it as the very first `-ex`):
   ```bash
   core=$(mktemp -t crash-XXXXXX.core)
   coredumpctl dump <pid> --output="$core"
   gdb -q -batch \
     -ex 'set substitute-path /tmp/.mount_XXXXXXXX /tmp/stmarks_extract/squashfs-root' \
     -ex 'file /tmp/stmarks_extract/squashfs-root/usr/bin/<name>' \
     -ex "core-file $core" \
     -ex 'bt' -ex 'thread apply all bt'
   rm -f "$core"
   ```
   (Replace `/tmp/.mount_XXXXXXXX` with the exact mount path from `coredumpctl info`.)
4. No `sudo`/bind-mount needed — `substitute-path` handles it entirely inside gdb.
   (A bind-mount of `squashfs-root` back onto `/tmp/.mount_XXXXXXXX` also works and needs
   no gdb flag, but requires root and isn't worth it when substitute-path is available.)

## Locating the crash address when frames stay `n/a`/`??`

If frames are still unresolved for the app's own (unstripped) main binary or bundled
libs even in-tree, check whether gdb picked up the debug info at all — for AppImage'd
GUI toolkits (Electron/CEF, or WebKitGTK-based wrappers built with e.g. Tauri) the
bundled shared libraries are usually stripped release builds with no local debug info
and no debuginfod coverage, so frames will stay unresolved even with a correct
substitute-path. In that case, identify *which* library the crash address belongs to
via `info proc mappings` (loaded after `core-file`) — cross-reference the unresolved
return address against the mapped ranges to at least attribute the abort to a specific
library (e.g. `libwebkit2gtk-4.1.so.0`, `libnvidia-gpucomp.so`) even without a function
name. This is real, reportable signal ("WebKit itself called abort()") — state it as
such rather than leaving the frame as a bare unexplained address.

## Cleanup

Delete the scratch extraction dir and the core file when done — same rule as the base
skill: a core dump is a verbatim memory copy and may contain secrets.
