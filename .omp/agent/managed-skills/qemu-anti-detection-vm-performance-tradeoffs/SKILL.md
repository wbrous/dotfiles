---
name: qemu-anti-detection-vm-performance-tradeoffs
description: "Use when the UndetectableVM (qemu-anti-detection patched QEMU + libvirt on Omarchy) feels laggy and the user wants more cores/RAM, a faster display, or asks whether virtio drivers can be renamed/rebranded to bypass detection. Covers why unaccelerated VGA is the lag source, the QXL-vs-VGA EDID tradeoff, and why renaming virtio drivers does NOT hide virtualization (PCI vendor 0x1AF4 is hardware-level)."
---

# VM Performance vs Anti-Detection Tradeoffs (UndetectableVM)

Context: the qemu-anti-detection VM on this Omarchy host (see qemu-anti-detection-vm-device-ids). When the guest feels laggy, the bottleneck is almost always the DISPLAY, not cores/RAM. Keep this decision map in mind.

## Verified facts (from this setup)

- **Display is currently `VGA` (unaccelerated framebuffer)** — chosen so the patched EDID reports a Dell monitor ("DEL Monitor") instead of "Generic Non-PnP Monitor". Windows redraws over SPICE with no GPU accel → laggy feel regardless of vCPU/RAM.
- **QXL (`qxl-vga`) cannot emit its own EDID** — it has NO `edid` property (rejects `-device qxl-vga,edid=on`). It relies on the SPICE client sending monitor EDID; virt-manager/virt-viewer often sends none → guest shows "Generic Non-PnP Monitor". QXL = smooth 2D, but generic monitor name.
- **`VGA` and `virtio-vga` have `edid=<bool>` default ON** using the patched qemu-anti-detection EDID generator (defaults: vendor "DEL", name "DEL Monitor", model 0xA05F, prefx 1280).
- **Virtio devices report PCI vendor `0x1AF4` (Red Hat)** in hardware — the single loudest VM tell in a PCI/firmware scan. This is in the device, NOT the driver.
- **Renaming/recompiling a virtio driver with a custom name does NOT defeat detection**: detectors read PCI vendor/device IDs (1AF4), fw-cfg hints, and ACPI/DMI strings — not the driver filename or display name. A "rebranded" virtio-gpu/virtio-blk driver is cosmetically renamed but still 100% detectable. Compiling virtio from scratch with fake PCI IDs + a matching custom guest driver is a large fork (QEMU device IDs + guest driver) and out of scope.
- Adding virtio (blk or gpu) REGRESSES the anti-detection posture of this build — 1AF4 undoes the whole hidden-hypervisor/realistic-device setup.
- Host resources: AMD Ryzen AI 9 HX 370, 24 threads, 30 GiB RAM (~13 GiB available at the time).

## Recommended performance path (keep anti-detection posture)

1. **Do NOT add virtio-blk or virtio-gpu** — 1AF4 PCI vendor is a detection tell no rename fixes.
2. Bump resources: 12 vCPU (topology cores=6 threads=2 or cores=8) + 16 GiB RAM. Host has headroom.
3. **vCPU pinning** (`virsh vcpupin` to physical cores) + raise QEMU nice level → less scheduler jitter, noticeably smoother, zero detection cost.
4. SPICE tuning: `image compression=off` already set in domain XML.
5. Keep SATA disk (realistic) and e1000/e1000e NIC (real Intel) — no virtio.

## If the user accepts one VM-ish device for smoothness

- `qxl-vga` is the single biggest perf win, cost = "Generic Non-PnP Monitor" (Red Hat PCI vendor too). Flip back to `VGA` before sandbox-testing if the sample checks monitor names.
- `virtio-vga` keeps EDID (named monitor) + smooth, but needs virtio-gpu guest driver in Windows (VM-specific driver) AND exposes 1AF4.

## Ethics note

Renaming/rebranding drivers specifically to defeat sandbox/anti-cheat detection is out of scope. The legit use is malware analysis: getting samples to RUN by hiding QEMU device names/SMBIOS/hypervisor (the qemu-anti-detection patch) — not fabricating hardware identities to evade analysis tooling.
