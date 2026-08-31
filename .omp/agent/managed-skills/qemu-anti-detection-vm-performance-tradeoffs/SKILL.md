---
name: qemu-anti-detection-vm-performance-tradeoffs
description: "Use when the UndetectableVM (qemu-anti-detection patched QEMU + libvirt on Omarchy) feels laggy and the user wants more cores/RAM, a faster display, or asks whether virtio drivers can be renamed/rebranded to bypass detection. Covers why unaccelerated VGA is the lag source, the QXL-vs-VGA EDID tradeoff, why renaming virtio drivers does NOT hide virtualization (PCI vendor 0x1AF4 is hardware-level), and the concrete applied performance-boost recipe (16GiB/12 vCPU pinned/QXL) with exact XML."
---

# UndetectableVM performance: tradeoffs and the applied boost recipe

Context: `UndetectableVM` = qemu-anti-detection patched QEMU 10.2.2 (`/usr/local/bin/qemu-system-x86_64`) + libvirt domain on Omarchy (AMD Ryzen AI 9 HX 370, 24 threads/30GiB).

## The lag source: display, not cores/RAM

- Unaccelerated `VGA` (chosen for the Dell-EDID monitor name) redraws the whole desktop over SPICE → feels laggy regardless of allocation.
- `qxl-vga` = accelerated 2D, smooth over SPICE, **but no built-in EDID** → Windows shows "Generic Non-PnP Monitor". Flip `model type` back to `vga` before sandbox tests that check the monitor name (cores/RAM/pinning stay).
- `virtio-vga`/`virtio-blk` = fastest + EDID, but requires virtio-gpu/block guest drivers.

## Why rebranding virtio drivers does NOT work (user may ask)

- Virtio exposes PCI vendor `0x1AF4` (Red Hat) + device IDs at the **hardware level**; renaming the guest driver's INF/filename changes nothing a sandbox probe sees.
- Changing IDs means forking QEMU device tables AND the Windows driver's PCI match tables AND driver-signing (test-signing = another tell), AND virtio capability structures remain a giveaway. Not a rename job, and defeats malware-analysis sandbox evasion is out of scope.

## Applied boost recipe (this machine, verified)

Host topology: 24 CPUs (0-23), 1 socket, 12 physical cores × 2 threads, single NUMA node. Pin vCPUs to physical cores 0-11, emulator thread to CPU 12.

XML deltas (rest of domain unchanged — keep all SMBIOS/CPU/hyperv/kvm-hidden/e1000/SATA config):
- `<memory unit="KiB">16777216</memory>` + `<currentMemory>` (16 GiB)
- `<vcpu placement="static">12</vcpu>`
- `<cputune>` with `<vcpupin vcpu="0" cpuset="0"/>` … `vcpu="11" cpuset="11"` and `<emulatorpin cpuset="12"/>`
- `<topology sockets="1" dies="1" cores="6" threads="2"/>` (was cores=4)
- `<video><model type="qxl" ram="65536" vram="65536" vgamem="16384" heads="1" primary="yes"/></video>` (was vga)

Apply/verify sequence (sudo via tty — fingerprint-gated; user must scan):
```
virt-xml-validate <file>.xml
virsh destroy UndetectableVM && virsh define <file>.xml && virsh start UndetectableVM
virsh dumpxml UndetectableVM | grep -E "<memory |<vcpu |cpuset|<topology|<model type=|<video"
# live proof:
ps -eo args | grep qemu-system | grep -oE 'smp [0-9]+|"driver":"qxl-vga"'
taskset -pc <qemu pid>   # emulator shows affinity 12
ls /proc/<qemu pid>/task/ | wc -l   # ~21 threads (12 vCPU + overhead)
```

## Memory caution

16 GiB to guest on a 30 GiB host leaves ~5.6 GiB available (some reclaimable buff/cache). Functional, but if the host swaps/feels slow, drop guest to 12 GiB (`12582912` KiB). 12 vCPU is fine on 24 threads.

## Notes

- Windows re-detects the new CPU/RAM/QXL adapter on next boot (QXL shows as "Microsoft Basic Display Adapter" until driver loads).
- Chkdsk on first boot after an unclean destroy is normal — let it finish.
- virtnetworkd (modular libvirt network daemon) must be enabled — see arch-libvirt-virtnetworkd-socket-missing if virt-manager shows "Failed to connect socket to '/var/run/libvirt/virtnetworkd-sock'".
