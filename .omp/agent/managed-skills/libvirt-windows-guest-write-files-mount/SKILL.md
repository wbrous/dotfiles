---
name: libvirt-windows-guest-write-files-mount
description: "Use when copying files into a Windows guest's filesystem by mounting its libvirt disk image from the host (e.g. placing setup.exe + key files on the guest Desktop), or when an auto-mounted NTFS volume mounts read-only and cp fails with \"Read-only file system\". Covers probing the GPT layout, losetup -fP partition attach, checking NTFS Volume Flags (0x0000 = clean, no hibernation flag), mounting rw with ntfs-3g, finding the user Desktop at Users/name/Desktop, and safe unmount before booting the VM."
---

# Writing files into a Windows guest (mount libvirt disk image)

Use when a Windows VM's disk must be modified from the host while the VM is OFF — e.g. placing `setup.exe` + a key file on the guest Desktop because the guest couldn't read an ISO.

## Prereqs
- VM fully shut off (`virsh list --all` shows "shut off"), or filesystem will be inconsistent.
- Packages: `sudo pacman -S ntfs-3g ntfsprogs` (ntfs-3g = userspace rw mount; ntfsprogs = `ntfsinfo`, `ntfsfix`).

## Quick path (whole-image offset, no partition nodes)
Windows C: partition offset = start_sector × 512 (from `fdisk -l disk.img`; typically the 49G "Microsoft basic data" partition, sector ~239616 for a default Win10 install → offset 122683392).
```bash
sudo mkdir -p /mnt/winguest
sudo mount -o offset=$((239616*512)) /var/lib/libvirt/images/disk.img /mnt/winguest
```

## The udisks read-only gotcha (the real fix)
If the user auto-mounts the image via a file manager / udisks, the mount is **read-only by udisks policy** (`ro,nosuid,...,ntfs3`), and `sudo cp` fails with `Read-only file system`. This is NOT necessarily a dirty/hibernation flag:
1. Check the volume is clean: `ntfsinfo -m <partdev> | grep -iE "Volume Flags"` — `0x0000` = clean (no hibernation/dirty). If flags non-zero, `ntfsfix -d` may be needed (hibernation flag blocks rw).
2. Reattach with partition scanning and mount rw:
```bash
sudo losetup -d /dev/loopN          # release the ro udisks loop first
sudo umount /run/media/<user>/<VOL> # may say "target is busy" — losetup -d still frees it
LOOP=$(sudo losetup --show -fP /var/lib/libvirt/images/disk.img)  # → /dev/loop1, nodes loop1p1..p4
sudo mkdir -p /mnt/lockdown
sudo ntfs-3g -o rw ${LOOP}p3 /mnt/lockdown   # partition 3 = Windows C: on standard Win10 GPT
```
3. Verify writable: `touch /mnt/lockdown/.writetest && rm /mnt/lockdown/.writetest` → `WRITE_OK`.
4. Guest Desktop: `/mnt/lockdown/Users/<WindowsUsername>/Desktop/` (find the username with `ls /mnt/lockdown/Users/`).

## Cleanup (before booting the VM!)
```bash
sudo umount /mnt/lockdown
sudo losetup -d /dev/loop1
```
NEVER boot the VM while the image is mounted — conflicting filesystem access corrupts the guest.

## Notes
- `virsh domblklist` reports the guest disk path (`/var/lib/libvirt/images/disk.img` here).
- The guest's C: partition is the ~49G "Microsoft basic data" GPT partition (part 3 after EFI + MSR).
- Copies into the guest must go through the rw ntfs-3g mount (root), not the udisks ro mount.
