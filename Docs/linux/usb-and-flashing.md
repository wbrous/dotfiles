# USB Flashing on Arch (Ventoy)

Flash/install Ventoy onto a USB drive on Arch/Omarchy (official repos have no `ventoy`, only AUR). Sudo here is fingerprint-gated — any sudo needing interactive confirmation must run in a real PTY, not plain non-interactive bash.

## Install Ventoy and flash the drive

**Symptom:** Need a Ventoy multiboot USB on Arch.

**Fix:**
```sh
lsblk -o NAME,SIZE,MODEL,TRAN,VENDOR,RM,TYPE,MOUNTPOINT   # look for TRAN=usb
yay -S --noconfirm ventoy-bin
```
Confirm the exact device with the user before wiping (destructive — never assume `/dev/sda`). If the `makepkg` build's final `pacman -U` fails with "sudo: a terminal is required" / "Verification timed out", the packages are still built in `~/.cache/yay/ventoy-bin/*.pkg.tar.zst` — install them manually in a PTY rather than re-running yay. Verify: `which ventoy` / `ls /opt/ventoy/`.
```sh
umount /run/media/$USER/<label>
sudo /opt/ventoy/Ventoy2Disk.sh -I /dev/sdX
```
**Gotcha:** `Ventoy2Disk.sh` takes the device as a bare positional arg: `-I /dev/sdX` (force install) or `-i /dev/sdX` (refuses if already Ventoy). There is no `-d` flag — passing `-d` errors with "-d is NOT a valid device". The script asks twice (`Continue? (y/n)`, then `Double-check. Continue? (y/n)`) — answer each after reading the actual prompt, don't blind-send both. Wait for `Install Ventoy to /dev/sdX successfully finished.` Verify:
```sh
lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINT /dev/sdX
```
Expect partition 1 = exFAT labeled `Ventoy` (bulk of disk), partition 2 = ~32M VFAT `VTOYEFI`. Afterwards just copy bootable ISOs into the `Ventoy` partition; Ventoy menus them all with no reflash per ISO.

_Migrated from: ventoy-usb-flash-arch_
