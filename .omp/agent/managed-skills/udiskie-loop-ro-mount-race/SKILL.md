---
name: udiskie-loop-ro-mount-race
description: "Use when mounting a libvirt VM's disk image (or any image) via losetup on an Omarchy box with udiskie --automount running, and the NTFS mount comes up READ-ONLY, cp fails with \"Read-only file system\" or \"Transport endpoint is not connected\", or losetup -d refuses to stick. The fix is killing udiskie first, detaching ALL loops, doing one clean attach, mounting rw with ntfs-3g -o rw,remove_hiberfile, then restoring udiskie."
---

# udiskie loop read-only mount race (Omarchy)

Companion to `libvirt-windows-guest-write-files-mount` — use when that skill's
rw mount unexpectedly comes up read-only, or when a loop device can't be
detached / a mount reports `Transport endpoint is not connected`.

## Root cause

On Omarchy (and similar desktops), `udiskie --automount` runs as a user daemon
and watches for new block devices. When you `losetup` a disk image, udiskie:

1. auto-attaches the loop and mounts the NTFS volume **read-only** (its policy
   for volumes it didn't cleanly manage), racing your ntfs-3g rw mount, and
2. can pile up **multiple loop attachments** (loop0 + loop1 on the same image),
   leaving stale mounts whose writes fail with
   `cp: ... Transport endpoint is not connected`.

`losetup -d` then "succeeds" but the loop reappears, and `umount` says
`target is busy` — udiskie keeps re-holding it.

## Diagnosis

```bash
mount | grep <mntpoint>          # shows ro (fuseblk) unexpectedly
losetup -j /path/to/image         # shows MORE THAN ONE loop on the image
touch <mntpoint>/.wtest           # "Transport endpoint is not connected" = stale loop mount
pgrep -af udiskie                 # udiskie is the re-holder
```

## Fix sequence (works every time)

```bash
# 1. stop udiskie so it stops racing the loop attach
pkill -f "python.*udiskie"

# 2. force-unmount the stale mount and detach ALL loops on the image
umount -f <mntpoint> 2>/dev/null || true
for l in $(losetup -j <image> -n -O NAME 2>/dev/null); do losetup -d "$l"; done
losetup -d /dev/loop0 2>/dev/null; losetup -d /dev/loop1 2>/dev/null

# 3. ONE clean attach
LOOP=$(losetup --find --show -P <image>)

# 4. mount rw (remove_hiberfile guards the NTFS hibernation flag)
ntfs-3g -o rw,remove_hiberfile ${LOOP}p3 <mntpoint>

# 5. do the file copy, then clean unmount + detach
cp ... <mntpoint>/Users/<user>/Desktop/
umount <mntpoint>
losetup -d "$LOOP"

# 6. restore udiskie
setsid /usr/bin/udiskie --automount --no-notify --no-tray >/dev/null 2>&1 < /dev/null &
```

## Verification

- `mount | grep <mntpoint>` shows `rw` before copying.
- `ls -la <mntpoint>/Users/<user>/Desktop/` shows the file with correct size.
- After unmount: `losetup -j <image>` prints nothing; `findmnt <mntpoint>` is empty.
- `pgrep -af udiskie` shows it restored before telling the user to boot the VM.

## Notes

- Never boot the VM while the image is loop-mounted — unmount+detach first.
- The volume's own `ntfsinfo -m` flags are usually `0x0000` (clean) — the ro is
  udiskie's policy, not a dirty/hibernation flag, so don't waste time checking
  hibernation first; go straight to the udiskie kill.
