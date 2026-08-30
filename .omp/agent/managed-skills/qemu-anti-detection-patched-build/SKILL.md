---
name: qemu-anti-detection-patched-build
description: "Use when setting up the qemu-anti-detection (zhaodice/vm-anti-detection) patched QEMU + libvirt anti-detection VM on Arch Linux — building QEMU 10.2.2 with the anti-detection patch into /usr/local/bin, wiring libvirtd, and defining an undetectable VM XML with spoofed SMBIOS/CPU."
---

# qemu-anti-detection patched QEMU + VM setup (Arch)

Build a VM that hides virtualization traces (ASUS device names, spoofed SMBIOS, hidden hypervisor) per `so1icitx/vm-anti-detection` guide, using `zhaodice/qemu-anti-detection` patches. Verified working 2026-08 on Omarchy/Arch (AMD Ryzen AI 9 HX 370), QEMU 10.2.2 patch applied cleanly, VM started with all anti-detection args active.

## Patch/version selection
- Patches available: 6.2.0, 7.0.0, 7.2.0, 8.0.2, 8.0.5, 8.1.0, 8.2.0, **10.2.2** (newest).
- Pick the closest patch to a real QEMU release from https://download.qemu.org/. Keep the package-managed QEMU installed (runtime deps) — patched build installs to `/usr/local/bin` and shadows it.

## Build steps
```bash
mkdir -p /tmp/vm-anti-detect && cd /tmp/vm-anti-detect
git clone --depth 1 https://github.com/zhaodice/qemu-anti-detection.git
curl -fsSL -o qemu-10.2.2.tar.xz https://download.qemu.org/qemu-10.2.2.tar.xz
tar xJf qemu-10.2.2.tar.xz
cd qemu-10.2.2
git apply ../qemu-anti-detection/qemu-10.2.2.patch   # must print clean; verify with grep ASUS hw/input/ps2.c
./configure --target-list=x86_64-softmmu              # x86_64-only target keeps build ~90s on 24 cores
cd build && make -j$(nproc)
sudo make install
/usr/local/bin/qemu-system-x86_64 --version           # → QEMU emulator version 10.2.2
```
Arch deps: `base-devel glib2 ninja python` (already present typically). Install `swtpm dmidecode` too (guide lists them; swtpm only needed if XML adds a TPM).

## libvirt wiring
```bash
sudo systemctl enable --now libvirtd.service
sudo usermod -aG libvirt,kvm $(whoami)   # new group needs re-login; use sudo virsh until then
sudo virsh net-start default && sudo virsh net-autostart default
```
Key: libvirt resolves x86_64 emulator to `/usr/local/bin/qemu-system-x86_64` (its capabilities probe prefers /usr/local/bin) — verify with `sudo virsh capabilities | grep -oE '<emulator>[^<]+'` and `virsh dumpxml VM | grep emulator`.

## VM XML gotchas (deviations from the guide — guide is broken verbatim on Arch)
1. **OVMF paths**: Arch ships `/usr/share/edk2/x64/OVMF_CODE.4m.fd` and `OVMF_VARS.4m.fd` — the guide's `/usr/share/edk2/x64/OVMF_CODE.fd` does not exist. nvram target: `/var/lib/libvirt/qemu/nvram/UndetectableVM_VARS.fd`.
2. **Machine type must match built QEMU**: with 10.2.2 use `pc-q35-10.2` (check `qemu-system-x86_64 -machine help | grep pc-q35`).
3. **`<smbios mode="sysinfo"/>` requires a sibling `<sysinfo type="smbios">` block** or `virsh define` fails — the guide omits it. (Alternative: `mode="host"` without sysinfo block.)
4. **qemu:arg quoting**: use proper `value="type=0,version=UX305UA.201"` form, not the guide's malformed `value="type=0",version="..."`.
5. CPU: `<cpu mode="host-passthrough" check="none"><feature policy="disable" name="hypervisor"/></cpu>` + commandline `-cpu host,family=6,model=158,stepping=2,model_id=...,hypervisor=off`.
6. SATA disk (`bus="sata"`, serial) + `e1000e` NIC — avoids VirtIO VM-specific driver strings.
7. User said malware analysis; a coherent AMD model_id (e.g. `AMD Ryzen 9 7950X`) beats the guide's Intel i9 on AMD hosts.

## Verification (do all three)
1. `sudo virsh start UndetectableVM` → `ps aux | grep qemu-system` must show: `/usr/local/bin/qemu-system-x86_64`, `hypervisor=off`, `hv-vendor-id=GenuineIntel`, `kvm=off`, `vmport=off`, `model_id=Intel(R)...`, multiple `-smbios` args.
2. `strings /usr/local/bin/qemu-system-x86_64 | grep -c ASUS` → 75 (device-name renames compiled in).
3. In guest: `systeminfo`, `wmic path Win32_BIOS` → ASUS/Intel.

## Known limits (guide acknowledges)
RDTSC timing and WMI sensor classes (`Win32_Fan`, `Win32_CacheMemory`, `CIM_TemperatureSensor` etc.) are NOT patched — sandbox-detecting malware can still use them. Vanguard not bypassed.

## Pitfall
If working dir is `/tmp` (tmpfs), the raw disk image is RAM-backed and wiped on reboot — for a persistent VM put disk.img + XML on a real filesystem.
