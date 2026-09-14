---
name: ventoy-usb-flash-arch
description: "Use when flashing/installing Ventoy onto a USB drive on Arch/Omarchy — covers installing ventoy-bin from AUR (yay), the Ventoy2Disk.sh CLI arg gotcha, and running the interactive install (double y/n confirmation, fingerprint-gated sudo) via hub for a real PTY."
---

## Context
Arch/Omarchy has no `ventoy` package in official repos — only AUR. Sudo is fingerprint-gated (fprintd), so any `sudo` invocation needing interactive confirmation must run in a real PTY via `hub`, not plain `bash` (which can't surface the prompt and will hang/timeout).

## Steps

1. Identify the target device (never assume `/dev/sda`):
   ```
   lsblk -o NAME,SIZE,MODEL,TRAN,VENDOR,RM,TYPE,MOUNTPOINT
   ```
   Look for `TRAN=usb`. Confirm the exact device with the user before wiping (destructive).

2. Install ventoy-bin from AUR:
   ```
   yay -S --noconfirm ventoy-bin
   ```
   The `makepkg` build step itself may trigger a fingerprint sudo prompt for `pacman -U` at the end — if it fails with "sudo: a terminal is required" / "Verification timed out", the AUR package files are still built successfully in `~/.cache/yay/ventoy-bin/*.pkg.tar.zst`. Install them manually via hub (step 3) rather than re-running yay.

3. If step 2's final install failed, install the built packages manually via hub for a real PTY:
   ```
   hub start name=ventoy-install application=sudo args=["pacman","-U","--noconfirm","<pkg1>.pkg.tar.zst","<pkg2-debug>.pkg.tar.zst"] pty=true
   ```
   Verify: `which ventoy` / `ls /opt/ventoy/`.

4. Unmount the target drive first:
   ```
   umount /run/media/$USER/<label>
   ```

5. Run the installer via hub (PTY required — it prompts fingerprint + two y/n confirmations):
   ```
   hub start name=ventoy-flash application=sudo args=["/opt/ventoy/Ventoy2Disk.sh","-I","/dev/sdX"] pty=true
   ```
   **Gotcha:** `Ventoy2Disk.sh` does NOT take `-d /dev/sdX` — the device is a bare positional arg after the mode flag: `-I /dev/sdX` (force install) or `-i /dev/sdX` (install, fails if already Ventoy). Passing `-d` errors with "-d is NOT a valid device".

6. The script asks for confirmation twice:
   - `Continue? (y/n)` → send `y`
   - `Double-check. Continue? (y/n)` → send `y`
   Use `hub send name=ventoy-flash text=y` for each, then `hub logs` to check state before sending the next one (don't blind-send both at once — read the actual prompt each time).

7. Wait for exit via `hub wait name=ventoy-flash for=exit timeout=120`. Success message: "Install Ventoy to /dev/sdX successfully finished."

8. Verify result:
   ```
   lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINT /dev/sdX
   ```
   Expect: partition 1 = exFAT labeled `Ventoy` (bulk of disk), partition 2 = ~32M VFAT `VTOYEFI`.

Usage after install: copy bootable ISOs directly into the `Ventoy`-labeled partition; boot the drive and Ventoy presents a menu of all ISOs on it — no reflash needed per ISO.
