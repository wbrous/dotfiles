# QEMU Anti-Detection VM

Build zhaodice/qemu-anti-detection patched QEMU (hides QEMU/KVM traces from malware sandbox detection) into /usr/local/bin and configure a libvirt domain that passes as physical hardware.

## Building patched QEMU

```bash
mkdir -p /tmp/vm-anti-detect && cd /tmp/vm-anti-detect
git clone --depth 1 https://github.com/zhaodice/qemu-anti-detection.git
curl -fsSLO https://download.qemu.org/qemu-10.2.2.tar.xz   # newest patch in repo: qemu-10.2.2.patch
tar xJf qemu-10.2.2.tar.xz && cd qemu-10.2.2
git apply ../qemu-anti-detection/qemu-10.2.2.patch
./configure --target-list=x86_64-softmmu                    # only the target we need
make -j$(nproc)
sudo make install                                           # /usr/local/bin
/usr/local/bin/qemu-system-x86_64 --version
```

Keep package QEMU (`pacman -S qemu`) for runtime deps; the patched binary shadows it. `virsh capabilities` shows `<emulator>/usr/local/bin/qemu-system-x86_64` automatically. Verify the patch: `grep -n '"ASUS PS/2 Keyboard"' hw/input/ps2.c`, `strings /usr/local/bin/qemu-system-x86_64 | grep -c ASUS`. `sudo systemctl enable --now libvirtd.service`; `sudo usermod -aG libvirt,kvm wils` (takes effect after re-login); `sudo virsh net-start default; sudo virsh net-autostart default`.

_Migrated from: qemu-anti-detection-patched-build_

## VM XML gotchas (all hit in practice)

1. `virsh define` SILENTLY DROPS devices after any schema-invalid element (e.g. a `<controller>` outside `<devices>`). Always `virt-xml-validate file.xml` first, then verify with `virsh dumpxml NAME | grep -cE '<disk|<interface'` after define.
2. All devices go inside `<devices>`; declare `<controller type="sata" index="0"/>` explicitly; skip fixed `<address>` elements, let libvirt assign them.
3. `<smbios mode="sysinfo"/>` requires a `<sysinfo type="smbios">` block (bios/system/baseBoard).
4. Arch OVMF paths have `.4m` suffix: `/usr/share/edk2/x64/OVMF_CODE.4m.fd` and `OVMF_VARS.4m.fd`.
5. Machine type must exist in the PATCHED QEMU: `pc-q35-10.2` (`qemu-system-x86_64 -machine help | grep pc-q35`).
6. libvirt-qemu must traverse storage paths: `~/...` fails with Permission denied (home is `drwx------`). Put disks/ISOs in `/var/lib/libvirt/images/` (copy with `sudo cp`, disk with `sudo cp --sparse=always`).
7. The guide's XML has NO graphics/video — add the SPICE stack: `<graphics type='spice' autoport='yes'>`, `<video><model type='qxl' .../></video>`, USB tablet, virtio-serial controller + spicevmc channel, ich9 sound + spice audio, 2× spicevmc redirdev, PTY serial/console.
8. Boot order for install: cdrom `order="1"`, disk `order="2"` (both SATA).
9. `virsh undefine` on UEFI needs `--nvram`; add `--remove-all-storage` to also delete the disk.
10. Verify anti-detection args live: `ps -eo args | grep qemu-system | grep UndetectableVM` → `hypervisor=off`, `hv-vendor-id=GenuineIntel`, `kvm=off`, `model_id=Intel(R) Core(TM) i9-12900K CPU @ 2.60GHz`, `-smbios type=0..17`, `vmport=off`, `smm=on`.

Anti-detection CPU/SMBIOS commandline (qemu:commandline), plus domain `<cpu mode='host-passthrough'><feature policy='disable' name='hypervisor'/></cpu>`, `<kvm><hidden state='on'/></kvm>`, `<hyperv mode='custom'>` with `vendor_id value='GenuineIntel'`, `<vmport state='off'/>`:

```xml
<qemu:arg value="-smbios"/> <qemu:arg value="type=0,version=UX305UA.201"/>
<qemu:arg value="-smbios"/> <qemu:arg value="type=1,manufacturer=ASUS,product=UX305UA,version=2021.1"/>
<qemu:arg value="-smbios"/> <qemu:arg value="type=2,manufacturer=Intel,version=2021.5,product=Intel i9-12900K"/>
<qemu:arg value="-smbios"/> <qemu:arg value="type=3,manufacturer=XBZJ"/>
<qemu:arg value="-smbios"/> <qemu:arg value="type=17,manufacturer=KINGSTON,loc_pfx=DDR5,speed=4800,serial=000000,part=0000"/>
<qemu:arg value="-smbios"/> <qemu:arg value="type=4,manufacturer=Intel,max-speed=4800,current-speed=4800"/>
<qemu:arg value="-cpu"/> <qemu:arg value="host,family=6,model=158,stepping=2,model_id=Intel(R) Core(TM) i9-12900K CPU @ 2.60GHz,vmware-cpuid-freq=false,enforce=false,host-phys-bits=true,hypervisor=off"/>
<qemu:arg value="-machine"/> <qemu:arg value="q35,kernel_irqchip=on"/>
```

