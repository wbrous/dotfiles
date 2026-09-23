---
name: local-dot-local-hostname-caddy-dev-proxy
description: "Use when setting up a temporary local reverse-proxy setup so a browser can reach services via friendly hostnames like foo.local / foo-admin.local instead of localhost:PORT — especially for testing a multi-service app (e.g. Logto: public app + admin console) where one service's Admin/Web-Crypto UI requires a secure context. Also covers the systemd/Arch nsswitch.conf gotcha where .local hostnames in /etc/hosts are silently ignored because mdns_minimal is queried before files, the browser HTTPS-auto-upgrade trap that breaks a plain-HTTP-only proxied port, and a Host-header-based backend routing trap where a reverse-proxied app (e.g. Logto) decides \"which service/tenant is this?\" by matching Host/X-Forwarded-Host against a hardcoded internal endpoint config rather than the listening port — requiring the proxy to rewrite Host (and X-Forwarded-Host/Proto/Port) to the internal expected value even though the browser-facing hostname is different."
---

## Problem

Want `foo.local` / `foo-admin.local` (etc.) in the browser instead of `localhost:PORT`, for local testing only — temporary, not meant to be committed or made permanent.

## Recipe

1. Add entries to `/etc/hosts`: `127.0.0.1 foo.local foo-admin.local` (needs sudo — see fingerprint gotcha below).
2. Run a local Caddy instance (portable binary, no install needed: `curl -sL "https://caddyserver.com/api/download?os=linux&arch=amd64" -o ~/.local/bin/caddy && chmod +x ~/.local/bin/caddy`) with a **temporary** Caddyfile reverse-proxying each hostname to its real `127.0.0.1:PORT`.
3. Use unprivileged ports (e.g. `18080`, `18443`) to avoid needing root to bind 80/443, and to sidestep collisions with whatever else may already be squatting on 8080 on a dev box — check with `ss -ltn` first, don't assume a port is free from memory.
4. Update the app's own `ENDPOINT`-style env var to the new public hostname/port so self-referencing URLs (OIDC issuer, asset links, etc.) match what the browser will actually hit, then restart just that container.

## Gotcha 1: `.local` silently ignored by `/etc/hosts` (systemd/Arch specific)

Default `/etc/nsswitch.conf` on systemd-resolved systems often has:
```
hosts: mymachines mdns_minimal [NOTFOUND=return] resolve files myhostname dns
```
`[NOTFOUND=return]` on `mdns_minimal` means: if mDNS resolution for a `.local` name comes back not-found, **stop immediately** — `files` (i.e. `/etc/hosts`) is never even reached. `getent hosts foo.local` returns nothing even though the entry is clearly present in `/etc/hosts`.

Fix (temporary, revert on cleanup): back up and reorder so `files` comes first:
```
sudo cp /etc/nsswitch.conf /etc/nsswitch.conf.BACKUP-SUFFIX
sudo sed -i 's/^hosts:.*/hosts: files mymachines resolve myhostname mdns_minimal [NOTFOUND=return] dns/' /etc/nsswitch.conf
```
Verify with `getent hosts foo.local` before assuming the browser will resolve it. Restore from the backup on cleanup — this is a system-wide change affecting all `.local`/mDNS resolution (printers, Chromecasts, etc.) for the duration of the test.

## Gotcha 2: browser HTTPS-auto-upgrade breaks a plain-HTTP-only proxied port

Modern Firefox/Chrome auto-upgrade `http://` navigations to `https://` by default. If Caddy is only listening HTTP on that port, the browser's TLS ClientHello hits a plain HTTP server and you get `SSL received a record that exceeded the maximum permissible length` (Firefox) or similar.

Fix: don't fight the browser — make the port genuinely HTTPS via Caddy's `tls internal` (self-signed local CA, no ACME/DNS needed):
```caddyfile
{
	auto_https disable_redirects   # prevents Caddy trying to bind :80 for an HTTP->HTTPS redirect (permission denied if non-root)
}

https://foo.local:18080 {
	tls internal
	reverse_proxy 127.0.0.1:3001
}
```
One cert-warning click-through per domain per browser session; no system trust-store changes needed for casual local testing.

## Gotcha 3: reverse-proxied app routes by Host header against an internal endpoint config, not by port

Some apps (e.g. Logto, which serves both its public app and its admin console from the same process pool) decide "which service is this request for?" by matching the incoming `Host` / `X-Forwarded-Host` header against a hardcoded internal config value (e.g. `ADMIN_ENDPOINT=http://localhost:3002`) — **not** simply by which backend port was hit. If Caddy forwards the real external hostname (`foo-admin.local:18443`) unchanged, the app doesn't recognize the request as "admin traffic," silently falls through to default/core behavior, and you get a confusing generic error (e.g. Logto's "Session not found. Please go back and sign in again" 404 — the *same* error page the main app shows when hit with no active session, making the two failures look identical and the actual root cause invisible from the browser alone).

Diagnosis: curl the backend directly (`curl -sL http://localhost:3002/`) and compare against curling through the proxy (`curl -skL https://foo-admin.local:18443/`) — if the direct hit redirects correctly (e.g. to `/console/welcome`) but the proxied hit redirects somewhere else entirely (e.g. back to the *other* service's public hostname), that's the signature of this bug.

Fix: rewrite **both** `Host` and the `X-Forwarded-*` headers to match what the app's internal config expects, even though the browser-facing hostname is different:
```caddyfile
https://foo-admin.local:18443 {
	tls internal
	reverse_proxy 127.0.0.1:3002 {
		header_up Host localhost:3002
		header_up X-Forwarded-Host localhost:3002
		header_up X-Forwarded-Proto http
		header_up X-Forwarded-Port 3002
	}
}
```
Rewriting `Host` alone is often insufficient if the app has `TRUST_PROXY_HEADER`-style config enabled — it may prioritize `X-Forwarded-Host` over the raw `Host` header, so both must be overridden together.

## Fingerprint-gated sudo

On a machine with fingerprint-gated `sudo` (fprintd/polkit), the `/etc/hosts` and `/etc/nsswitch.conf` edits need a physical touch. Use `hub start` with `pty: true` to surface the interactive prompt (see `sudo-interactive-tty-via-hub`), tell the user a prompt is pending, and `hub wait`/`hub logs` to observe completion — it can time out once and need a retry; that's normal, not a sign of failure.

## Cleanup (this is meant to be temporary)

- Stop the Caddy process.
- `docker compose down -v` (or equivalent) for the proxied app.
- Remove the added `/etc/hosts` lines.
- Restore `/etc/nsswitch.conf` from the backup made in Gotcha 1.
