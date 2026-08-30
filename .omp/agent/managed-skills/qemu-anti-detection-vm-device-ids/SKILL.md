---
name: qemu-anti-detection-vm-device-ids
description: "Use when customizing the qemu-anti-detection libvirt VM (UndetectableVM on this Omarchy host) so Windows guest shows realistic device names instead of \"Standard PS/2 Keyboard\", \"PS/2 Compatible Mouse\", or \"Generic Non-PnP Monitor\" — covers swapping PS/2 input for ASUS-branded USB HID, switching QXL video to EDID-generating VGA for a Dell PnP monitor, keeping the real Intel ich9 audio, and detaching the installer ISO."
---

# QEMU Anti-Detection VM: Realistic Device IDs

Customize the patched-QEMU libvirt VM (from zhaodice/qemu-anti-detection, built per `qemu-anti-detection-patched-build` skill) so Windows enumerates realistic hardware instead of generic VM devices. Verified working on this Omarchy host, QEMU 10.2.2 patched build, domain `UndetectableVM` (XML at `/tmp/vm-anti-detect/undetectable-vm-win10.xml`).

## Input: PS/2 → USB HID (kills "Standard PS/2 Keyboard" / "PS/2 Compatible Mouse")

Windows names PS/2 devices by its inbox class driver regardless of QEMU strings — the only way to get brand names is USB HID. The patched QEMU's USB HID descriptors are already ASUS-branded (dev-hid.c: `STR_MANUFACTURER="ASUS"`, `STR_PRODUCT_KEYBOARD="ASUS USB Keyboard"`, mouse/tablet likewise), so libvirt `<input>` swaps yield:

```xml
<input type="tablet" bus="usb"/>
<input type="mouse" bus="usb"/>
<input type="keyboard" bus="usb"/>
```

- libvirt maps these to `usb-kbd`/`usb-mouse`/`usb-tablet`; verified in process via `ps aux | grep qemu-system | grep -oE '"driver":"usb-(kbd|mouse|tablet)"'`.
- libvirt auto-adds PS/2 mouse+keyboard fallback inputs even with USB HID present — this is normal, leave them.
- USB vendor ID stays QEMU's 0x0627 (patch only changed string descriptors), so Device Manager shows the ASUS *name* but driver is generic "HID Keyboard Device" — good enough; real USB VID/PID would need USB passthrough.

## Monitor: QXL → VGA with EDID (kills "Generic Non-PnP Monitor")

- **QXL cannot generate EDID**: `qxl-vga` has NO `edid` property (`-device qxl-vga,edid=on` → "Property 'qxl-vga.edid' not found"). It depends on the SPICE client sending monitor EDID; virt-manager/virt-viewer often doesn't → guest sees no EDID → Windows shows "Generic Non-PnP Monitor".
- **Plain `VGA` device has `edid=<bool>` default on** and generates EDID via the patched `hw/display/edid-generate.c` → vendor `DEL`, name "DEL Monitor", model 0xA05F, pref 1280x1024. Windows shows a real Dell PnP monitor. Presents as generic "VGA compatible controller" (like real iGPUs), no guest driver needed.
- libvirt XML: `<model type="vga" heads="1" primary="yes"/>`. **Do NOT set `vgamem`** — libvirt rejects it: "vgamem attribute only supported for video type qxl".
- Tradeoff: loses QXL 2D accel; guest runs on basic display adapter at limited resolution. Acceptable for malware-analysis VMs.

## Audio: already real, leave it

`<sound model="ich9"/>` + `<audio id="1" type="spice"/>` → `ich9-intel-hda` is a genuine Intel HD Audio Controller identifier (what real boards report); Windows shows "Speakers (HD Audio)". No change needed.

## Detaching the installer ISO

Remove the `<disk type="file" device="cdrom">` element (the Win10 ISO at `/var/lib/libvirt/images/Win10_22H2_English_x64v1.iso` on sdb) and bump the hard disk `<boot order="2"/>` → `order="1"` so it boots the disk. Verify: `ps aux | grep qemu-system` shows only `disk.img`, no `.iso`, no `ide-cd`.

## Apply procedure

1. Edit XML, then `virt-xml-validate undetectable-vm-win10.xml` (catches the vgamem/ordering errors `virsh define` rejects).
2. `sudo virsh destroy UndetectableVM` (fingerprint-gated sudo on this host — user must scan; run via hub PTY).
3. `sudo virsh define undetectable-vm-win10.xml` → `DEFINE=0`.
4. `sudo virsh start UndetectableVM`.
5. Verify with `virsh dumpxml --inactive UndetectableVM | grep -E '<disk|<input|<model type'` (NOT plain dumpxml while running — it shows the stale live config) and the `ps` greps above.
6. Guest re-enumerates devices on boot; network lease re-obtains automatically (ufw rules already allow virbr0 — see `qemu-anti-detection-vm-network-debug` skill).

## Known pitfalls

- `virsh define` while VM running only updates persistent config; running instance keeps old devices until restart. `virsh start` errors "Domain is already active" if you forgot to destroy first.
- After edits, `virsh dumpxml` (no flag) on a running domain shows the OLD live device list — always use `--inactive` to check persistent state.
- `/tmp/vm-anti-detect/` is ephemeral tmpfs — the XML lives there; if the file is gone, regenerate from the persistent domain (`virsh dumpxml --inactive UndetectableVM`), or recreate the whole setup from the build skill.
