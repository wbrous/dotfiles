# Windows Guest Files, MSI Builds, and ISOs

Work with Windows guests and installers from an Arch/Linux host: write files into guest disks, debug MSI 1603 failures, build WiX 6 MSIs in CI, and package ISOs for VM guests.

## Writing files into a Windows guest disk (VM off)

**Symptom:** Need to modify a Windows VM's disk from the host while the VM is OFF (e.g. place `setup.exe` + key on the Desktop because the guest couldn't read an ISO).

**Prereqs:** VM fully shut off (`virsh list --all` shows "shut off"); `sudo pacman -S ntfs-3g ntfsprogs`.

**Quick path (whole-image offset, no partition nodes):** C: offset = start_sector × 512 from `fdisk -l disk.img` (typically the ~49G "Microsoft basic data" partition, sector ~239616 → offset 122683392):

```bash
sudo mkdir -p /mnt/winguest
sudo mount -o offset=$((239616*512)) /var/lib/libvirt/images/disk.img /mnt/winguest
```

**udisks read-only gotcha:** a file-manager/udisks auto-mount is read-only by policy (`ro,nosuid,...,ntfs3`) and `sudo cp` fails with `Read-only file system`. Check volume clean: `ntfsinfo -m <partdev> | grep -iE "Volume Flags"` — `0x0000` = clean (if non-zero, `ntfsfix -d` may be needed). Then reattach with partition scanning and mount rw:

```bash
sudo losetup -d /dev/loopN
sudo umount /run/media/<user>/<VOL>   # may say busy — losetup -d still frees it
LOOP=$(sudo losetup --show -fP /var/lib/libvirt/images/disk.img)
sudo mkdir -p /mnt/lockdown
sudo ntfs-3g -o rw ${LOOP}p3 /mnt/lockdown   # p3 = Windows C: on standard Win10 GPT
```

Verify writable (`touch /mnt/lockdown/.writetest`), find the Desktop at `/mnt/lockdown/Users/<WindowsUsername>/Desktop/`. Cleanup before booting: `sudo umount /mnt/lockdown; sudo losetup -d /dev/loop1`. NEVER boot the VM while the image is mounted. `virsh domblklist` reports the guest disk path.

_Migrated from: libvirt-windows-guest-write-files-mount_

## udiskie loop read-only race (Omarchy)

**Symptom:** The rw mount above unexpectedly comes up read-only, `cp` fails with "Transport endpoint is not connected", or `losetup -d` refuses to stick.

**Cause:** `udiskie --automount` watches for new block devices: it auto-attaches the loop and mounts NTFS read-only, racing your ntfs-3g rw mount, and can pile up multiple loop attachments (loop0 + loop1 on the same image) with stale mounts. The volume's `ntfsinfo` flags are usually `0x0000` — the ro is udiskie's policy, not a dirty flag, so don't check hibernation first.

**Fix (works every time):**

```bash
pkill -f "python.*udiskie"                                  # stop the race
umount -f <mntpoint> 2>/dev/null || true
for l in $(losetup -j <image> -n -O NAME 2>/dev/null); do losetup -d "$l"; done
losetup -d /dev/loop0 2>/dev/null; losetup -d /dev/loop1 2>/dev/null
LOOP=$(losetup --find --show -P <image>)                    # ONE clean attach
ntfs-3g -o rw,remove_hiberfile ${LOOP}p3 <mntpoint>
cp ... <mntpoint>/Users/<user>/Desktop/
umount <mntpoint>; losetup -d "$LOOP"
setsid /usr/bin/udiskie --automount --no-notify --no-tray >/dev/null 2>&1 < /dev/null &
```

Diagnose: `mount | grep <mntpoint>` shows unexpected ro; `losetup -j <image>` shows more than one loop; `touch` gives "Transport endpoint is not connected"; `pgrep -af udiskie` confirms the re-holder. Verify before copying: `mount | grep <mntpoint>` shows `rw`; after: `losetup -j <image>` empty, udiskie restored.

_Migrated from: udiskie-loop-ro-mount-race_

## MSI 1603 on a clean Windows VM

**Symptom:** MSI install fails with 1603; custom action returns -1073741515 (0xC0000135).

**Getting install.log out of the VM:** offline disk access is usually a dead end — use the network. `virsh -c qemu:///system domifaddr <vm>` gives the IP; in the log's folder (elevated PowerShell): `python -m http.server 8000` + `New-NetFirewallRule ... -LocalPort 8000 -Action Allow`; then `curl -o install.log http://<ip>:8000/install.log`; afterwards `Remove-NetFirewallRule -DisplayName "tmp-8000"`.

