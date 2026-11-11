# Crash Diagnosis

Diagnose native crashes (SIGSEGV/SIGABRT/core dumps) on Linux: AppImage symbolization, gdb batch-mode debuginfod, amdgpu GTT exhaustion, JetBrains JCEF bursts, and quickshell crashes. Supplements coredumpctl/journal basics.

## AppImage crash: gdb can't open /tmp/.mount_* files

**Symptom:** `coredumpctl info <pid>` shows `binary: /tmp/.mount_XXXXXXXX/usr/bin/<name>`, but the mount is gone by investigation time (`journalctl` shows `tmp-.mount_XXXXXXXX.mount: Deactivated successfully` right after the coredump). gdb on a bare `coredumpctl dump` core gives dozens of `warning: Can't open file /tmp/.mount_XXXXXXXX/usr/lib/*.so during file-backed mapping note processing` with unresolved (`n/a`/`??`) frames, though libc/system libs resolve.

**Cause:** systemd/the AppImage runtime unmounts its squashfs the moment the process dies, so the executable and bundled libs in the core's file-backed mappings no longer exist at that path.

**Fix — re-extract and substitute the path (no sudo needed):**

```bash
cd /tmp && mkdir stmarks_extract && cd stmarks_extract
chmod +x /path/to/app.AppImage
/path/to/app.AppImage --appimage-extract   # ./squashfs-root/
core=$(mktemp -t crash-XXXXXX.core)
coredumpctl dump <pid> --output="$core"
gdb -q -batch \
  -ex 'set substitute-path /tmp/.mount_XXXXXXXX /tmp/stmarks_extract/squashfs-root' \
  -ex 'file /tmp/stmarks_extract/squashfs-root/usr/bin/<name>' \
  -ex "core-file $core" \
  -ex 'bt' -ex 'thread apply all bt'
rm -f "$core"
```

`set substitute-path` must be the very first `-ex` (before `core-file`) — as a later `-batch -ex` it's too late for shared-library note processing on some gdb versions. Find the original .AppImage via `~/Downloads`, `~/.local/share/<app-id>`, or `find ~ -iname '*.appimage'`.

**If frames stay unresolved:** for AppImage'd GUI toolkits (Electron/CEF, WebKitGTK/Tauri wrappers) the bundled libs are usually stripped with no debuginfod coverage — use `info proc mappings` after `core-file` and cross-reference the crash address against mapped ranges to at least attribute the abort to a library (e.g. `libwebkit2gtk-4.1.so.0`). That's reportable signal ("WebKit itself called abort()"), not a bare address. Delete the scratch extraction dir and core afterwards — a core is a verbatim memory copy and may contain secrets.

_Migrated from: diagnose-crash-appimage-unmounted_

## gdb batch mode: debuginfod stays disabled

**Symptom:** gdb batch symbolization leaves frames `??` even with `-ex 'set debuginfod enabled on'`.

**Cause:** In `-batch` mode gdb asks "Enable debuginfod for this session?" BEFORE `-ex` runs, auto-answers N (no tty).

**Fix:** use `-iex` instead:

```bash
core=$(mktemp -t crash-XXXXXX.core); trap 'rm -f "$core"' EXIT
coredumpctl dump <pid> --output="$core"
DEBUGINFOD_URLS="https://debuginfod.archlinux.org" timeout 280 \
  gdb -q /usr/bin/<exe> "$core" -batch -iex 'set debuginfod enabled on' -ex 'thread 1' -ex 'bt 8'
rm -f "$core"
```

First run downloads debuginfo (~3 min for mesa/libc) — background it and do journal work meanwhile. Verify `ls /tmp/crash-*.core` is empty afterwards.

_Migrated from: diagnose-crash-gdb-debuginfod-and-amdgpu-gtt-exhaustion_

## Journal after a reboot

**Symptom:** `journalctl -b 0` shows nothing about the crash.

**Cause:** `uptime -s` is later than the crash — the crash-time journal is in the previous boot (`journalctl --list-boots`). Use `journalctl -b -1 -k`. Kernel floods (hundreds of lines): count and bucket with `grep | awk '{print substr($3,1,7)}' | sort | uniq -c` instead of printing them.

_Migrated from: diagnose-crash-gdb-debuginfod-and-amdgpu-gtt-exhaustion_

## Pattern: amdgpu GTT exhaustion (many GPU apps SIGABRT together)

