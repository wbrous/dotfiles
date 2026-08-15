---
name: tailscale-forwarding-warnings-fix
description: "Use when tailscale/tailscaled prints \"IPv6 forwarding is disabled\" and/or \"UDP GRO forwarding is suboptimally configured on iface\" warnings on Arch Linux (or similar), and subnet routes / exit nodes aren't working correctly."
---

## Symptom
Tailscale warns on start/status:
```
Warning: IPv6 forwarding is disabled. ... See https://tailscale.com/s/ip-forwarding
Warning: UDP GRO forwarding is suboptimally configured on <iface> ... See https://tailscale.com/s/ethtool-config-udp-gro
```

## Fix (Arch Linux)

1. Enable IPv6 forwarding now + persist across reboot:
```
sudo sysctl -w net.ipv6.conf.all.forwarding=1
echo 'net.ipv6.conf.all.forwarding=1' | sudo tee /etc/sysctl.d/99-tailscale.conf
```
(IPv4 forwarding is usually already on via tailscaled/systemd; check with `sysctl net.ipv4.ip_forward`.)

2. `ethtool` may not be installed on minimal Arch — install it:
```
sudo pacman -S --noconfirm ethtool
```

3. Apply the UDP GRO forwarding tune to the actual uplink interface (find name via `ip route` / `ip link`, e.g. `wlp192s0`):
```
sudo ethtool -K <iface> rx-udp-gro-forwarding on rx-gro-list off
```

4. Verify:
```
sysctl net.ipv6.conf.all.forwarding
ethtool -k <iface> | grep -i gro
```
Expect `net.ipv6.conf.all.forwarding = 1`, `rx-udp-gro-forwarding: on`, `rx-gro-list: off`.

## Caveat
The `ethtool -K` NIC setting is NOT persistent across reboot/link resets — Arch has no built-in unit for it. Either re-run the `ethtool -K` command after reboots, or create a systemd oneshot unit (e.g. `/etc/systemd/system/tailscale-gro-fix.service` with `ExecStart=/usr/bin/ethtool -K <iface> rx-udp-gro-forwarding on rx-gro-list off`, `WantedBy=multi-user.target`) if persistence is needed — do this proactively next time rather than just noting it.

## Notes
- These commands need sudo/root; on systems with fingerprint/PAM sudo, expect an interactive prompt via a pty-backed session.
- `pacman -Q ethtool` fails ("was not found") if not installed — that's expected on a minimal install, not an error to debug further.