Spoofed values are Intel while the host is AMD — intentional; use a coherent AMD string if the guest must look self-consistent. Repo-documented limits (don't promise more): RDTSC timing and WMI sensor classes (`Win32_Fan`, `CIM_TemperatureSensor`) are NOT patched.

_Migrated from: qemu-anti-detection-patched-build_

## Realistic device IDs in the Windows guest

**Symptom:** Windows shows "Standard PS/2 Keyboard", "PS/2 Compatible Mouse", "Generic Non-PnP Monitor".

**Cause/Fix:**

- Input: Windows names PS/2 devices by its inbox class driver regardless of QEMU strings — only USB HID gets brand names. The patched QEMU's USB HID descriptors are already ASUS-branded, so `<input type="tablet/mouse/keyboard" bus="usb"/>` yields ASUS names (`ps aux | grep qemu-system | grep -oE '"driver":"usb-(kbd|mouse|tablet)"'`). libvirt auto-adds PS/2 fallbacks — normal, leave them. USB VID stays QEMU's 0x0627; driver shows generic "HID Keyboard Device" — good enough.
- Monitor: `qxl-vga` has NO `edid` property (`-device qxl-vga,edid=on` → "Property 'qxl-vga.edid' not found"); it depends on the SPICE client sending EDID, which virt-manager often doesn't → "Generic Non-PnP Monitor". Plain `VGA` has `edid` default-on via patched `hw/display/edid-generate.c` → vendor `DEL`, "DEL Monitor", Windows shows a real Dell PnP monitor. libvirt XML: `<model type="vga" heads="1" primary="yes"/>` — do NOT set `vgamem` ("vgamem attribute only supported for video type qxl"). Tradeoff: loses QXL 2D accel; acceptable for analysis VMs.
- Audio: `<sound model="ich9"/>` is already a genuine Intel HDA identifier — leave it.
- Detaching the installer ISO: remove the `<disk type="file" device="cdrom">` element and bump the hard disk boot order to 1. Verify: `ps aux | grep qemu-system` shows only `disk.img`, no `.iso`.

Apply: `virt-xml-validate`, `virsh destroy`, `virsh define`, `virsh start`; verify with `virsh dumpxml --inactive` (plain dumpxml on a running domain shows stale live config). `/tmp/vm-anti-detect/` is ephemeral tmpfs — regenerate XML from the persistent domain if gone.

_Migrated from: qemu-anti-detection-vm-device-ids_

## Network debugging (silent NIC / dead DNS)

**Symptom:** Guest has no network, "unidentified network", or "DNS address could not be found".

**Triage first:** `sudo tcpdump -i virbr0 -nn -e` for 15-20s. Zero frames from guest MAC → guest NIC silent (link-down/driver). DHCP DISCOVER with no OFFER → host ufw dropping DHCP at INPUT. No port-53 packets at all → stale Windows DNS state. Also check: `virsh net-list --all`, `ip -br addr show virbr0` (UP 192.168.122.1/24), `virsh net-dhcp-leases default`, `bridge link show master virbr0`.

**Cause 1 — host ufw drops guest DHCP (the big one):** ufw INPUT/FORWARD policies are `drop` with no libvirt rule allowing UDP 67. Fix (persistent):

```bash
sudo ufw allow in on virbr0
sudo ufw allow out on virbr0
sudo ufw route allow in on virbr0
sudo ufw route allow out on virbr0
```

Then bounce the guest NIC so Windows re-runs DHCP:

```bash
MAC="f0:bc:8e:cd:6e:ec"   # from `virsh domiflist UndetectableVM`
sudo virsh detach-interface UndetectableVM network --config --live --mac "$MAC"
sudo virsh attach-interface UndetectableVM network default --model e1000 --mac "$MAC" --live --config
sudo virsh net-dhcp-leases default    # confirm a lease appears
```

**Cause 2 — NIC model silently dead (`e1000e`):** adapter present in Windows but transmits nothing. Swap to `<model type='e1000'/>` (Intel 82540EM, bulletproof under hidden-hypervisor), redefine, restart.

**Cause 3 — stale guest DNS after libvirt network churn:** after `default` was destroyed/redefined, the guest sends zero DNS queries though dnsmasq is fine (verify from host with a python UDP query to 192.168.122.1:53 — `dig`/`nslookup` often not installed). Fix: same NIC bounce as Cause 1.

Host notes: `sudo -n virsh` fails (libvirt group needs re-login; use `sudo virsh` via tty, fingerprint-gated); virbr0 DOWN with guest off is normal; after `net-destroy`/`net-start` the tap is recreated with a new vnet index and Windows may need the NIC bounce.

_Migrated from: qemu-anti-detection-vm-network-debug_

## Performance tradeoffs and boost recipe

**Symptom:** VM feels laggy.

**Cause:** The lag source is the display, not cores/RAM: unaccelerated `VGA` (chosen for the Dell-EDID monitor name) redraws the whole desktop over SPICE. `qxl-vga` is smooth but has no EDID → "Generic Non-PnP Monitor". Flip `model type` back to `vga` before sandbox tests that check the monitor name (cores/RAM/pinning stay). Renaming virtio drivers does NOT hide virtualization: virtio exposes PCI vendor `0x1AF4` at hardware level; changing IDs means forking QEMU tables + Windows driver PCI match tables + driver signing, and virtio capability structures remain a giveaway. Out of scope.

**Applied boost (Ryzen AI 9 HX 370, 24 threads/30GiB host):** 16 GiB (`16777216` KiB) + 12 vCPU pinned to physical cores 0-11 with emulatorpin on CPU 12, `<topology sockets="1" dies="1" cores="6" threads="2"/>`, video back to `qxl` (ram/vram 65536, vgamem 16384). Apply: `virt-xml-validate`, `destroy && define && start`, verify via dumpxml greps, `ps -eo args | grep -oE 'smp [0-9]+|"driver":"qxl-vga"'`, `taskset -pc <pid>`. Caution: 16 GiB leaves ~5.6 GiB host-available; drop to 12 GiB (`12582912` KiB) if the host swaps. Windows re-detects CPU/RAM/QXL on next boot; chkdsk after unclean destroy is normal.

_Migrated from: qemu-anti-detection-vm-performance-tradeoffs_

## Hardening: RDTSC pinning + WMI sensor SSDT

**Symptom:** Pafish-style probes flag RDTSC drift and missing `Win32_Fan` / `CIM_TemperatureSensor` classes.

**Fix 1 — TSC pinning:** NEVER guess the frequency (lscpu boost clock is NOT the invariant TSC; Ryzen AI 9 HX 370 showed 5157 MHz vs real 1996.276 MHz). Authoritative value (root): `dmesg | grep -iE "tsc: Detected|Refined TSC"` → `tsc: Refined TSC clocksource calibration: 1996.276 MHz` → use `1996276000`. Non-root C `__rdtsc()` measurement is unreliable. Append `,tsc-frequency=<hz>` INSIDE the `-cpu` qemu:arg value string (after `hypervisor=off`, before the closing quote), define, restart, verify via `ps aux | grep -oE "tsc-frequency=[0-9]+"`.

**Fix 2 — thermal SSDT (driver-free):** WMI sensor classes are instantiated by WmiAcpi from ACPI thermal/fan/sensor devices, so inject a custom SSDT via `-acpitable`:

1. `pacman -S acpica` (provides `iasl`).
2. Author `thermal.asl`: `DefinitionBlock("thermal.aml","SSDT",2,"ASUS ","Thermal",0x2021)` with `ThermalZone (TZ0)` (`_TMP` deciKelvin, `_PSV`/`_AC0`/`_CRT`/`_TC1`/`_TC2`/`_TSP`, `_TZD` → `\_SB.PR00`), `Device (FAN0)` `_HID` PNP0C0B with `_FPS` + `_FST`, `Device (SEN0)` `_HID` PNP0C15, `Device (PR00)` `_HID` PNP0C0E.
3. `_FPS` gotcha (iasl enforces): outer `Package(5)` = [control-valid Integer, then one Package(5) PER STATE]; per-state Package(5) = (control, speed_rpm, noise, power, flanking_RPS):
   ```
   Return (Package (5) { 0x00010000,
     Package (5) {0,0,0,0,0}, Package (5) {1,2200,20,2,0},
     Package (5) {2,3200,26,3,0}, Package (5) {3,3900,30,4,0} })
   ```
4. `iasl -we thermal.asl` → `thermal.aml`; `cp` to `/var/lib/libvirt/images/ssdt_thermal.aml`, `chown libvirt-qemu:libvirt-qemu`.
5. Domain XML: `<qemu:arg value="-acpitable"/>` + `<qemu:arg value="file=/var/lib/libvirt/images/ssdt_thermal.aml"/>`. Validate, define, restart. Guest verify: `wmic path win32_fan get *` should return rows.

**Dead end — libvirt 12.x `<dnsmasq:options>`:** `network.rng` declares it but the parser rejects it ("Expecting a namespace for element option") regardless of placement. Don't fight it; use host-side tcpdump on virbr0 for DNS/egress observability. Per-detonation identity randomization (`randomize-vm.py` pattern): randomize MAC, domain UUID, SMBIOS serials (inject `serial=` inside the arg value before the closing quote — a missing serial is itself a VM tell), disk serial.

_Migrated from: qemu-anti-detection-vm-sensor-tsc-hardening_
