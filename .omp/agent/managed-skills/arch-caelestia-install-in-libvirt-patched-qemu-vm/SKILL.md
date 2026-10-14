---
name: arch-caelestia-install-in-libvirt-patched-qemu-vm
description: "Install Arch Linux + Caelestia (Hyprland shell) into a libvirt VM on this host, driving the live ISO from the host: virsh send-key typing, virtio NIC/disk invisible under patched QEMU, SSH bootstrap, paru/jack2 gotchas, caelestia install --noconfirm."
---

# Arch + Caelestia into a libvirt VM (patched QEMU host)

## Driving the guest console
- `wtype` into the focused virt-manager window produces GARBLED text (fcitx5 is the main keyboard). Do not use it.
- Use `virsh -c qemu:///system send-key DOMAIN KEY_...` per character (US layout; shift = KEY_LEFTSHIFT + key). Write a small python helper that validates every char has a keycode BEFORE sending anything.
- This Hyprland (0.56) uses Lua dispatch: `hyprctl dispatch 'hl.dsp.focus({ window = "address:0x..." })'`. Old `focuswindow address:...` syntax errors.
- Once in the live ISO: `echo root:live | chpasswd; systemctl start sshd`, then SSH with `sshpass` (installed on host). Guest IP: `virsh net-dhcp-leases default` (IP CHANGES per boot; newest lease wins) or `domifaddr DOMAIN --source arp`.
- User says "online, just ping 1.1.1.1": do not test DNS/archlinux.org; avoid long-running foreground SSH commands (they background and waste turns). Use `nohup sh -c '...; echo EXIT=$? >> log' &` then one wait loop on `grep ^EXIT=`.

## Patched QEMU gotcha (qemu-anti-detection)
- Virtio PCI IDs are spoofed (8086:1041/1042), so the guest has NO virtio_net / virtio_blk binding: no network, no /dev/vda.
- Fix: NIC -> `e1000` (detach, then `attach-device` with XML pinned to the SAME `<address type='pci' bus='0x01' .../>`; plain attach-interface fails "No more available PCI slots"). Disk -> `bus='sata'` `dev='sdb'`, remove the alias/pci address from its XML, redefine from `dumpxml --inactive`. Disk then appears as /dev/sda.
- Redefining while running leaves the old config live; `virsh destroy` first, then define + start. virt-manager may restart the domain.
- BIOS (SeaBIOS) guest: MBR + `grub-install --target=i386-pc /dev/sda`. After install, `change-media sda --eject --config`, delete `<boot dev='cdrom'/>`, redefine.

## Install flow that worked
1. parted msdos, one ext4 partition (full disk), mount /mnt.
2. `pacstrap -K /mnt base linux linux-firmware base-devel git sudo networkmanager grub vim openssh qemu-guest-agent`.
3. genfstab, arch-chroot script: locale, hostname, user in wheel, grub, `systemctl enable NetworkManager sshd`.
4. Reboot; temp `NOPASSWD` sudoers drop-in for the install, REMOVE it afterwards (makepkg/paru need non-tty sudo).
5. AUR helper: `paru-bin` FAILS (links libalpm.so.15, system has 16). Build source `paru` from AUR instead (~3 min, needs `rust`).
6. `paru -S caelestia-cli`, then `caelestia install --aur-helper paru --noconfirm` (default components; spotify/vscode/etc off).
7. First run fails with `pipewire-jack and jack2 conflict` (--noconfirm answers N): `pacman -Rdd jack2` first, then rerun (~8 min).
8. Add exec Hyprland on tty1 to ~/.bash_profile. Installer's `hyprctl reload` hook exit 1 is expected (Hyprland not running).

## Not verified
Whether Hyprland starts on the spoofed Intel GPU (82562EZ ID shown as VGA) -- needs the console; user said to notify (notify-send) and yield when UI is needed.
