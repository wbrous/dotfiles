---
name: linux-idle-cpu-hot-high-power-diagnosis
description: "Use when Linux laptop (AMD/Framework/Omarchy) CPU runs hot, loud fan, high power while idle; check power profile before blaming processes."
---

## Recipe: "CPU hot / high power but nothing is happening"

Do these in parallel, read-only first:

1. `powerprofilesctl get` and `powerprofilesctl list`. If it says `performance`, that is the likely cause: it sets governor and EPP to `performance`, keeps boost on and sets the ACPI platform profile to performance. Idle cores then sit near max clock (~4.7 GHz).
   - Confirm: `cat /sys/devices/system/cpu/cpu0/cpufreq/{scaling_governor,energy_performance_preference}`, `/sys/firmware/acpi/platform_profile`, `cat /sys/devices/system/cpu/amd_pstate/status`, and `grep MHz /proc/cpuinfo | sort -t: -k2 -nr | head`.
2. `sensors` (k10temp Tctl, fan RPM) to quantify heat.
3. `ps -eo pid,ppid,pcpu,etimes,args --sort=-pcpu | head`. Prefer this over `top -b` (output was truncated and showed 0% in the sandbox). `pidstat` may be absent.
4. Short-lived busy processes, such as many `gh` invocations at 100% for under 1s, indicate something polling. Find the parent by sampling `ps` repeatedly. A single-shot sample often misses them.

Fix to propose (do not run without user consent): `powerprofilesctl set balanced` (or `power-saver`). Then re-check `sensors`. If it reverts, find what sets the profile (keybind, Omarchy toggle, firmware).

Pitfalls:
- Do NOT `grep -r` over `~/.config/omarchy`. It contains theme `.git` pack files and dumps binary garbage. Restrict to `*.lua`, `*.conf`, `bin/`.
- Report that a process (e.g. omp itself) using ~60% CPU also contributes, but that performance mode amplifies it.
