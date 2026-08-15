---
name: cloudflare-free-ssl-single-level-wildcard
description: "Use when setting up cloudflared tunnels, DNS records, or any hostname under a Cloudflare zone where the hostname has two or more subdomain levels below the zone apex (e.g. api.foo.example.com where example.com is the zone) — especially when TLS fails with SSL_ERROR_NO_CYPHER_OVERLAP or a generic handshake-failure/TLS alert 40, since Cloudflare's free Universal SSL wildcard only covers one level (*.example.com), not two (*.foo.example.com)."
---

## Symptom
A hostname two+ levels below a Cloudflare zone apex (e.g. zone is `example.com`,
hostname is `api.foo.example.com` — two levels below apex) fails TLS with:
- Firefox/Zen: `SSL_ERROR_NO_CYPHER_OVERLAP`
- curl: `TLS connect error: error:0A000410:SSL routines::ssl/tls alert handshake failure`
- openssl s_client: `SSL alert number 40` (handshake_failure), no peer certificate

DNS resolves fine, cloudflared tunnel connects fine, `cloudflared tunnel route dns`
succeeds — the problem is purely: no valid edge certificate covers that hostname.

## Root cause
Cloudflare's free Universal SSL issues a certificate covering the zone apex and
`*.example.com` (one wildcard level) only. A hostname like `api.foo.example.com`
(two levels below apex) is NOT covered by that wildcard. Covering it requires a
paid Advanced Certificate Manager (ACM) add-on with a custom hostname cert.

## Fix (free, no paid add-on)
Restructure the hostname to be exactly one level below the zone apex instead of
two — e.g. use `foo-api.example.com` (sibling of `foo.example.com`) instead of
`api.foo.example.com`. Both are covered by the same free `*.example.com` wildcard.

Steps to migrate an already-created cloudflared tunnel ingress hostname:
1. `cloudflared tunnel route dns <tunnel-name> <new-one-level-hostname>` — adds the
   new CNAME pointing at the tunnel (does not remove the old one).
2. Edit `~/.cloudflared/config.yml` AND `/etc/cloudflared/config.yml` (the systemd
   service reads from `/etc/cloudflared/`, not `~/.cloudflared/`, when installed via
   `cloudflared service install` — both copies must be kept in sync manually, there's
   no symlink by default) — change the `ingress:` hostname entry.
3. `sudo systemctl restart cloudflared`
4. Verify: `curl -sS -o /dev/null -w '%{http_code}\n' https://<new-hostname>/<path>`
   — expect a real HTTP status (200/302/etc), not a curl exit 35 TLS error.
5. The old two-level CNAME record is now orphaned (unused, no ingress rule matches
   it) — harmless to leave, but delete it via Cloudflare dashboard DNS records if
   you want it tidy. `cloudflared tunnel route dns` has no built-in delete/remove.

## Diagnostic shortcut
`openssl s_client -connect <host>:443 -servername <host> </dev/null 2>&1` — if you
see "SSL alert number 40" / "no peer certificate available" with a clean TCP
connect, it's this depth-of-subdomain cert coverage issue, not a tunnel/DNS/config
problem. Don't waste time re-checking ingress rules or DNS propagation first.
