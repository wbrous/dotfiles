---
name: libvirt-vm-mitmproxy-egress-capture
description: "Use when setting up transparent HTTP/HTTPS egress capture for a libvirt/KVM analysis VM (malware detonation box) with mitmproxy on the host — especially when libvirt 12.x's dnsmasq:options DNS-logging extension fails RelaxNG validation, or when the host firewall is nftables-backed (Arch/Omarchy with Tailscale+ufw xtables shims) and you need to redirect guest traffic to a proxy. Covers the nftables nat-prerouting redirect that works, mitmweb transparent mode flags, the HTTPS-decryption CA step in the Windows guest, and why flows.mitm stays empty while the guest is idle."
---

# Transparent mitmproxy egress capture for a libvirt analysis VM

Intercept and log every HTTP/HTTPS request a KVM guest (malware sample) makes, from the host, without guest-side proxy config. This is the observability half of a detonation sandbox: the sample talks, mitmproxy records host/URL/headers/timing/body.

## When libvirt's own DNS logging fails (Arch, libvirt 12.x)

Trying to enable dnsmasq query logging via `<dnsmasq:options>` in the network XML **fails RelaxNG validation** on libvirt 12.6 even though the schema (`/usr/share/libvirt/schemas/network.rng`, around line 447) declares the extension: `Expecting a namespace for element option`. This is a parser/schema mismatch in that version. **Do not fight it** — don't hack the auto-generated `/var/lib/libvirt/dnsmasq/default.conf` (it's rewritten on network restart). Use host-side capture (below) instead, which also captures more than DNS.

## Architecture

- Host runs `mitmweb --mode transparent` listening on :8080 (0.0.0.0), web UI on :8081 (127.0.0.1).
- An nftables `nat prerouting` redirect sends guest-originated tcp/80 and tcp/443 to :8080.
- Guest keeps normal NAT internet; only new web connections are intercepted.

## Host firewall reality (Omarchy/Arch: nftables backend)

The live firewall is **nftables** (with xtables shims from ufw + Tailscale `ts-*` chains). `iptables -t nat -L PREROUTING` shows an empty chain — adding rules there via iptables does not reliably interpose. Add a **separate nft table** (independent of libvirt's `libvirt_network` table) so libvirt network restarts don't clobber it:

```sh
pacman -S --noconfirm mitmproxy          # provides mitmweb + mitmdump
mkdir -p mitm-$(date +%Y%m%d-%H%M%S)

mitmweb --mode transparent \
  --listen-host 0.0.0.0 --listen-port 8080 \
  --web-host 127.0.0.1 --web-port 8081 \
  --set web_open_browser=false --set block_global=false \
  --save-stream-file mitm-<ts>/flows.mitm &

nft add table ip mitm_egress
nft add chain ip mitm_egress prerouting '{ type nat hook prerouting priority 0; }'
nft add rule ip mitm_egress prerouting iif virbr0 tcp dport { 80, 443 } redirect to :8080
```

Cleanup on exit (trap): `nft delete table ip mitm_egress`.

## Verification pitfalls

- `flows.mitm` stays **0 bytes** while the guest is idle — Windows makes no web requests at idle. A 0-byte flow file is NOT a failure; it means no traffic yet. Verify by opening a plain-http site (`http://neverssl.com`) in the guest, then check the web UI at `http://127.0.0.1:8081`.
- Transparent mode only catches **new** connections; already-established TCP passes through.
- Confirm listener with `/proc/net/tcp` (`:1F90` = 8080 on 0.0.0.0, `:1F91` = 8081 on 127.0.0.1) — `ss -tlnp` may miss it when run from a non-root PTY context.

## HTTPS body decryption (guest CA trust)

Without it you capture hostname/SNI/URL/timing but not bodies. To decrypt, install mitmproxy's CA into the analysis guest (standard sandbox practice, but a conscious guest-side change):

- CA cert: `~/.mitmproxy/mitmproxy-ca-cert.cer` (generated on first run; `.cer` is the Windows-friendly format)
- Copy it into the guest (loop-mount the raw disk — see libvirt-windows-guest-write-files-mount — or attach an ISO) then in the guest:
  ```
  certutil -addstore "Root" mitmproxy-ca-cert.cer
  ```
  Reboot the guest; mitmproxy then decrypts its HTTPS.

## Companion tooling

- `capture-detonation.sh` pattern: tcpdump on virbr0 (`not stp and not port 5900`) to a timestamped pcap + separate `udp port 53` DNS-query log + `tcp port 80` HTTP log. Same host-side observability goal, passive (no interception), works even when mitmproxy isn't wanted.
- Per-detonation identity randomization (`randomize-vm.py`): randomize MAC, domain UUID, SMBIOS serials (inject `serial=` where absent — a missing serial is itself a VM tell), disk serial, then redefine+restart. Regex-inject carefully: append `,serial=X` inside the `qemu:arg value` string before the closing quote; never double-quote.
