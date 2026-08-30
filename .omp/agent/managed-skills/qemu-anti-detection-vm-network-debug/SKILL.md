---
name: qemu-anti-detection-vm-network-debug
description: "Diagnose a silent/unidentified NIC in the qemu-anti-detection UndetectableVM libvirt guest on this host: host-side verification (tap on virbr0, dnsmasq leases, tcpdump), guest-side triage (disable/enable, Device Manager), and the e1000e→e1000 NIC-model swap fix with the stop/define/start procedure"
---

# qemu-anti-detection VM network debug

Use when the UndetectableVM (or any libvirt VM on this machine) shows "Unidentified network" / no internet in Windows, or the guest NIC appears present but transmits nothing.

## Host-side verification (proves host healthy in ~30s)

1. `sudo virsh net-list --all` — `default` must be `active`. If not: `sudo virsh net-start default && sudo virsh net-autostart default`.
2. `ip -brief addr show virbr0` — must be UP with `192.168.122.1/24`.
3. `pgrep -af dnsmasq` — libvirt dnsmasq must be running (`--conf-file=/var/lib/libvirt/dnsmasq/default.conf`).
4. `cat /var/lib/libvirt/dnsmasq/default.leases` — non-empty means guest got a lease; **empty + ARP empty = guest transmits nothing**.
5. Tap attached: `bridge link show master virbr0` — look for `vnetN` master virbr0.
6. **Decisive test**: `sudo timeout 12 tcpdump -i vnetN -nn` (the guest's tap). If only STP BPDUs appear and zero guest frames (no DHCP DISCOVER/ARP), the **guest NIC is silent — host is blameless**.
   - tcpdump may need installing: `sudo pacman -S --noconfirm tcpdump`.
   - Note: the vnet port's displayed MAC shows the locally-administered bit flipped (`fe:bc:…` vs domain's `f0:bc:…`) — that's normal bridge behavior.

## Guest-side triage (in Windows, via SPICE console)

1. `ncpa.cpl` → right-click Ethernet → **Disable → Enable** (forces driver rebind + DHCP retry). Most common fix for silent-but-present adapter.
2. Device Manager → Network adapters → check for yellow bang / Code 10. If present: Update driver → Search automatically.
3. No warning sign + disable/enable didn't help → the adapter is bound but never transmits: **swap the NIC model** (below).
4. Adapter Properties → Advanced → disable Jumbo Packet and Interrupt Moderation (occasional silent-failure culprits under hidden-hypervisor VMs).

## NIC model swap (e1000e → e1000)

The anti-detection XML uses `e1000e` (Intel 82574L). If Windows binds it but the guest sends zero frames (verified via tap capture), swap to plain `e1000` (Intel 82540EM — Windows 10 has inbox drivers, very robust under q35 + hidden hypervisor + SMM/OVMF).

Procedure:
1. Edit `/tmp/vm-anti-detect/undetectable-vm-win10.xml`: `<model type="e1000e"/>` → `<model type="e1000"/>` (use the edit tool's `»` block form; the `⟪⟫` inline form can be finicky).
2. Validate: `virt-xml-validate /tmp/vm-anti-detect/undetectable-vm-win10.xml` (MUST pass; `virsh define` silently drops invalid devices — see below).
3. `sudo virsh destroy UndetectableVM && sudo virsh define undetectable-vm-win10.xml && sudo virsh start UndetectableVM`.
4. Verify running process: `ps -eo args | grep qemu-system | grep -oE '"e1000"'` — must show `"e1000"` not `"e1000e"`.
5. In Windows the new adapter enumerates as "Intel(R) PRO/1000 MT Desktop Adapter"; give it ~30s to DHCP after boot before judging.

## Critical libvirt gotchas (learned the hard way)

- **`virsh define` SILENTLY DROPS devices** whose XML placement is schema-invalid (e.g. `<controller>` outside `<devices>`) — the domain "defines" OK but loses disks/interfaces. Always `virt-xml-validate` before define, and verify with `virsh dumpxml | grep <device>` after.
- The anti-detection guide's XML has NO `<graphics>`/`<video>` — add SPICE + QXL (mirror virt-manager defaults: `<graphics type="spice" autoport="yes">`, QXL video, usb-tablet, virtio-serial + spicevmc channel, ich9 sound + spice audio, 2× redirdev) or virt-manager shows "no graphical interface configured for guest".
- OVMF on Arch lives at `/usr/share/edk2/x64/OVMF_CODE.4m.fd` / `OVMF_VARS.4m.fd` (not the guide's non-`.4m` paths).
- qemu-anti-detection has no patch for QEMU 11.x; newest usable patch is `qemu-10.2.2.patch` against QEMU 10.2.2, installed to `/usr/local/bin` (libvirt picks it up for x86_64).
- libvirt-qemu can't traverse `/home/wils` (700) — keep disks/ISOs under `/var/lib/libvirt/images/`.
- `virsh` from the user's shell fails until re-login picks up the `libvirt` group; use `sudo virsh` (fingerprint-gated — the polkit prompt appears on the desktop; the user must scan).
- Windows install status check: `qemu-img info` / `du -h` on `/var/lib/libvirt/images/disk.img` — non-trivial size means the guest OS is installed.
