# libvirt Setup on Arch

Fix the two common "daemon not running" failures on Arch's modular libvirt, and install Arch + Caelestia into a libvirt VM driven from the host.

## Fix "Unable to connect to libvirt qemu:///system"

**Symptom:** virt-manager or `virsh -c qemu:///system list --all` fails with `Failed to connect socket to '/var/run/libvirt/virtqemud-sock': No such file or directory`.

**Cause:** Arch libvirt 12.x uses modular socket-activated daemons, not the legacy monolithic `libvirtd`. `virtqemud.socket` is disabled by default. Legacy `libvirtd.service` being dead is NORMAL — don't chase it.

**Fix:**

```bash
systemctl enable --now virtqemud.socket virtqemud-ro.socket
```

`virtqemud.service` spawns on demand via socket activation; no need to enable the service. Verify with `virsh -c qemu:///system list --all` (exit 0), then reconnect in virt-manager (File → Add Connection → qemu:///system). No reboot needed.

_Migrated from: arch-libvirt-virtqemud-not-running_

## Missing virtnetworkd / virtstoraged / virtnodedevd / virtsecretd socket

**Symptom:** `Failed to connect socket to '/var/run/libvirt/virtnetworkd-sock'` (or virtstoraged/virtnodedevd/virtsecretd), e.g. on domain start or "Validating install media failed".

**Cause:** Same modular-daemon story: each driver daemon's sockets ship disabled. Map: network→virtnetworkd, storage pools/ISO validation→virtstoraged, host devices→virtnodedevd, secrets→virtsecretd.

**Fix (enable all missing drivers at once; plain, -ro, -admin sockets each):**

```bash
sudo systemctl enable --now virtstoraged.socket virtstoraged-ro.socket virtstoraged-admin.socket \
  virtnodedevd.socket virtnodedevd-ro.socket virtnodedevd-admin.socket \
  virtsecretd.socket virtsecretd-ro.socket virtsecretd-admin.socket
sudo systemctl enable --now virtnetworkd.socket virtnetworkd-ro.socket virtnetworkd-admin.socket
```

Verify: `virsh -c qemu:///system pool-list --all` (storage) and `virsh -c qemu:///system net-list --all` (network). Notes: `virbr0` DOWN with no VM running is normal; always use `virsh -c qemu:///system` (bare `virsh` may query the wrong socket); reopen the client app if it cached the failed connection.

_Migrated from: arch-libvirt-virtnetworkd-socket-missing_

## Installing Arch + Caelestia into a libvirt VM (patched-QEMU host)

**Symptom:** Need a Caelestia (Hyprland shell) Arch guest on a host whose patched QEMU spoofs virtio PCI IDs, so virtio-net/blk/gpu don't bind in the guest.

**Driving the guest console:** `wtype` into virt-manager produces garbled text — don't use it. Use `virsh -c qemu:///system send-key DOMAIN KEY_...` per character (US layout) via a small python helper that validates every char has a keycode first. Once in the live ISO: `echo root:live | chpasswd; systemctl start sshd`, then SSH in with `sshpass` (guest IP from `virsh net-dhcp-leases default` — IP changes per boot, newest lease wins — or `domifaddr DOMAIN --source arp`). Avoid long foreground SSH commands; use `nohup sh -c '...; echo EXIT=$? >> log' &` plus one wait loop. Take `grim` screenshots in a separate bash call.

**Patched-QEMU device workarounds (virtio PCI IDs spoofed, no virtio binding):**

- NIC → `e1000` (detach, then `attach-device` with XML pinned to the same `<address type='pci' bus='0x01' .../>`; plain attach-interface fails "No more available PCI slots"). Guest sees `enp1s0`.
- Disk → `bus='sata'` `dev='sdb'`; remove alias/pci-address from its XML, redefine from `dumpxml --inactive`. Disk appears as /dev/sda (ISO is sr0).
- Video → virtio-vga stays on `simpledrm` at 640x480 (unusable). Use `<model type='vga' vram='65536' heads='1' primary='yes'/>`; `bochs-drm` binds and offers 1280x800+.
- Redefine while running leaves old config live: `virsh destroy` first, then define + start. BIOS (SeaBIOS) guest: MBR + `grub-install --target=i386-pc /dev/sda`; after install `change-media sda --eject --config`, delete `<boot dev='cdrom'/>`, redefine.

**Install flow:** parted msdos single ext4, pacstrap `base linux linux-firmware base-devel git sudo networkmanager grub vim openssh qemu-guest-agent`, genfstab, arch-chroot (locale, hostname, wheel user, grub, enable NetworkManager + sshd). Reboot; temp `NOPASSWD` sudoers drop-in for install, REMOVE afterwards. `paru-bin` FAILS (links libalpm.so.15, system has 16) — build source `paru` from AUR instead (~3 min, needs `rust`). `paru -S caelestia-cli`, then `caelestia install --aur-helper paru --noconfirm`. First run fails on `pipewire-jack and jack2 conflict` (--noconfirm answers N): `pacman -Rdd jack2` first, rerun (~8 min). Installer's `hyprctl reload` hook exit 1 is expected (Hyprland not running).

**Login manager (greetd + Astra Airlock):** `paru -S --noconfirm --needed --skipreview greetd cage astra-airlock`. `/etc/greetd/config.toml`: `[terminal] vt = 1`, `[default_session] command = "cage -s -- astra-airlock >/dev/null 2>&1"`, `user = "greeter"`. Add `auth optional pam_gnome_keyring.so` + `session optional pam_gnome_keyring.so auto_start` to `/etc/pam.d/greetd` (AUR package omits them). `usermod -aG video,input greeter`; `install -d -o greeter -g greeter /var/cache/astra-airlock`; `sudo astra-airlock --sync`; `systemctl enable greetd`. Remove any manual `exec Hyprland` from ~/.bash_profile. Gotcha: hyprland ships `hyprland-uwsm.desktop` (TryExec=uwsm) which Airlock lists and defaults to — login authenticates then the session dies instantly. Fix: set `userSessions.<user>` to `hyprland` in `/var/cache/astra-airlock/greeter.json` and restart greetd. Greeter keeps its own (possibly letterboxed) resolution and `use12Hour` in greeter.json (default false).

**Post-install tweaks:** timezone defaults to UTC — `timedatectl set-timezone America/Chicago`, `systemctl enable --now systemd-timesyncd`. 24h clock: `~/.config/caelestia/shell.json` → `{"services": {"clockFormat": "TwentyFourHour"}}` (applies live). Display: `~/.config/caelestia/hypr-user.lua` with `hl.monitor({ output = "", mode = "WxH@60", position = "auto", scale = 1 })`, then `hyprctl reload`; bochs-drm has no 3:2 modes but Hyprland accepts custom ones (e.g. 1920x1280@60 for a 3:2 host panel). Run hyprctl as the user over SSH with `XDG_RUNTIME_DIR=/run/user/1000` and `HYPRLAND_INSTANCE_SIGNATURE=$(ls $XDG_RUNTIME_DIR/hypr | head -1)`.

_Migrated from: arch-caelestia-install-in-libvirt-patched-qemu-vm_
