---
name: diagnose-crash-quickshell-omarchy-shell
description: "Use when quickshell (Omarchy shell, quickshell -n -p /usr/share/omarchy/shell) crashes; where its own crash report/log live and what to correlate. Supplements diagnose-crash."
---

Supplements `skill://diagnose-crash` for quickshell / Omarchy shell crashes.

## Evidence sources beyond coredumpctl
- Quickshell writes its own crash dir: `~/.cache/quickshell/crashes/<instance-id>/` containing `report.txt` (version, build flags, GPU, env) and `log.qslog.log` (full runtime log, can be MBs). The instance id is in the journal line `Further crash information is stored under ...`.
  - Read the tail with `tail -c 6000 log.qslog.log | strings` — the last events before the abort show what the shell was doing (e.g. a toplevel/appid being registered).
- The journal for the *crashed boot/session* (`journalctl -b -1 --since/--until`, grep `omarchy-shell|quickshell|coredump`) holds the fatal Qt message (e.g. `pure virtual method called`, `Terminate called without active C++ exception`) and quickshell's lines:
  - `Quickshell crashed within 10 seconds of launching. Not restarting to avoid a crash loop.`
  - `Omarchy shell exited with status 255; relaunching.` (the omarchy-shell wrapper relaunches it)
- `coredumpctl info` shows the crashing thread name (e.g. `QQuickPixmapRea` = QML image reader), which is the PID's comm, not "quickshell".

## Gotchas
- If a reboot happened after the crash, `coredumpctl info` timestamps/boot IDs refer to the previous boot: use `journalctl -b -1`.
- Check `/var/log/pacman.log` timing: an upgrade of quickshell AFTER the crash explains gdb's "doesn't match build-id" warnings but did not cause the crash.
- `gdb` batch mode declines the debuginfod prompt if `set debuginfod enabled on` comes after file load; use `-iex 'set debuginfod enabled on'`. Arch has no `quickshell-debug` package, so quickshell frames stay unsymbolized (say so; don't invent names).
- Compare against earlier quickshell dumps (`coredumpctl list | grep quickshell`) to see whether startup-time crashes form a pattern, and compare stacks before calling them the same bug.
