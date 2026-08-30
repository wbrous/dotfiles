---
name: xorriso-windows-setup-iso-build
description: "Use when creating an ISO from Windows setup/installer files (exe, drivers, keys) to mount into a VM guest — covers staging, xorriso -as mkisofs flags (Joliet for Windows long filenames, Rock Ridge), volume label constraints, and the extract-and-cmp verification step."
---

# Building a Windows-usable ISO with xorriso

Use when packaging Windows setup executables / driver packs / key files into an ISO to attach to a VM (e.g. the qemu-anti-detection Windows guest) or physical media.

## Why xorriso flags matter
- `-J` (Joliet): Windows reads long filenames (e.g. `LockDownBrowserOEMSetup.exe`) correctly. Without it, Windows sees mangled 8.3 names.
- `-r` (Rock Ridge): keeps long names + permissions for Linux/macOS mounting too.
- Volume label: short, uppercase, no spaces (e.g. `LDB_OEM_SETUP`); lowercase/long labels get sanitized or rejected.

## Procedure
1. Stage files in a clean dir:
   ```bash
   mkdir -p /tmp/iso-staging
   cp ~/Downloads/SomethingSetup.exe /tmp/iso-staging/
   # write text/key files with the Write tool (exact bytes matter; see verification)
   ```
2. Build:
   ```bash
   cd /tmp && xorriso -as mkisofs -o OUTPUT.iso -V VOL_LABEL -J -r -graft-points iso-staging/
   ```
   `xorriso` is on Arch (package `libisoburn`); no mkisofs/genisoimage needed.
3. Verify — always extract back and compare byte-for-byte:
   ```bash
   # list contents:
   xorriso -indev OUTPUT.iso -find / -type f
   # extract a file and compare:
   rm -rf /tmp/iso-verify && mkdir /tmp/iso-verify
   xorriso -osirrox on -indev OUTPUT.iso -extract /name.txt /tmp/iso-verify/name.txt
   cmp /tmp/iso-verify/name.txt iso-staging/name.txt && echo MATCH
   ```
   For key/credential text files, `cmp` must pass — a single wrong byte in a base64 blob breaks the tool.

## Mounting into the libvirt VM
- Attach: `virsh attach-disk UndetectableVM /tmp/OUTPUT.iso sdb --type cdrom --mode readonly` (or virt-manager → Add Hardware → CD/DVD).
- Hot-detach when done: `virsh detach-disk UndetectableVM sdb`.
- Guest sees it as a normal CD-ROM; run the installer from Explorer.

## Gotchas
- `file OUTPUT.iso` should report `ISO 9660 CD-ROM filesystem data 'LABEL'`; if it says something else, the build failed.
- Text files: preserve exact line breaks (`cat -A` to inspect; trailing newline is typical). URL-encoded chars (`%5B`/`%5D`) and base64 line-wrapping must be kept verbatim.
- Disk size: sparse-aware; a 145 MB ISO from a 144 MB exe is normal (ISO overhead ~1%).
