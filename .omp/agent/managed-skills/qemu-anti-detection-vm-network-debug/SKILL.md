---
name: qemu-anti-detection-vm-network-debug
description: "Diagnose a silent/unidentified NIC or dead DNS in the qemu-anti-detection UndetectableVM libvirt guest on this host: tcpdump/tap verification, ufw dropping guest DHCP, the e1000e→e1000 NIC-model swap, and the stale-DNS-after-network-churn NIC-bounce fix."
---

# QEMU Anti-Detection VM Network Debug

Use when the UndetectableVM (qemu-anti-detection patched QEMU + libvirt on Omarchy) guest has NO network, an "unidentified network", "Ethernet N doesn't have a valid IP configuration", or "DNS address could not be found".

## Symptom triage: is the guest transmitting AT ALL?

The single most decisive test: capture on the bridge while the guest is idle-but-up.

```bash
sudo tcpdump -i virbr0 -nn -e   # 15-20s window
```

- **Zero frames from the guest MAC** → guest NIC is silent (link-down/disabled state in Windows, or driver issue).
- **Guest sends DHCP DISCOVER but gets no OFFER** → host firewall (ufw) is dropping DHCP at INPUT.
- **Guest resolves nothing and sends NO port-53 packets** → stale DNS state in Windows from network churn (see below).

Also check, in order:
```bash
sudo virsh net-list --all                       # default active?
ip -br addr show virbr0                          # UP with 192.168.122.1/24
sudo virsh net-dhcp-leases default               # does the guest hold a lease?
sudo bridge link show master virbr0              # vnet tap attached?
sudo nft list table ip mitm_egress               # mitmproxy redirect only touches tcp 80/443 — NOT DNS
```

## Cause 1: host ufw firewall dropping guest DHCP (the big one)

On this Omarchy host, **ufw's INPUT and FORWARD policies are `drop`**, and there is NO libvirt rule allowing guest DHCP (UDP 67) at INPUT. Symptom: guest transmits DHCP fine (visible on virbr0) but `default.leases` stays empty forever, and Windows shows "no valid IP configuration". The smoking gun is the ufw-before-input rule `udp dport 67 → ufw-skip-to-policy-input` with a rising drop counter.

Fix (persistent ufw rules — survive reboot):

```bash
sudo ufw allow in on virbr0
sudo ufw allow out on virbr0
sudo ufw route allow in on virbr0
sudo ufw route allow out on virbr0
```

Then bounce the guest NIC so Windows re-runs DHCP:
```bash
MAC="f0:bc:8e:cd:6e:ec"   # from `virsh domiflist UndetectableVM`
sudo virsh detach-interface UndetectableVM network --config --live --mac "$MAC"
sudo virsh attach-interface UndetectableVM network default --model e1000 --mac "$MAC" --live --config
sudo virsh net-dhcp-leases default    # confirm a lease appears
```

## Cause 2: NIC model silently dead (e1000e)

If Windows shows the adapter present but it transmits NOTHING (zero frames on vnet tap, no warning icon in Device Manager), swap the NIC model — `e1000e` → `e1000` in the domain XML (`<model type='e1000'/>`), redefine, restart. e1000 (Intel 82540EM) is more bulletproof in Windows under the hidden-hypervisor setup. The `e1000` model then presents as "Intel(R) PRO/1000 MT Desktop Adapter" and transmits normally.

## Cause 3: stale guest DNS after libvirt network churn

Symptom: browser says "DNS address could not be found" AFTER the `default` network was destroyed/redefined (e.g. during egress/mitmproxy setup). The guest stops sending ANY DNS queries — tcpdump on virbr0 shows **0 packets on udp port 53** even though the NIC is up with a fresh lease. dnsmasq itself is fine (verify from host with a python UDP query to 192.168.122.1:53, since `dig`/`nslookup` are often not installed).

Fix: bounce the guest NIC (same detach/attach as Cause 1) — forces Windows to re-DHCP and re-apply its DNS server. Verified: after bounce the guest resolves normally (capture shows healthy query/answer pairs).

## Host-side resolution sanity checks (no dig/nslookup installed)

```bash
getent hosts example.com                     # host resolves?
ping -c1 -W2 1.1.1.1                          # upstream reachable?
python3 - <<'EOF'                             # query dnsmasq on virbr0 directly
import socket, struct, random
tid = random.randint(0,0xffff)
q = struct.pack('>HHHHHH', tid, 0x0100, 1, 0, 0, 0)
for part in 'example.com'.split('.'): q += bytes([len(part)]) + part.encode()
q += b'\x00' + struct.pack('>HH', 1, 1)
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(4)
s.sendto(q, ('192.168.122.1', 53)); d,_ = s.recvfrom(512)
print('answers:', struct.unpack('>H', d[6:8])[0])
EOF
```

## Guest-side notes

- `sudo -n virsh` from the user shell fails ("a password is required") — the libvirt group membership requires re-login; use `sudo virsh` via an interactive tty instead.
- Every sudo on this Omarchy box is fingerprint-gated (polkit) — the prompt appears on the desktop; commands wait at "Place your right index finger on the fingerprint reader" until scanned.
- virbr0 shows DOWN (no carrier) when the guest is off; it comes UP when the guest NIC attaches — not a fault.
- After `virsh net-destroy`/`net-start`, the guest tap is recreated with a new vnet index; the domain's interface re-attaches automatically but Windows may need the NIC bounce to re-sync DHCP/DNS.
