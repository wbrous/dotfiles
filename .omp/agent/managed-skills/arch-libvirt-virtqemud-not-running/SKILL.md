---
name: arch-libvirt-virtqemud-not-running
description: "Use when virt-manager or virsh fails with \"Unable to connect to libvirt qemu:///system\" (or socket not found) on Arch Linux — modular libvirt daemons (virtqemud) are disabled/not running."
---

# Arch: fix "Unable to connect to libvirt qemu:///system"

## Symptom
- virt-manager: "Unable to connect to libvirt qemu:///system. Verify that an appropriate libvirt daemon is running."
- `virsh -c qemu:///system list --all` → `Failed to connect socket to '/var/run/libvirt/virtqemud-sock': No such file or directory`

## Root cause
Arch's libvirt uses **modular daemons** (socket-activated per-driver), NOT the legacy monolithic `libvirtd`. `virtqemud` handles QEMU. Its socket `/run/libvirt/virtqemud-sock` doesn't exist when `virtqemud.socket` is disabled/inactive. (Legacy `libvirtd.service` being dead is NORMAL — it's a different, deprecated path; don't chase it.)

## Diagnose
```bash
systemctl status virtqemud virtqemud.socket --no-pager -l
# expect: inactive (dead) / disabled
ls /run/libvirt/   # missing virtqemud-sock when down
```

## Fix
```bash
systemctl enable --now virtqemud.socket virtqemud-ro.socket
```
- Symlinks all three sockets (`virtqemud.socket`, `-ro`, `-admin`) into `sockets.target.wants` (boot-persistent).
- `virtqemud.service` itself spawns on demand via socket activation — no need to enable the service.

## Verify
```bash
virsh -c qemu:///system list --all   # exit 0, possibly empty list
systemctl status virtqemud.socket    # active (listening)
```
Reconnect in virt-manager (File → Add Connection → qemu:///system). No reboot needed.
