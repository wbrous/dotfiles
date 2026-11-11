# Quickshell / Omarchy shell crash diagnosis

Supplements general crash procedure: where quickshell's own crash reports live and what to correlate.

## Evidence beyond coredumpctl

- Quickshell writes its own crash dir: `~/.cache/quickshell/crashes/<instance-id>/` containing `report.txt` (version, build flags, GPU, env) and `log.qslog.log` (full runtime log, can be MBs). The instance id is in the journal line `Further crash information is stored under ...`.
- Read the tail: `tail -c 6000 log.qslog.log | strings` — the last events before the abort (e.g. a toplevel/appid being registered) show what the shell was doing.
- The journal for the crashed boot holds the fatal Qt message (`pure virtual method called`, `Terminate called without active C++ exception`) and quickshell lines: `Quickshell crashed within 10 seconds of launching. Not restarting to avoid a crash loop.` / `Omarchy shell exited with status 255; relaunching.`
- `coredumpctl info` shows the crashing thread name (e.g. `QQuickPixmaRea` = QML image reader) as the comm — that's the thread, not "quickshell".

## Gotchas

- After a reboot, `coredumpctl info` timestamps/boot IDs refer to the previous boot: use `journalctl -b -1`.
- Check `/var/log/pacman.log` timing: a quickshell upgrade AFTER the crash explains gdb's "doesn't match build-id" warnings but did not cause the crash.
- `gdb` batch mode declines the debuginfod prompt if `set debuginfod enabled on` comes after file load — pass with `-iex 'set debuginfod enabled on'`. Arch has no `quickshell-debug` package, so quickshell frames stay unsymbolized (say so; don't invent names).
- Compare `coredumpctl list | grep quickshell` across dumps: check whether startup-time crashes form a pattern before calling them the same bug.

_Migrated from: diagnose-crash-quickshell-omarchy-shell_
