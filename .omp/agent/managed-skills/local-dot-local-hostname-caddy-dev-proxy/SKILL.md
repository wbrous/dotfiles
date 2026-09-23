---
name: local-dot-local-hostname-caddy-dev-proxy
description: "Use when setting up a temporary local reverse-proxy so a browser can reach services via friendly hostnames like foo.local / foo-admin.local instead of localhost:PORT — especially for testing a multi-service app (e.g. Logto: public app + admin console) where one service's Admin/Web-Crypto UI requires a secure context, or where an app's own OIDC/backend config hardcodes an internal self-referential URL (e.g. ADMIN_ENDPOINT) that the reverse-proxied hostname must match."
---

## Problem

Temporary local reverse-proxy setup so a browser can reach services via friendly hostnames like `foo.local` / `foo-admin.local` instead of `localhost:PORT` — e.g. testing Logto's public app + admin console side by side.

## `.local` hostnames silently ignored: mDNS beats `/etc/hosts`

On systemd/Arch-style systems, `/etc/nsswitch.conf`'s `hosts:` line commonly reads:

```
hosts: mymachines mdns_minimal [NOTFOUND=return] resolve files myhostname dns
```

`mdns_minimal` runs *before* `files`, and `[NOTFOUND=return]` means: if mDNS says "not found," resolution **stops immediately** — `/etc/hosts` (`files`) is never even consulted for `.local` names. Symptom: you add `127.0.0.1 foo.local` to `/etc/hosts`, `getent hosts foo.local` returns nothing, and the browser can't reach it, even though the entry is definitely there.

Fix (reversible, needs sudo): reorder so `files` comes first —

```bash
sudo cp /etc/nsswitch.conf /etc/nsswitch.conf.backup
sudo sed -i 's/^hosts:.*/hosts: files mymachines resolve myhostname mdns_minimal [NOTFOUND=return] dns/' /etc/nsswitch.conf
```

Revert from the backup when done — this is a machine-wide change affecting all `.local` resolution (real mDNS devices too), so only do it for genuinely temporary testing and always restore it in cleanup.

## Browser HTTPS-auto-upgrade breaks plain-HTTP custom hostnames

Modern Firefox/Chrome silently upgrade `http://custom.local:PORT` to `https://` on their own (HTTPS-Only Mode / HSTS-adjacent heuristics). Symptom: `SSL received a record that exceeded the maximum permissible length` — the browser sent a TLS ClientHello to a plain-HTTP-only port.

Fix: don't fight it — make the reverse proxy actually serve HTTPS on every custom hostname (Caddy's `tls internal` directive generates a self-signed cert from Caddy's local CA, no ACME/public DNS needed):

```caddyfile
{
	auto_https disable_redirects
}

https://foo.local:18080 {
	tls internal
	reverse_proxy 127.0.0.1:3001
}
```

`auto_https disable_redirects` is needed because Caddy's default behavior for any `https://` block is to also bind port 80 for an HTTP→HTTPS redirect — which fails with `permission denied` on a non-privileged port <1024, or just isn't wanted when using high ports anyway.

Browser will show one self-signed-cert warning per hostname on first visit — click through/accept once per session; this is expected for local test infra you don't own a public cert for.

Bind Caddy to unprivileged high ports (e.g. `18080`, `18443`) to avoid needing root/`setcap` for port 80/443, especially useful when sudo is fingerprint-gated and may be unreliable in the current context (see `sudo-interactive-tty-via-hub`).

## App's own internal self-calls need the fake hostname to resolve *inside* Docker too

If the proxied app makes outbound HTTP calls back to its own public URL (e.g. Logto's `ENDPOINT` — see `axum-sqlx-scaffold-gotchas`/Logto-specific skills for why), and that app runs inside a Docker container, the container's own DNS won't know about your host's `/etc/hosts` entry. Add `extra_hosts` via a small compose override (don't touch the real `compose.yml`, use `-f compose.yml -f override.yml`):

```yaml
services:
  app:
    extra_hosts:
      - "foo.local:host-gateway"
```

`host-gateway` is Docker's built-in magic value resolving to the host's own IP from inside the container's bridge network — works on Linux too (Docker 20.10+), not just Docker Desktop.

## Reverse-proxying a service whose backend hard-codes a self-referential URL (e.g. Logto's `ADMIN_ENDPOINT`) can be architecturally impossible

Some apps compute security-sensitive values (OIDC `redirect_uri`, CSRF origin checks, etc.) from `window.location.origin` **client-side**, then validate them server-side against a hardcoded config value (e.g. Logto's Admin Console always builds `redirect_uri = window.location.origin + '/console/callback'`, and the OIDC provider only accepts it if it matches `ADMIN_ENDPOINT` exactly).

If that hardcoded value (`ADMIN_ENDPOINT=http://localhost:3002`) *must* stay literal `localhost` for other reasons (e.g. avoiding `ECONNREFUSED` on the app's own backend-to-backend calls — see the Logto-specific `axum-sqlx-scaffold-gotchas`-adjacent decisions doc), then **no reverse-proxy trick can make a different hostname work for that specific sub-app** — the browser's origin and the hardcoded config value must match, full stop. Setting `header_up Host` / `X-Forwarded-Host` in the reverse proxy config changes what the *backend* sees, but not what the *browser's own JS* computes as its origin, so it doesn't help here.

Diagnose fast: hit the auth/callback endpoint directly with curl using both redirect_uri variants and compare:

```bash
# fails: 400 invalid_redirect_uri (custom hostname doesn't match the hardcoded config value)
curl -s ".../oidc/auth?redirect_uri=https%3A%2F%2Ffoo-admin.local%3A18443%2Fcallback&..." -o /dev/null -w "%{http_code}\n"

# succeeds: 303 (redirects into sign-in)
curl -s ".../oidc/auth?redirect_uri=http%3A%2F%2Flocalhost%3A3002%2Fcallback&..." -o /dev/null -w "%{http_code}\n"
```

If confirmed, don't keep patching the proxy — just tell the user to use the literal hardcoded hostname/port for that specific sub-app (`http://localhost:3002` in Logto's case) while other services in the same stack (which don't have this self-referential constraint) can still use friendly custom hostnames through the proxy normally. This usually mirrors the app's own production design intentionally (e.g. Logto's admin console is *designed* to only ever be reached via its own literal `ADMIN_ENDPOINT`, typically over an SSH tunnel, never a public-facing custom domain).
