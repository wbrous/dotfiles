---
name: local-dot-local-hostname-caddy-dev-proxy
description: "Use when setting up a temporary local reverse-proxy setup so a browser can reach services via friendly hostnames like foo.local / foo-admin.local instead of localhost:PORT — especially for testing a multi-service app (e.g. Logto: public app + admin console) where one service's Admin/Web-Crypto UI requires a secure context. Also covers the systemd/Arch nsswitch.conf gotcha where .local hostnames in /etc/hosts are silently ignored because mdns_minimal is queried before files, and the browser HTTPS-auto-upgrade trap that breaks a plain-HTTP-only proxied port."
---

## Problem

Testing a multi-service local app (e.g. self-hosted Logto: public app on one port, admin console on another) where you want browser-friendly hostnames instead of `localhost:PORT` — e.g. `foo.local` for the app, `foo-admin.local` for the admin console — purely for a temporary local test, not a permanent system change.

## Components

1. **`/etc/hosts` entries** (needs sudo): `127.0.0.1 foo.local foo-admin.local`.
2. **A local Caddy instance** (no sudo needed if you avoid ports 80/443 — install the static binary to `~/.local/bin/caddy` via `curl -sL "https://caddyserver.com/api/download?os=linux&arch=amd64" -o ~/.local/bin/caddy && chmod +x ~/.local/bin/caddy`, and bind to unprivileged ports like `18080`/`18443` instead).
3. **Docker Compose `extra_hosts` override** if the containerized app makes internal self-calls back to its own public `ENDPOINT`-style URL (e.g. Logto's OIDC issuer self-validation) — the container's own DNS won't know `foo.local` unless you add `extra_hosts: ["foo.local:host-gateway"]` to that service via a temporary override compose file (`docker compose -f compose.yml -f /tmp/override.yml up -d --wait`), keeping the real repo `compose.yml` untouched.

## Gotcha 1: `.local` silently ignored by `/etc/hosts` on systemd/Arch systems

Check `/etc/nsswitch.conf`'s `hosts:` line. A common systemd-resolved-managed default is:

```
hosts: mymachines mdns_minimal [NOTFOUND=return] resolve files myhostname dns
```

`[NOTFOUND=return]` applies to the preceding `mdns_minimal` module: if mDNS resolution for a `.local` name comes back not-found, nsswitch **stops the chain right there** and never falls through to `resolve`/`files`/`dns` — so your `/etc/hosts` entry is never even consulted, no matter how correctly it's written. `getent hosts foo.local` will return nothing even though `cat /etc/hosts` shows the line.

**Fix (temporary, revert after testing):**
```bash
sudo cp /etc/nsswitch.conf /etc/nsswitch.conf.<test-name>-backup
sudo sed -i 's/^hosts:.*/hosts: files mymachines resolve myhostname mdns_minimal [NOTFOUND=return] dns/' /etc/nsswitch.conf
```
This restores standard Linux precedence (`files` first). Revert from the backup during cleanup — this is a system-wide change affecting real mDNS resolution (printers, Chromecasts, etc.) for the duration of the test.

Verify with `getent hosts foo.local` before troubleshooting anything else — if that returns empty, don't waste time debugging Caddy/Docker; fix nsswitch first.

## Gotcha 2: browser HTTPS-auto-upgrade breaks a plain-HTTP-only proxied port

Modern Firefox/Chrome auto-upgrade `http://` to `https://` for typed/bookmarked URLs by default. If one Caddy site block is plain HTTP only (e.g. the app, while the admin console legitimately needs `tls internal` for Web Crypto secure-context reasons), the browser will silently try HTTPS against that HTTP-only port and fail with `SSL_ERROR_RX_RECORD_TOO_LONG` / "SSL received a record that exceeded the maximum permissible length" — a classic TLS-ClientHello-against-plaintext-server signature.

**Fix:** make *every* proxied hostname genuinely HTTPS via Caddy's `tls internal` (self-signed local CA), not just the one that strictly needs it. Update the app's own `ENDPOINT`-style env var to `https://` too and restart/recreate that container so its OIDC issuer (or equivalent) matches. One cert-trust-warning click per domain in the browser is the tradeoff; it beats fighting the browser's upgrade behavior.

Also add a global Caddyfile block to stop Caddy's own automatic HTTP→HTTPS redirect from trying (and failing, unprivileged) to bind port 80:
```caddyfile
{
	auto_https disable_redirects
}
```

## Minimal working Caddyfile pattern

```caddyfile
{
	auto_https disable_redirects
}

https://foo.local:18080 {
	tls internal
	reverse_proxy 127.0.0.1:3001
}

https://foo-admin.local:18443 {
	tls internal
	reverse_proxy 127.0.0.1:3002
}
```

Start with: `caddy run --config Caddyfile --adapter caddyfile` (via a supervised background process, not persisted, so it dies with the session — matches "temporary" intent).

## Cleanup checklist (temporary setup — always revert)

1. Stop the Caddy process.
2. `docker compose down -v` the app stack.
3. Remove the two lines from `/etc/hosts`.
4. Restore `/etc/nsswitch.conf` from the `.backup` file made above.
5. Delete the temp Caddyfile/override directory.

## Notes

- Port conflicts happen even when a prior `ss -ltn` check said a port was free — re-check immediately before starting Caddy, and prefer high unprivileged ports (18080/18443, not 8080/8443 which are common defaults other tools grab) to sidestep `bind: address already in use` and avoid needing any sudo for port binding at all.
- Sudo on this class of machine is fingerprint-gated (see `sudo-interactive-tty-via-hub`) — both the `/etc/hosts` edit and the `nsswitch.conf` edit need a physical touch; if it's not the user's first prompt of the session it may time out waiting for a stale touch — always start a **fresh** `hub start` for each sudo command rather than reusing/retrying the same stuck process.
- A plain redirect to an "unknown session" / "session not found" page when visiting a Logto-style core app's root URL directly (no active OIDC flow) is expected behavior, not a bug — don't waste time debugging that specifically for the *app* port; it only matters if the *admin console* shows the same thing after accepting its cert warning.
