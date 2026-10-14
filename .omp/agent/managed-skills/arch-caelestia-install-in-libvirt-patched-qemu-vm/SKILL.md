---
name: arch-caelestia-install-in-libvirt-patched-qemu-vm
description: "Install Arch Linux + Caelestia (Hyprland shell) + greetd/Airlock login manager into a libvirt VM on this host, driving the live ISO from the host: virsh send-key typing, virtio NIC/disk/GPU invisible under patched QEMU, SSH bootstrap, paru/jack2 gotchas, caelestia install --noconfirm, plus post-install tweaks (resolution, timezone, 24h clock)."
---

# Arch + Caelestia into a libvirt VM (patched QEMU host)

## Driving the guest console
- `wtype` into the focused virt-manager window produces GARBLED text (fcitx5 is the main keyboard). Do not use it.
- Use `virsh -c qemu:///system send-key DOMAIN KEY_...` per character (US layout; shift = KEY_LEFTSHIFT + key). Write a small python helper that validates every char has a keycode BEFORE sending anything.
- This Hyprland (0.56) uses Lua dispatch: `hyprctl dispatch 'hl.dsp.focus({ window = "address:0x..." })'`. Old `focuswindow address:...` syntax errors. `hl.dsp.cursor.move({x=,y=})` works; there is NO click/send_key dispatcher and no ydotool, so drive guest UIs with keyboard only. Hide the agent scratchpad with `hl.dsp.workspace.toggle_special("scratchpad")`.
- Once in the live ISO: `echo root:live | chpasswd; systemctl start sshd`, then SSH with `sshpass` (installed on host). Guest IP: `virsh net-dhcp-leases default` (IP CHANGES per boot; newest lease wins) or `domifaddr DOMAIN --source arp`.
- User says "online, just ping 1.1.1.1": do not test DNS/archlinux.org; avoid long-running foreground SSH commands (they background and waste turns). Use `nohup sh -c '...; echo EXIT=$? >> log' &` then one wait loop on `grep ^EXIT=`.
- User may keep using their computer: notify with `notify-send` when UI is needed, then yield.
- Take screenshots with `grim` as its OWN bash call (or after the SSH call returns); a grim chained after a failing/odd step may not run.

## Patched QEMU gotcha (qemu-anti-detection): ALL virtio PCI devices are unusable
- Virtio PCI IDs are spoofed (8086:1041 net, 1042 blk, 1050 gpu), so the guest has NO virtio_net / virtio_blk / virtio-gpu binding.
- NIC: -> `e1000` (detach, then `attach-device` with XML pinned to the SAME `<address type='pci' bus='0x01' .../>`; plain attach-interface fails "No more available PCI slots"). Guest sees `enp1s0`.
- Disk: -> `bus='sata'` `dev='sdb'`, remove the alias/pci address from its XML, redefine from `dumpxml --inactive`. Disk then appears as /dev/sda (ISO is sr0).
- Video: virtio-vga stays on `simpledrm` at 640x480 (cropped, unusable). Switch to `<model type='vga' vram='65536' heads='1' primary='yes'/>`; `bochs-drm` binds and the guest offers many modes.
- Redefining while running leaves the old config live; `virsh destroy`/`shutdown` first, then define + start. virt-manager may restart the domain.
- BIOS (SeaBIOS) guest: MBR + `grub-install --target=i386-pc /dev/sda`. After install, `change-media sda --eject --config`, delete `<boot dev='cdrom'/>`, redefine.

## Install flow that worked
1. parted msdos, one ext4 partition (full disk), mount /mnt.
2. `pacstrap -K /mnt base linux linux-firmware base-devel git sudo networkmanager grub vim openssh qemu-guest-agent`.
3. genfstab, arch-chroot script: locale, hostname, user in wheel, grub, `systemctl enable NetworkManager sshd`.
4. Reboot; temp `NOPASSWD` sudoers drop-in for the install, REMOVE it afterwards (makepkg/paru need non-tty sudo).
5. AUR helper: `paru-bin` FAILS (links libalpm.so.15, system has 16). Build source `paru` from AUR instead (~3 min, needs `rust`).
6. `paru -S caelestia-cli`, then `caelestia install --aur-helper paru --noconfirm` (default components; spotify/vscode/uwsm etc off).
7. First run fails with `pipewire-jack and jack2 conflict` (--noconfirm answers N): `pacman -Rdd jack2` first, then rerun (~8 min).
8. Installer's `hyprctl reload` hook exit 1 is expected (Hyprland not running).

## Login manager: greetd + Astra Airlock (Caelestia-styled, single user, password entry)
- `paru -S --noconfirm --needed --skipreview greetd cage astra-airlock` (qt6-m3shapes-git + quickshell-git already come from caelestia-shell).
- `/etc/greetd/config.toml`: `[terminal] vt = 1`, `[default_session] command = "cage -s -- astra-airlock >/dev/null 2>&1"`, `user = "greeter"`. Cage (not Hyprland) as the greeter compositor.
- `/etc/pam.d/greetd`: add `auth optional pam_gnome_keyring.so` and `session optional pam_gnome_keyring.so auto_start` (AUR package did NOT add them).
- `usermod -aG video,input greeter`; `install -d -o greeter -g greeter /var/cache/astra-airlock`; `sudo astra-airlock --sync` copies the desktop scheme; `systemctl enable greetd`.
- Remove any manual `exec Hyprland` from ~/.bash_profile (greetd owns tty1).
- Airlock opens on an idle clock; ANY key (Enter) shows the login form. It auto-shows only the one user with the password field focused: just type the password + Enter. Do NOT Tab/Enter blindly: that submits an empty password (AUTH_ERR) and restarts the greeter.
- GOTCHA: the hyprland package ships `hyprland-uwsm.desktop` (TryExec=uwsm), Airlock lists it anyway and defaults to it; uwsm is not installed so login authenticates then the session dies instantly. Fix: set `userSessions.<user>` to `hyprland` in `/var/cache/astra-airlock/greeter.json` and restart greetd (or install uwsm).
- Greeter 12/24h is `use12Hour` in `/var/cache/astra-airlock/greeter.json` (already false by default).

## Post-install tweaks (all via Caelestia's user-override files, survive updates)
- Zoom out = higher guest resolution. `~/.config/caelestia/hypr-user.lua`: `hl.monitor({ output = "", mode = "1920x1200@60", position = "auto", scale = 1 })` (16:10 fits the ~2280x1477 virt-manager window; modes come from bochs-drm, check `/sys/class/drm/card*-*/modes`). Apply with `hyprctl reload` (set XDG_RUNTIME_DIR=/run/user/1000 and HYPRLAND_INSTANCE_SIGNATURE=$(ls $XDG_RUNTIME_DIR/hypr|head -1) when running over SSH).
- Timezone: guest defaults to UTC. `timedatectl set-timezone <host tz>` (host: `timedatectl show -p Timezone --value`) and `systemctl enable --now systemd-timesyncd`.
- 24-hour shell clock: `~/.config/caelestia/shell.json` = `{"services": {"clockFormat": "TwentyFourHour"}}` (values: Auto | TwelveHour | TwentyFourHour). Auto follows the en_US locale = 12h. Applies live, no restart.

## Verified end state
Greeter renders, password login succeeds, Caelestia shell (`qs -c caelestia`) + dashboard appear at 1920x1200, Chicago time, 24h clock.

## Credentials / state left on the VM
user `wils` and `root` password `caelestia` (user should change); temp sudoers drop-in removed; 20 GiB disk = single ext4 root.
