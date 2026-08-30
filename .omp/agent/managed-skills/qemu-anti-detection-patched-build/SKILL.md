---
name: qemu-anti-detection-patched-build
description: "Use when setting up the qemu-anti-detection (zhaodice/vm-anti-detection) patched QEMU + libvirt anti-detection VM on Arch Linux — building QEMU 10.2.2 with the anti-detection patch into /usr/local/bin, wiring libvirtd, and defining an undetectable VM XML with spoofed SMBIOS/CPU. Covers the silent-device-drop XML bug, ISO permission failures, and verification steps."
---

# qemu-anti-detection patched build + undetectable libvirt VM (Arch)

Verified end-to-end 2026-08 on Omarchy (Arch, AMD Ryzen AI 9 HX 370, kernel 7.1.9). Purpose: malware-analysis VM that sandbox-detecting samples can't easily identify as virtualized.

## Procedure (verified working)

1. **Packages**: `sudo pacman -S --noconfirm swtpm dmidecode` (libvirt, virt-manager, edk2-ovmf, glib2, ninja, base-devel usually already present). Keep the package QEMU installed — patched build only overlays /usr/local/bin, and libvirt probes `/usr/local/bin/qemu-system-x86_64` first for x86_64 (confirm via `sudo virsh capabilities | grep emulator`).
2. **libvirt**: `sudo systemctl enable --now libvirtd.service`, `sudo usermod -aG libvirt wils` (re-login needed for group), `sudo virsh net-start default && sudo virsh net-autostart default`.
3. **Build**:
   ```
   git clone --depth 1 https://github.com/zhaodice/qemu-anti-detection.git
   curl -fsSL -o qemu-10.2.2.tar.xz https://download.qemu.org/qemu-10.2.2.tar.xz
   tar xJf qemu-10.2.2.tar.xz && cd qemu-10.2.2
   git apply ../qemu-anti-detection/qemu-10.2.2.patch   # newest patch; applies cleanly to 10.2.2
   ./configure --target-list=x86_64-softmmu             # --target-list avoids building all arches
   make -j$(nproc)                                      # ~90s on 24 threads
   sudo make install                                    # → /usr/local/bin/qemu-system-x86_64
   ```
   Verify patch took: `strings /usr/local/bin/qemu-system-x86_64 | grep -c ASUS` (≈75) or grep source (`hw/ide/core.c` → "ASUS HARDDISK", `hw/input/ps2.c` → "ASUS PS/2 Keyboard").
4. **VM XML** (see repo README `configs`/guide for the full anti-detection block: hyperv vendor_id=GenuineIntel, kvm hidden, vmport off, smm on, host-passthrough cpu with hypervisor disabled, SMBIOS spoofing, `-cpu host,family=6,model=158,stepping=2,model_id=Intel(R) Core(TM) i9-12900K CPU @ 2.60GHz,...,hypervisor=off`). Arch-specific corrections:
   - OVMF paths: `/usr/share/edk2/x64/OVMF_CODE.4m.fd` and `/usr/share/edk2/x64/OVMF_VARS.4m.fd` (the `.4m` suffix; guide's bare `.fd` paths don't exist on Arch).
   - Machine: `pc-q35-10.2` to match the built QEMU.
   - `<smbios mode="sysinfo"/>` requires a `<sysinfo type="smbios">` block with bios/system/baseBoard entries or define fails.
5. **Storage**: put disk + ISOs under `/var/lib/libvirt/images/` (world-traversable). NOT under `/tmp` (tmpfs, wiped on reboot) and NOT under `~/Downloads` — see gotcha #2. `cp --sparse=always` keeps a 50G raw image at 0 real bytes.
6. **Define/start**: `virsh undefine --nvram <name>` (plain undefine fails with "Cannot undefine domain with NVRAM/varstore"), then `virsh define vm.xml`, `virsh start <name>`. Attach Windows ISO as a second SATA cdrom with `<boot order="1"/>`, disk `<boot order="2"/>`, so the installer boots first.

## Gotcha #1 — devices silently dropped by virsh define (critical)

**Symptom**: `virsh define` returns success, VM starts, but there's no disk/network — the guest can never boot an OS. `sudo virsh dumpxml <name>` shows only auto-generated controllers/emulator/input/watchdog/memballoon; `<disk>` and `<interface>` are gone.

**Cause**: any device element (`<controller>`, `<disk>`, `<interface>`) placed as a direct child of `<domain>` instead of inside `<devices>` is a schema violation. libvirt's parser hits the error, **silently discards the offending element and everything after it**, and still reports "defined". This is exactly what the original guide XML does (it has no `<devices>` wrapper).

**Fix/check**: wrap ALL devices in `<devices>...</devices>` and ALWAYS run `virt-xml-validate vm.xml` before `virsh define` — it catches what define swallows. Also drop explicit `<address>` on disks/interfaces and declare `<controller type="sata" index="0"/>` inside `<devices>` to let libvirt assign addresses.

## Gotcha #2 — libvirt-qemu cannot read files under $HOME

**Symptom**: VM fails to start: `qemu-system-x86_64: -blockdev ... Could not open '/home/wils/Downloads/X.iso': Permission denied`, even when the file itself is world-readable.

**Cause**: QEMU runs as `libvirt-qemu`; `/home/wils` is `drwx------` so the process can't traverse the home dir regardless of file perms.

**Fix**: copy ISOs/disks to `/var/lib/libvirt/images/` (755, root-owned, world-readable files) and reference those paths in the XML. Don't chmod the home dir.

## Verification after start

- `pgrep -af 'qemu-system-x86_64.*UndetectableVM'` → must be `/usr/local/bin/...` (patched), stable after 10+s.
- Process args must include: `hypervisor=off`, `hv-vendor-id=GenuineIntel`, `kvm=off`, `vmport=off`, `smm=on`, `model_id=Intel(R)...`, `-smbios` chain.
- `sudo virsh dumpxml <name> | grep -E '<disk|<interface'` → both present.

## Known limits (guide's own, unpatched)

- RDTSC timing attacks (needs WCharacter/RDTSC-KVM-Handler host kernel patch).
- WMI sensor classes (`Win32_Fan`, `CIM_TemperatureSensor`, etc.) return nothing — detectable.
- Vanguard (Riot) not bypassed.
