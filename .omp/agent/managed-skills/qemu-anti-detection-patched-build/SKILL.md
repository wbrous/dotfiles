---
name: qemu-anti-detection-patched-build
description: "Build zhaodice/qemu-anti-detection patched QEMU (hides QEMU/KVM traces from malware sandbox-detection) into /usr/local/bin and configure a libvirt VM with anti-detection XML — including the silent device-drop, OVMF path, permission, and missing-graphics gotchas that break the stock guide. Use when setting up an undetectable VM for malware analysis."
---

# QEMU Anti-Detection Patched Build + Undetectable VM

Build a patched QEMU (zhaodice/qemu-anti-detection) that renames QEMU devices to "ASUS", masks SMBIOS/CPUID/hypervisor, and configure a libvirt domain that passes as physical hardware. Legit use: malware analysis (samples that refuse to run in sandboxes). The repo README mentions anti-cheat bypass — same techniques; user's intent governs.

## Build patched QEMU

```bash
mkdir -p /tmp/vm-anti-detect && cd /tmp/vm-anti-detect
git clone --depth 1 https://github.com/zhaodice/qemu-anti-detection.git
curl -fsSLO https://download.qemu.org/qemu-10.2.2.tar.xz   # newest patch in repo: qemu-10.2.2.patch
tar xJf qemu-10.2.2.tar.xz && cd qemu-10.2.2
git apply ../qemu-anti-detection/qemu-10.2.2.patch          # cleanly applies to the .tar.xz (no git repo needed)
./configure --target-list=x86_64-softmmu                    # only the target we need — much faster
make -j$(nproc)
sudo make install                                           # installs to /usr/local/bin
/usr/local/bin/qemu-system-x86_64 --version                 # verify
```

- **Keep the package-managed QEMU** (`pacman -S qemu`) for runtime deps; the patched binary at `/usr/local/bin` shadows it.
- **libvirt picks up /usr/local/bin automatically**: `virsh capabilities` shows `<emulator>/usr/local/bin/qemu-system-x86_64` for x86_64. No qemu.conf change needed.
- Verify the patch landed: `grep -n '"ASUS PS/2 Keyboard"' hw/input/ps2.c`, `strings /usr/local/bin/qemu-system-x86_64 | grep -c ASUS`.

## libvirtd

```bash
sudo systemctl enable --now libvirtd.service
sudo usermod -aG libvirt,kvm wils     # takes effect only after re-login; use sudo virsh until then
sudo virsh net-start default; sudo virsh net-autostart default
```

## VM XML — gotchas that break the stock guide (all hit in practice)

1. **`virsh define` SILENTLY DROPS devices after any schema-invalid element.** A `<controller>` placed outside `<devices>` (as the guide's XML does) causes the disks + interface to vanish from the defined domain with NO error. Always run `virt-xml-validate file.xml` first; always verify with `virsh dumpxml NAME | grep -cE '<disk|<interface'` after define. Symptom: VM starts, boots nowhere, no disk in process args.
2. **All devices go inside `<devices>`**: controllers, disks, interface, graphics, video, etc. Declare `<controller type="sata" index="0"/>` explicitly; skip fixed `<address>` elements and let libvirt assign them.
3. **`<smbios mode="sysinfo"/>` requires a `<sysinfo type="smbios">` block** (bios/system/baseBoard entries), or define fails/drops it.
4. **Arch OVMF paths have `.4m` suffix**: `/usr/share/edk2/x64/OVMF_CODE.4m.fd` and `OVMF_VARS.4m.fd` (guide's `/usr/share/edk2/x64/OVMF_CODE.fd` doesn't exist on Arch).
5. **Machine type must exist in the PATCHED QEMU**: use `pc-q35-10.2` for QEMU 10.2.2 (`qemu-system-x86_64 -machine help | grep pc-q35`).
6. **libvirt-qemu user must be able to traverse storage paths.** `~/...` fails at VM start: `Could not open ... Permission denied` (home is `drwx------`). Put disks/ISOs in `/var/lib/libvirt/images/` (world-traversable). Copy ISO with `sudo cp`, disk with `sudo cp --sparse=always` (50G raw stays 0-byte actual).
7. **The guide's XML has NO graphics/video** → virt-manager: "no graphical interface configured for guest". Add the SPICE stack: `<graphics type='spice' autoport='yes'><listen type='address'/><image compression='off'/></graphics>`, `<video><model type='qxl' ram='65536' vram='65536' vgamem='16384' heads='1' primary='yes'/></video>`, `<input type='tablet' bus='usb'/>`, `<controller type='virtio-serial' index='0'/>` + `<channel type='spicevmc'><target type='virtio' name='com.redhat.spice.0'/></channel>`, `<sound model='ich9'/>`, `<audio id='1' type='spice'/>`, 2× `<redirdev bus='usb' type='spicevmc'/>`, PTY `<serial>`/`<console>`.
8. **Boot order for install**: cdrom `boot order="1"`, disk `boot order="2"` (both SATA: sda disk, sdb cdrom).
9. **`virsh undefine` on a UEFI domain needs `--nvram`**; add `--remove-all-storage` to also delete the disk image (use when user asks to remove a scratch VM).
10. Verify the running process carries the anti-detection args: `ps -eo args | grep qemu-system | grep UndetectableVM` → look for `hypervisor=off`, `hv-vendor-id=GenuineIntel`, `kvm=off`, `model_id=Intel(R) Core(TM) i9-12900K CPU @ 2.60GHz`, `-smbios type=0..17`, `vmport=off`, `smm=on`.

## Anti-detection CPU/SMBIOS commandline (qemu:commandline)

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

Plus domain `<cpu mode='host-passthrough'><feature policy='disable' name='hypervisor'/></cpu>`, `<kvm><hidden state='on'/></kvm>`, `<hyperv mode='custom'>` with `vendor_id value='GenuineIntel'`, `<vmport state='off'/>`. Spoofed values are Intel while this host is AMD — intentional; consider a coherent AMD model string if the guest must look self-consistent.

## Limits (repo-documented, don't promise more)

RDTSC timing and WMI sensor classes (`Win32_Fan`, `CIM_TemperatureSensor`, etc.) are NOT patched — tools like Pafish can still flag them. Only "two traces" claimed by the guide.
