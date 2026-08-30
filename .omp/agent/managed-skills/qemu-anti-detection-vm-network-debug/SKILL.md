---
name: qemu-anti-detection-vm-network-debug
description: "Use when the Windows guest on the libvirt/patched-QEMU anti-detection VM (UndetectableVM, e1000e NIC) shows \"Unidentified network\" / no internet / no traffic — covers the host-side verification procedure (network active, dnsmasq leases, tap-on-bridge, tcpdump on the tap) that proves whether the fault is host or guest, and the guest-side fixes for a silent-but-present e1000e adapter (Disable/Enable, driver rebind, jumbo packet/interrupt moderation, NIC model swap to e1000)."
---

# QEMU Anti-Detection VM — Silent NIC / "Unidentified Network" Debug

Symptom: Windows guest on the anti-detection VM (libvirt `UndetectableVM`, patched QEMU 10.2.2, e1000e NIC, hidden hypervisor) shows "Unidentified network" or no internet. Windows *sees* the adapter but it transmits nothing.

## Host-side verification (proves host is healthy, fault is in guest)

Run as sudo (fingerprint-gated on Omarchy; use a PTY/hub session — `sudo -n` fails silently):

```bash
# 1. Network active + virbr0 up
virsh net-list --all                  # default should be active
ip -brief addr show virbr0            # 192.168.122.1/24 UP

# 2. dnsmasq serving + lease history
pgrep -af dnsmasq
cat /var/lib/libvirt/dnsmasq/default.leases   # EMPTY = guest never got a lease
virsh net-dhcp-leases default

# 3. Tap attached to bridge
ip -d link show vnet5                 # master virbr0, state forwarding, promisc

# 4. Definitive test — capture on the tap itself (not virbr0)
sudo timeout 12 tcpdump -i vnet5 -nn -c 30
# Guest healthy  → DHCP DISCOVER / ARP / broadcast traffic
# Guest silent   → only STP BPDUs every ~2s (bridge's own frames) = guest NIC transmits NOTHING
```

Interpretation:
- `default.leases` empty + ARP table on virbr0 empty + tap capture shows only STP → **guest-side problem, host network 100% healthy**. Not NAT/firewall/ufw (FORWARD drop rules only matter for L3 outbound; bridge-local DHCP/ARP is L2 and worked fine for the Reference VM).
- tcpdump is not installed by default on Arch — `pacman -S tcpdump`.
- Stale libvirtd errors about "nonexistent bridge WiFi Card" in `journalctl -u libvirtd` are transient from redefines; ignore if current `virsh dumpxml` interface shows `type='network'` + `bridge='virbr0'` + `e1000e`.

## Why: guest-side silent-but-present adapter

Windows 10 bundles the e1000e driver (Intel 82574L), so it's almost never a *missing* driver. The anti-detection config (hidden hypervisor, `hv-vendor-id=GenuineIntel`, spoofed CPUID, SMM+OVMF) can leave the adapter bound but not transmitting — a truly broken driver would show a yellow bang / Code 10 instead.

## Guest-side fixes, in order

1. **Disable → Enable** the adapter: `Win+R` → `ncpa.cpl` → right-click Ethernet → Disable, then Enable (forces driver rebind + DHCP retry). Most likely fix.
2. Device Manager → Network adapters → Intel(R) 82574L → Update driver → Search automatically, then reboot guest.
3. Adapter Properties → Advanced → set **Jumbo Packet** and **Interrupt Moderation** to **Disabled**, then Disable/Enable again.
4. If still dead: **swap NIC model `e1000e` → `e1000`** in the domain XML (simpler, more bulletproof Intel model for Windows; slightly less realistic device name but still real Intel ID — minor anti-detection tradeoff). Requires stop/define/start; disk persists.

## Environment specifics

- Host: Omarchy/Arch, libvirt 12.x, patched QEMU 10.2.2 at `/usr/local/bin` (libvirt resolves it), ufw + Tailscale `ts-*` chains present (not the cause).
- VM: `UndetectableVM`, `pc-q35-10.2`, OVMF UEFI, SPICE/QXL display, e1000e on `default` NAT network (192.168.122.0/24).
- `virsh` from a user shell shows empty lists until re-login picks up the `libvirt` group; use `sudo virsh` via PTY.
