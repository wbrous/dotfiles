---
name: qemu-anti-detection-vm-sensor-tsc-hardening
description: "Use when hardening a qemu-anti-detection/libvirt Windows analysis VM against RDTSC/timing detection and missing WMI sensor classes (Win32_Fan, CIM_TemperatureSensor) — covers pinning the guest TSC to the host invariant frequency (tsc-frequency from dmesg, never guess), authoring+compiling a thermal SSDT with iasl and injecting via -acpitable so WMI sensors enumerate, and the libvirt 12.x dnsmasq:options broken-extension dead end (use host tcpdump capture instead)."
---

# QEMU analysis-VM hardening: RDTSC/TSC pinning + WMI sensor SSDT

For the qemu-anti-detection libvirt VM (UndetectableVM on this Omarchy host). Two analysis-enabling hardening procedures plus one known dead end.

## 1. RDTSC / TSC frequency pinning

Goal: guest `rdtsc` reads stable and consistent with real hardware (no detectable drift).

- **NEVER guess the frequency.** `cpu max MHz` (lscpu) is the boost clock, NOT the invariant TSC — on this Ryzen AI 9 HX 370 it showed 5157 MHz but the real calibrated TSC is **1996.276 MHz**. A wrong `tsc-frequency=` is worse than none.
- Authoritative value (root): `dmesg | grep -iE "tsc: Detected|Refined TSC"` → `tsc: Refined TSC clocksource calibration: 1996.276 MHz` → use `1996276000`.
- Non-root measurement via tiny C (`__rdtsc()` around a 1s `CLOCK_MONOTONIC` sleep) is **unreliable** (caught C-state-scaled ~1.996 GHz that *looks* right but is coincidence-prone; kernel value is ground truth).
- Apply: append `,tsc-frequency=<hz>` INSIDE the `-cpu` qemu:arg value string in the domain XML (after `hypervisor=off`), `virsh define`, restart, verify in process: `ps aux | grep qemu-system | grep -oE "tsc-frequency=[0-9]+"`.
- Watch the quote: the value must stay inside the single `value='...'` arg — append before the closing quote.

## 2. WMI sensor fabrication via thermal SSDT (driver-free)

`Win32_Fan` / `CIM_TemperatureSensor` / `CIM_NumericSensor` are NOT registry-backed — they're instantiated by the WmiAcpi provider from ACPI thermal-zone/fan/sensor devices in DSDT/SSDT. Fix = inject a custom SSDT via QEMU `-acpitable`.

Steps:
1. `pacman -S acpica` (provides `iasl`).
2. Author `thermal.asl`: `DefinitionBlock("thermal.aml","SSDT",2,"ASUS ","Thermal",0x2021)` containing:
   - `ThermalZone (TZ0)` in `Scope(\_SB)` with `_TMP` (deciKelvin, e.g. 3181 = 45C), `_PSV`/`_AC0`/`_CRT`/`_TC1`/`_TC2`/`_TSP`, `_TZD` → `\_SB.PR00`.
   - `Device (FAN0)` `_HID` PNP0C0B with `_FPS` + `_FST`.
   - `Device (SEN0)` `_HID` PNP0C15 with `_STR` Unicode.
   - `Device (PR00)` `_HID` PNP0C0E.
3. **`_FPS` format gotcha (iasl 20251212 enforces):** outer `Package(5)` = [control-valid Integer, then one Package(5) PER STATE]. Per-state Package(5) = (control, speed_rpm, noise, power, flanking_RPS). All-Package form → "Integer required at index 0"; all-flat-Integer form → "Package required"; Package(4) states → "length 4, required minimum is 5". Correct:
   ```
   Return (Package (5) { 0x00010000,
     Package (5) {0,0,0,0,0}, Package (5) {1,2200,20,2,0},
     Package (5) {2,3200,26,3,0}, Package (5) {3,3900,30,4,0} })
   ```
4. `iasl -we thermal.asl` → `thermal.aml` (~348 bytes).
5. `cp thermal.aml /var/lib/libvirt/images/ssdt_thermal.aml; chown libvirt-qemu:libvirt-qemu`.
6. Domain XML `<qemu:commandline>`: add `<qemu:arg value="-acpitable"/>` + `<qemu:arg value="file=/var/lib/libvirt/images/ssdt_thermal.aml"/>`. Validate (`virt-xml-validate`), `virsh define`, restart.
7. Guest verify: `wmic path win32_fan get *` / `wmic path win32_temperature get *` should return rows (was "No instance(s) available").

## 3. Dead end: libvirt 12.x `<dnsmasq:options>` DNS logging

libvirt 12.6 `network.rng` **declares** `<dnsmasq:options>` (ns `http://libvirt.org/schemas/network/dnsmasq/1.0`) but the parser **rejects** it: "Expecting a namespace for element option" regardless of placement (direct `<network>` child, after `</dns>`, prefixed/unprefixed options). Don't fight it — for DNS/egress observability use a host-side tcpdump on virbr0 instead (see capture-detonation pattern below).

## 4. Host-side egress capture (the working replacement)

`capture-detonation.sh` pattern: run as root, capture on `virbr0` (guest's only network path) for N seconds:
- `tcpdump -i virbr0 -w detonation.pcap` (full pcap)
- `tcpdump -i virbr0 -nn -l 'udp port 53'` → dns-queries.txt (domain beacon surface)
- `tcpdump -i virbr0 -nn -lA 'tcp port 80 ...'` → http-requests.txt
- Note: idle guest = 0 packets (expected); don't read that as a tooling failure.

## 5. Per-detonation identity randomization

`randomize-vm.py` pattern: dump domain XML, regex-randomize MAC (`02-7e` even first byte), `<uuid>` + `-smbios type=1 uuid=`, inject `serial=` into `-smbios type=1/2/3` args (missing serial is itself a VM tell; append `,serial=<hex>` INSIDE the value before closing quote), disk `<serial>`, temp-file `virsh define`, destroy+start if running. Dry-test regexes against real config first; the `add_or_set_serial` helper must NOT add its own trailing quote (caller's regex group owns it) or you get `serial=X""`.

## Files/state (as of 2026-08-30, /tmp — ephemeral)
- `/tmp/undetectablevm-tsc.xml` — current live config (16GiB, 12 vCPU pinned, QXL, tsc-frequency, acpitable)
- `/tmp/randomize-vm.py`, `/tmp/capture-detonation.sh` — deliverables (move to persistent location if wanted)
- VM: UndetectableVM, qemu:///system, virtnetworkd must be enabled (see arch-libvirt-virtnetworkd-socket-missing skill)
