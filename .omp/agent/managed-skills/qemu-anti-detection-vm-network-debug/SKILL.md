---
name: qemu-anti-detection-vm-network-debug
description: "Diagnose a silent/unidentified NIC in the qemu-anti-detection UndetectableVM libvirt guest on this host: host-side verification (tap on virbr0, dnsmasq leases, tcpdump), guest-side triage (disable/enable, Device Manager), the e1000e→e1000 NIC-model swap fix with the stop/define/start procedure, and the definitive root cause — host ufw firewall dropping guest DHCP (UDP 67) on virbr0 — fixed with ufw allow/route rules plus a virsh detach/attach NIC bounce."
---

# QEMU Anti-Detection VM Network Debug

Use when the qemu-anti-detection `UndetectableVM` libvirt guest (Windows 10/11, e1000/e1000e NIC on the `default` NAT network) has no network: Windows shows "Unidentified network" / "Ethernet N doesn't have a valid IP configuration", or the NIC appears present but never gets an IP.

## TL;DR — the actual root cause found on this host (2026-08-30)

**The guest's DHCP requests were being dropped by the HOST's ufw firewall**, not by any driver/NIC problem. Omarchy runs ufw with `Default: deny (incoming), deny (routed)`, and there was no allow rule for DHCP (UDP 67) inbound on the libvirt bridge. dnsmasq never saw the requests → no OFFER → no lease → "no valid IP configuration" forever.

**The fix (persistent):**
```bash
sudo ufw allow in on virbr0
sudo ufw allow out on virbr0
sudo ufw route allow in on virbr0
sudo ufw route allow out on virbr0
```
(`ufw route allow` is required because the default routed/FORWARD policy is deny.)

Then force the guest to re-run DHCP by bouncing the NIC (or just wait for Windows' periodic retry):
```bash
sudo virsh detach-interface UndetectableVM network --config --live --mac f0:bc:8e:cd:6e:ec
sudo virsh attach-interface UndetectableVM network default --model e1000 --mac f0:bc:8e:cd:6e:ec --live --config
```

## Full diagnosis sequence

1. **Host-side verification** (do this first — it's fast and rules the host in/out):
   ```bash
   sudo virsh net-list --all                    # default should be active
   sudo virsh net-dumpxml default               # NAT mode, virbr0, DHCP range
   ip -br addr show virbr0                      # UP, 192.168.122.1/24
   bridge link show master virbr0               # guest tap (vnetN) attached, state forwarding
   sudo virsh net-dhcp-leases default           # EMPTY = guest never got a lease
   sudo tcpdump -i virbr0 -nn -e                # watch for f0:bc:8e:cd:6e:ec frames
   ```
   The tap MAC shows as `fe:bc:8e:...` in `ip` output even though the domain MAC is `f0:bc:8e:...` — that's the bridge masking the locally-administered bit, normal.
   `pgrep -af "dnsmasq.*default.conf"` showing TWO processes is normal (parent+child fork), not a conflict.

2. **Interpretation of captures:**
   - **Zero frames from the guest MAC on virbr0/vnetN** (only STP BPDUs every ~2s) → guest NIC is silent → guest-side problem (adapter disabled, driver not bound, or cable state).
   - **Guest sends DHCP DISCOVER/REQUEST (0.0.0.0.68 → 255.255.255.255.67) but no OFFER ever comes back** → host-side problem: dnsmasq not receiving (firewall) or not replying. THIS was the real case here.
   - Guest with link-local 169.254.x.x + IGMP/SSDP chatter = adapter works, DHCP failing.

3. **Firewall check (the decisive one):**
   ```bash
   nft list table ip libvirt_network        # libvirt's own chains (guest_input/guest_output/guest_nat)
   nft -a list chain ip filter INPUT        # look for: udp dport 67 ... jump ufw-skip-to-policy-input
   ufw status verbose
   ```
   If INPUT policy is `drop` and DHCP port 67 traffic jumps to ufw's skip-to-policy, requests never reach dnsmasq. The `udp sport 67 udp dport 68 accept` rule is only for the REPLY direction; the REQUEST (dport 67) needs an explicit allow.

4. **Guest-side triage** (if host is confirmed clean): in Windows — `ncpa.cpl` → Disable/Enable the adapter; Device Manager → Network adapters → check for yellow bang / "Code 10" (driver truly missing/broken); check "Jumbo Packet" / "Interrupt Moderation" advanced settings if silent.

## NIC model swap (e1000e → e1000) — if still needed

Windows 10 bundles drivers for both. e1000e presents as Intel 82574L, e1000 as Intel PRO/1000 MT (82540EM). Swap only as a robustness measure; it does NOT fix firewall-blocked DHCP (it just makes the adapter re-enumerate as a new device, which sometimes makes Windows retry DHCP).

```bash
# edit /tmp/vm-anti-detect/undetectable-vm-win10.xml: <model type="e1000e"/> → <model type="e1000"/>
virt-xml-validate /tmp/vm-anti-detect/undetectable-vm-win10.xml   # ALWAYS validate — virsh define silently drops invalid devices
sudo virsh destroy UndetectableVM
sudo virsh define /tmp/vm-anti-detect/undetectable-vm-win10.xml
sudo virsh start UndetectableVM
```

## Gotchas learned the hard way

- **`virsh define` silently discards schema-invalid devices.** The guide's original XML placed `<controller>` outside `<devices>` → disks/interface vanished from the domain with no error. Always `virt-xml-validate` first, and verify with `virsh dumpxml | grep -E '<disk|<interface'` after define.
- **sudo is fingerprint-gated on this host** (Omarchy polkit). Run sudo through an interactive PTY (hub session); the "Place your right index finger" prompt is a real GUI polkit dialog the user must scan for. Chain all sudo commands into ONE invocation to minimize auth prompts; the first sudo in a session always prompts.
- **VM files live in /var/lib/libvirt/images/** (disk.img raw sparse, Win10 ISO) — NOT /tmp (tmpfs, wiped on reboot, and /home/wils is 700 so libvirt-qemu can't traverse it).
- After `virsh net-destroy default` + `net-start`, virbr0 may show NO-CARRIER and the guest goes quiet — bounce the NIC (detach/attach above) to force Windows to renegotiate.
- Confirm success with `virsh net-dhcp-leases default` — the guest should appear as e.g. `192.168.122.194/24` with hostname DESKTOP-xxxx.
