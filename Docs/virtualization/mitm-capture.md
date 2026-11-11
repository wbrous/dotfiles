# Transparent mitmproxy Egress Capture

Intercept and log every HTTP/HTTPS request a KVM analysis guest makes, from the host, without guest-side proxy config.

## Setup (nftables redirect + mitmweb)

The live firewall is **nftables** (xtables shims from ufw + Tailscale `ts-*` chains) — `iptables -t nat` rules don't reliably interpose. Add a separate nft table (independent of libvirt's table, so libvirt restarts don't clobber it):

```sh
pacman -S --noconfirm mitmproxy
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

Cleanup on exit (trap): `nft delete table ip mitm_egress`. libvirt 12.6's `<dnsmasq:options>` DNS-logging extension fails RelaxNG validation ("Expecting a namespace for element option") — do not fight it or hack `/var/lib/libvirt/dnsmasq/default.conf` (rewritten on restart); host-side capture covers more than DNS anyway.

_Migrated from: libvirt-vm-mitmproxy-egress-capture_

## Toggle scripts

`~/.local/bin/mitm-passthrough-enable` and `mitm-passthrough-disable` wrap the recipe above into idempotent commands. Enable starts `mitmweb --mode transparent` (0.0.0.0:8080, web UI 127.0.0.1:8081), verifies it bound, adds the `mitm_egress` table; refuses to run if the table exists or a tracked mitmweb pid is alive. Flow file: `~/.local/state/mitm-passthrough/mitm-<timestamp>/flows.mitm`; pid in `~/.local/state/mitm-passthrough/mitmweb.pid`. Disable deletes the table (no-ops silently if absent), SIGTERMs the tracked pid (poll 4s, SIGKILL fallback), sweeps strays. `MITM_BRIDGE` / `MITM_LISTEN_PORT` / `MITM_WEB_PORT` override defaults (`virbr0` / `8080` / `8081`). Both need passwordless-cached sudo or they prompt.

**Check state without running either:**

```sh
sudo -n nft list table ip mitm_egress   # exit 0 = redirect active
pgrep -f 'mitmweb --mode transparent'   # non-empty = mitmweb running
```

_Migrated from: mitm-passthrough-toggle-scripts_

## Verification pitfalls

- `flows.mitm` stays **0 bytes** while the guest is idle — Windows makes no web requests at idle. NOT a failure. Verify by opening `http://neverssl.com` in the guest, then check `http://127.0.0.1:8081`.
- Transparent mode only catches **new** connections; already-established TCP passes through.
- Confirm listener via `/proc/net/tcp` (`:1F90` = 8080, `:1F91` = 8081) — `ss -tlnp` may miss it from a non-root PTY.

_Migrated from: libvirt-vm-mitmproxy-egress-capture_

## HTTPS body decryption (guest CA trust)

Without it you capture hostname/SNI/URL/timing but not bodies. Install mitmproxy's CA into the analysis guest (conscious guest-side change, standard sandbox practice): CA cert `~/.mitmproxy/mitmproxy-ca-cert.cer` (`.cer` = Windows-friendly), copy into guest (loop-mount the disk or attach an ISO), then in the guest `certutil -addstore "Root" mitmproxy-ca-cert.cer` and reboot.

_Migrated from: libvirt-vm-mitmproxy-egress-capture_

## Passive alternative: capture-detonation.sh pattern

Root, capture on `virbr0` for N seconds: full pcap (`tcpdump -i virbr0 -w detonation.pcap`), `udp port 53` → dns-queries.txt, `tcp port 80` → http-requests.txt. Passive (no interception), works even when mitmproxy isn't wanted. Idle guest = 0 packets is expected.

_Migrated from: libvirt-vm-mitmproxy-egress-capture, qemu-anti-detection-vm-sensor-tsc-hardening_
