---
name: diagnose-crash-gdb-debuginfod-and-amdgpu-gtt-exhaustion
description: "Crash diagnosis gotchas: gdb batch debuginfod stays disabled (frames unresolved), journal after reboot, many apps SIGABRT together with amdgpu 'Not enough memory for command submission' on iGPU."
---

## When
Extends the `diagnose-crash` skill. Use when symbolizing a core with gdb in batch mode, when the machine rebooted after the crash, or when several GPU apps (kitty, Hyprland, browsers) abort in the same few seconds on an AMD iGPU.

## gdb + debuginfod in batch mode
The skill's snippet uses `-ex 'set debuginfod enabled on'`. In `-batch` mode gdb asks "Enable debuginfod for this session?" BEFORE `-ex` runs, auto-answers N (no tty), and frames stay `??`. Use `-iex` instead:

```bash
core=$(mktemp -t crash-XXXXXX.core); trap 'rm -f "$core"' EXIT
coredumpctl dump <pid> --output="$core"
DEBUGINFOD_URLS="https://debuginfod.archlinux.org" timeout 280 \
  gdb -q /usr/bin/<exe> "$core" -batch -iex 'set debuginfod enabled on' -ex 'thread 1' -ex 'bt 8'
rm -f "$core"
```
First run downloads debuginfo (~3 min for mesa/libc); run it in the background and do journal work meanwhile. Verify `ls /tmp/crash-*.core` is empty afterwards.

## Journal after a reboot
If `uptime -s` is later than the crash, the crash-time journal is in the previous boot: `journalctl -b -1 -k` (check `journalctl --list-boots`). `-b 0` shows nothing relevant.
Kernel floods (hundreds of lines) — count and bucket with `grep | awk '{print substr($3,1,7)}' | sort | uniq -c` instead of printing them.

## Pattern: amdgpu GTT exhaustion
Signature: kernel `amdgpu ... *ERROR* amdgpu_vm_validate() failed` + `Not enough memory for command submission!`; crashing thread is Mesa `util_queue` worker: `abort` <- `amdgpu_ctx_set_sw_reset_status` (PIPE_UNKNOWN_CONTEXT_RESET, "The CS has been rejected") <- `amdgpu_cs_submit_ib`. Mesa aborts deliberately; it is not an app bug. All GPU clients die together (Hyprland aborts in `CHyprOpenGLImpl::begin` assert; kernel logs `VM memory stats ... non-zero when fini` per client).
Check `/sys/class/drm/card*/device/mem_info_{vram,gtt}_{total,used}`: Strix iGPU has ~512 MiB VRAM and a ~16 GiB GTT shared with RAM.
Trigger seen: ollama with `OLLAMA_VULKAN=1 OLLAMA_IGPU_ENABLE=1` treated GTT as free VRAM and loaded ~12 GiB. Look for `ollama`/`llama-server` memory-breakdown lines just before the crash. Fix: run ollama on CPU, smaller model/context (`-c`, `-np`, `-ub`), or cap GPU memory. Not an Omarchy bug; system RAM and OOM killer are irrelevant here.