**Reading it:** `msiexec /l*v` logs are UTF-16LE: `iconv -f UTF-16LE -t UTF-8 install.log | tr -d '\r' > install.txt`. Ignore `Note: 1: 2205/2262` (benign). Look at `MainEngineThread is returning 1603`, `Action ended ...: InstallFinalize. Return value 3`, and the `CustomAction <Id> returned actual error code <N>` just before it.

**Cause/Fix for 0xC0000135:** `STATUS_DLL_NOT_FOUND` — the exe a custom action runs can't start. For a Rust MSVC exe it's `VCRUNTIME140.dll`/`api-ms-win-crt-*` missing on stock Windows. A `Return="check"` action fails and rolls back; `Return="ignore"` hides it. Fix: static CRT in `.cargo/config.toml`:

```toml
[target.'cfg(all(windows, target_env = "msvc"))']
rustflags = ["-C", "target-feature=+crt-static"]
```

Guard in CI with `dumpbin /dependents optic.exe` (via vswhere) failing on `VCRUNTIME*|MSVCP*|api-ms-win-crt-*`. From Linux: `7z x installer.msi -ox`, then read the PE import table. Local mingw (`gnu`) builds are unaffected by the `msvc`-scoped cfg.

_Migrated from: msi-1603-install-log-missing-vcruntime_

## WiX 6 MSI authoring and CI

**Version choice:** WiX 7 requires accepting the OSMF EULA (`-acceptEula wix7`); orgs over $10k revenue owe a fee — don't accept silently in CI. Pin WiX 6.0.2: `dotnet tool install --global wix --version 6.0.2`, `wix extension add --global WixToolset.Util.wixext/6.0.2`. `windows-latest` ships only WiX 3.14, plus VS 2022 with WDK VS extension, Windows SDK 26100, .NET 9, Rust — no WDK install step needed.

**Local validation on Linux (limited):** `wix` runs under `dotnet` but warns "undefined behavior"; EVERY `Directory/@Name` fails with WIX0389 even for a minimal file — a platform artifact, not a bug; full MSI build is impossible there. Any other error is real. Check PowerShell syntax with `System.Management.Automation.Language.Parser.ParseFile`, workflows with `actionlint`.

**Authoring facts (verified against docs/compiler):** XML comments can't contain `--`; Windows Installer can't `ServiceInstall` a kernel driver — copy the .sys, register via deferred custom action running the installed exe (SCM API); WiX 6 names: `FileRef` (not FileKey), `HideTarget` for secrets, `util:ServiceConfig` (not ServiceConfigFailureActions, WIX1149) nested in ServiceInstall; a component holding only `CreateFolder` needs an explicit `Guid`; `util:RemoveFolderEx` takes a PROPERTY set before CostInitialize, never a Directory id; `ServiceControl` has no Condition — omit `Start="install"` and start from a conditional custom action (`net.exe start`, `Directory="SystemFolder"`) if the service needs runtime state; public properties in `ExeCommand` format at script-write time, so `[PAIRING_CODE]` works in deferred actions; every stock WixUI set includes a licence page — with no repo licence, ship no wizard UI rather than placeholder text.

**CI:** pass free-text `workflow_dispatch` inputs via `env:`, not `${{ }}` inside `run:`; test-sign the driver with throwaway `New-SelfSignedCertificate`, verify with `Get-AuthenticodeSignature` (signtool verify /pa fails by design for self-signed), upload the .cer too.

_Migrated from: wix6-msi-from-linux-and-github-actions_

## Building a Windows-usable ISO with xorriso

**Symptom:** Need to package setup exes / drivers / keys into an ISO for a VM guest.

**Why flags matter:** `-J` (Joliet) so Windows reads long filenames; `-r` (Rock Ridge) for Linux/macOS long names; volume label short uppercase no spaces (e.g. `LDB_OEM_SETUP`).

```bash
mkdir -p /tmp/iso-staging
cp ~/Downloads/SomethingSetup.exe /tmp/iso-staging/
cd /tmp && xorriso -as mkisofs -o OUTPUT.iso -V VOL_LABEL -J -r -graft-points iso-staging/
```

`xorriso` is on Arch (package `libisoburn`). Always verify — extract back and byte-compare (`cmp` must pass for key/credential files):

```bash
xorriso -indev OUTPUT.iso -find / -type f
rm -rf /tmp/iso-verify && mkdir /tmp/iso-verify
xorriso -osirrox on -indev OUTPUT.iso -extract /name.txt /tmp/iso-verify/name.txt
cmp /tmp/iso-verify/name.txt iso-staging/name.txt && echo MATCH
```

Attach: `virsh attach-disk UndetectableVM /tmp/OUTPUT.iso sdb --type cdrom --mode readonly`; hot-detach: `virsh detach-disk UndetectableVM sdb`. `file OUTPUT.iso` should report `ISO 9660 CD-ROM filesystem data 'LABEL'`.

_Migrated from: xorriso-windows-setup-iso-build_
