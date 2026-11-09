---
name: arch-iphone-mount-ifuse
description: "Mount a plugged-in iPhone on Arch/Omarchy to browse photos/DCIM; ifuse missing, pairing, sudo install in PTY."
---

# Mount iPhone on Arch/Omarchy with ifuse

1. Detect: `lsusb | grep -i apple`; `systemctl is-active usbmuxd`; `idevice_id -l` (lists UDID if visible).
2. Pairing: `idevicepair validate`. If not validated, run `idevicepair pair` and have the user tap "Trust" on the phone (unlock it first).
3. Tools: `libimobiledevice` and `usbmuxd` are usually present, but `ifuse` often is NOT. Check `which ifuse`.
4. Install: `sudo pacman -S --needed --noconfirm ifuse`. `sudo -n` fails (password required), so run via `bash` with `pty: true`; sudo here uses fingerprint auth, so the user must touch the reader.
5. Mount: `mkdir -p ~/iPhone && ifuse ~/iPhone`, then verify with `mount | grep ifuse` and `ls ~/iPhone`. Photos/videos are in `~/iPhone/DCIM`.
6. Unmount: `fusermount -u ~/iPhone`.

Notes: ifuse exposes only Apple's media partition (AFC), not app data or the full filesystem. No sudo needed for the mount itself, only for installing ifuse.
