# Power, Thermals and Hardware on Linux

Hot/loud/hungry idle laptops: check the power profile before blaming processes.

## CPU hot / high power while idle

**Symptom:** Linux laptop (AMD/Framework/Omarchy) runs hot with loud fan and high power draw while apparently idle.

**Cause:** Often the power profile, not a runaway process: `performance` sets governor and EPP to `performance`, keeps boost on, and sets the ACPI platform profile to performance — idle cores sit near max clock (~4.7 GHz).

**Fix — read-only diagnosis first (run in parallel):**
```sh
powerprofilesctl get; powerprofilesctl list
cat /sys/devices/system/cpu/cpu0/cpufreq/{scaling_governor,energy_performance_preference}
cat /sys/firmware/acpi/platform_profile
cat /sys/devices/system/cpu/amd_pstate/status
grep MHz /proc/cpuinfo | sort -t: -k2 -nr | head
sensors   # k10temp Tctl, fan RPM — quantifies heat
ps -eo pid,ppid,pcpu,etimes,args --sort=-pcpu | head   # prefer over top -b (truncated/0% in sandbox)
```
Short-lived busy processes (e.g. many 100%-for-<1s `gh` invocations) indicate something polling — find the parent by sampling `ps` repeatedly; a single shot misses them.

**Fix to propose (do not run without user consent):** `powerprofilesctl set balanced` (or `power-saver`), then re-check `sensors`. If it reverts, find what sets the profile (keybind, Omarchy toggle, firmware).

**Pitfalls:** Do NOT `grep -r` over `~/.config/omarchy` — theme `.git` pack files dump binary garbage; restrict to `*.lua`, `*.conf`, `bin/`. A process (e.g. omp itself) at ~60% CPU also contributes, but performance mode amplifies it.

_Migrated from: linux-idle-cpu-hot-high-power-diagnosis_