**Symptom:** kitty, Hyprland, browsers abort in the same seconds on AMD iGPU. Kernel: `amdgpu ... *ERROR* amdgpu_vm_validate() failed` + `Not enough memory for command submission!`. Crashing thread is a Mesa `util_queue` worker: `abort` <- `amdgpu_ctx_set_sw_reset_status` (PIPE_UNKNOWN_CONTEXT_RESET, "The CS has been rejected") <- `amdgpu_cs_submit_ib`. Hyprland aborts in `CHyprOpenGLImpl::begin`; kernel logs `VM memory stats ... non-zero when fini` per client.

**Cause:** Mesa aborts deliberately — not an app bug. Check `/sys/class/drm/card*/device/mem_info_{vram,gtt}_{total,used}`: Strix iGPU has ~512 MiB VRAM and ~16 GiB GTT shared with RAM. Seen trigger: ollama with `OLLAMA_VULKAN=1 OLLAMA_IGPU_ENABLE=1` treated GTT as free VRAM and loaded ~12 GiB (look for `ollama`/`llama-server` memory-breakdown lines just before the crash). Fix: run ollama on CPU, smaller model/context, or cap GPU memory. Not an Omarchy bug; system RAM and OOM killer are irrelevant.

_Migrated from: diagnose-crash-gdb-debuginfod-and-amdgpu-gtt-exhaustion_

## JetBrains JCEF cef_server SIGABRT bursts

**Symptom:** Dozens of `cef_server` cores within seconds from `.../jcef-plugin/jcef/cef_server`. Crash thread: `main -> CefExecuteProcess -> __stack_chk_fail -> __fortify_fail -> abort`. Cmdline: `--type=utility --utility-sub-type=unzip.mojom.Unzipper` (also DataDecoderService, on_device_model) with `--change-stack-guard-on-fork=enable --no-sandbox`. Parent `cef_server --port=...`, GPU/network/renderer helpers and the IDE survive. No OOM, no data loss. Seen on glibc 2.39-2.44.

**Cause:** JetBrains hardcodes `--change-stack-guard-on-fork=enable`; helpers trip the stack canary on glibc 2.39+. Unfixed as of 2026-10-31; YouTrack JBR-10670, JBR-10677, JBR-10549, PY-92855. NOT an Omarchy bug; don't file duplicates — add a confirmation to JBR-10670.

**Workflow:** `coredumpctl list | grep -c cef_server`, check a few PIDs for the same subtype. Skip gdb (JetBrains ships no symbols; debuginfod has none). Rule out OOM, then query YouTrack JSON (`curl -H 'Accept: application/json' 'https://youtrack.jetbrains.com/api/issues/JBR-10670?...'`) since the pages are JS-rendered. Trigger is browser startup (Markdown preview, extension CRX unpack).

**User options (offer, don't apply unprompted):** disable JCEF via `-Dide.browser.jcef.enabled=false` in Help > Edit Custom VM Options (loses Markdown preview); `-Dide.browser.jcef.sandbox.enable=false` reportedly does NOT help; or live with it / `omarchy-crash-mute '<cef_server path>'`.

_Migrated from: diagnose-crash-jetbrains-jcef-cef-server-stack-chk_

## quickshell / Omarchy shell crashes

**Evidence beyond coredumpctl:** quickshell writes its own crash dir `~/.cache/quickshell/crashes/<instance-id>/` with `report.txt` (version, build flags, GPU, env) and `log.qslog.log` (full runtime log, can be MBs; instance id in the journal's `Further crash information is stored under ...` line). Read the tail: `tail -c 6000 log.qslog.log | strings` — last events before the abort show what the shell was doing. The journal for the crashed boot (`journalctl -b -1`, grep `omarchy-shell|quickshell|coredump`) holds the fatal Qt message (`pure virtual method called`, `Terminate called without active C++ exception`) and wrapper lines (`Quickshell crashed within 10 seconds of launching. Not restarting...`, `Omarchy shell exited with status 255; relaunching`). `coredumpctl info` shows the crashing thread name (e.g. `QQuickPixmapRea`), which is the comm, not "quickshell".

**Gotchas:** after a reboot use `journalctl -b -1`; a quickshell upgrade AFTER the crash explains gdb "doesn't match build-id" warnings but didn't cause the crash; gdb batch needs `-iex 'set debuginfod enabled on'`; Arch has no `quickshell-debug` package so quickshell frames stay unsymbolized — say so, don't invent names. Compare against earlier quickshell dumps before calling stacks the same bug.

_Migrated from: diagnose-crash-quickshell-omarchy-shell_
