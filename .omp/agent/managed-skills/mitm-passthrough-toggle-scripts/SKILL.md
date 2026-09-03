---
name: mitm-passthrough-toggle-scripts
description: "Use when enabling or disabling transparent mitmproxy egress capture for the libvirt analysis VM via the ~/.local/bin/mitm-passthrough-enable and mitm-passthrough-disable scripts — companion tooling to the libvirt-vm-mitmproxy-egress-capture skill's manual nftables/mitmweb recipe."
---

## What exists

Two executable scripts in `~/.local/bin/` wrap the manual recipe from
`libvirt-vm-mitmproxy-egress-capture` into idempotent enable/disable commands:

- `mitm-passthrough-enable` — starts `mitmweb --mode transparent` (listen
  0.0.0.0:8080, web UI 127.0.0.1:8081), waits 1s for it to bind and verifies
  it's alive, then adds the `mitm_egress` nftables table
  (`nat prerouting`, `iif virbr0 tcp dport {80,443} redirect to :8080`).
  Refuses to run if the nftables table already exists or a tracked mitmweb
  pid is already alive. Flow file saved to
  `~/.local/state/mitm-passthrough/mitm-<timestamp>/flows.mitm`. mitmweb pid
  tracked in `~/.local/state/mitm-passthrough/mitmweb.pid`.

- `mitm-passthrough-disable` — deletes the `mitm_egress` nftables table (via
  `sudo -n nft list table ip mitm_egress` check first, so it no-ops silently
  if absent), stops the tracked mitmweb pid (SIGTERM, poll up to 4s, SIGKILL
  fallback), and sweeps any stray `mitmweb --mode transparent` process not
  tracked by the pid file. Prints "already disabled (nothing to do)" if there
  was nothing to tear down — safe to run anytime as a sanity check.

Both use `MITM_BRIDGE` / `MITM_LISTEN_PORT` / `MITM_WEB_PORT` env vars to
override defaults (`virbr0` / `8080` / `8081`).

## Checking current state without running either script

```sh
sudo -n nft list table ip mitm_egress   # exit 0 = redirect active
pgrep -f 'mitmweb --mode transparent'   # non-empty = mitmweb running
```

Both commands need passwordless-cached sudo or will prompt (fingerprint/
password) — see sudo-interactive-tty-via-hub skill if driving this from an
agent without a live TTY.

## Note

This is companion tooling, not a replacement for the underlying skill —
consult `libvirt-vm-mitmproxy-egress-capture` for the HTTPS CA-trust step,
verification pitfalls (flows.mitm staying 0 bytes while guest is idle), and
why nftables (not iptables) is the correct interposition point on this
Arch/Omarchy host.
