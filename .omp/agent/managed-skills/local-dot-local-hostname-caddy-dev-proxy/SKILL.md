---
name: local-dot-local-hostname-caddy-dev-proxy
description: "Use when setting up a temporary local reverse-proxy so a browser can reach services via friendly hostnames like foo.local / foo-admin.local instead of localhost:PORT — especially for testing a multi-service app (e.g. Logto: public app + admin console) where one service's Admin/Web-Crypto UI requires a secure context, or where an app's own OIDC/backend config hardcodes an internal self-referential URL (e.g. ADMIN_ENDPOINT) that the reverse-proxied hostname must match."
---

## Problem

Testing a locally-run multi-service app (e.g. self-hosted Logto: public app on one port, admin console on another) via friendly hostnames instead of `localhost:PORT`, using a local Caddy reverse proxy + `/etc/hosts`. This runs into several distinct, non-obvious failures.

## Gotcha 1: `.local` TLD is often intercepted by mDNS before `/etc/hosts`

`.local` is the reserved mDNS TLD. On many systemd/Arch systems, `/etc/nsswitch.conf` has:

```
hosts: mymachines mdns_minimal [NOTFOUND=return] resolve files myhostname dns
```

`mdns_minimal` runs *before* `files`, and `[NOTFOUND=return]` means: if mDNS says "not found", stop right there — `/etc/hosts` (`files`) is never even consulted for `.local` names. Symptom: you add `127.0.0.1 foo.local` to `/etc/hosts`, but `getent hosts foo.local` returns nothing and the browser can't resolve it.

Fix (temporary, revert after testing — back up first):
```bash
sudo cp /etc/nsswitch.conf /etc/nsswitch.conf.backup
sudo sed -i 's/^hosts:.*/hosts: files mymachines resolve myhostname mdns_minimal [NOTFOUND=return] dns/' /etc/nsswitch.conf
# ... test ...
sudo mv /etc/nsswitch.conf.backup /etc/nsswitch.conf   # revert when done
```

## Gotcha 2: browsers auto-upgrade `http://` to `https://` (HTTPS-only mode)

If Caddy serves one domain over plain HTTP, the browser (Firefox HTTPS-Only Mode, Chrome's default upgrade behavior) may silently try HTTPS anyway, causing `SSL received a record that exceeded the maximum permissible length` (TLS ClientHello sent to a plain-HTTP-only port). This can also get triggered if a *different* site under the same browser session sent an HSTS header that your browser cached.

Fix: don't fight the browser — serve every temporary hostname over real (self-signed) HTTPS via Caddy's `tls internal` directive, on non-privileged high ports (no sudo needed for the ports themselves):

```caddyfile
{
	auto_https disable_redirects   # otherwise Caddy tries to bind :80 for the auto HTTP->HTTPS redirect and fails (permission denied) or conflicts
}

https://foo.local:18080 {
	tls internal
	reverse_proxy 127.0.0.1:3001
}
```
Self-signed cert means one click-through browser warning per domain — acceptable for temporary testing, don't try to get it trusted system-wide for a throwaway test.

## Gotcha 3: app-internal self-calls need the container to resolve your fake hostname too

If the backend app makes its own internal HTTP calls to its externally-configured public URL (e.g. Logto's `ENDPOINT` var is used both as the browser-facing issuer AND for the app's own OIDC-discovery self-checks), and that app runs in Docker, the container's own DNS has no idea what `foo.local` means — only your host's `/etc/hosts` does. Symptom: app fails to start / times out on startup self-checks, or its self-referencing discovery doc is wrong.

Fix: add `extra_hosts` to the specific service via a *separate temporary compose override* (don't touch the real committed `compose.yml`), pointing the fake hostname at Docker's special `host-gateway` name, and make sure Caddy binds on all interfaces (default) so the container can reach it via the bridge gateway, not just `127.0.0.1`:

```yaml
# override.yml
services:
  app:
    extra_hosts:
      - "foo.local:host-gateway"
```
```bash
docker compose -f compose.yml -f override.yml up -d --wait
```

## Gotcha 4 (the sharp one): an app that validates redirect/callback URLs against its OWN literal configured endpoint CANNOT be proxied under a different hostname — full stop

This is architectural, not a proxy misconfiguration, and no `header_up` trick fixes it. Example: Logto's Admin Console SPA always computes its OIDC `redirect_uri` client-side as `window.location.origin + /console/callback`. The Logto OIDC server only accepts that redirect_uri if it matches the literally-configured `ADMIN_ENDPOINT` value (e.g. `http://localhost:3002`) — and `ADMIN_ENDPOINT` has to stay literal `localhost` anyway, because Logto's own internal admin-token-validation self-calls break (`ECONNREFUSED`) if it's anything else. So:
- Proxying the *admin console* through `admin.foo.local` will 400 with `oidc.invalid_redirect_uri` the moment you try to actually sign in / create an account, even though the login page itself loads fine.
- You can still get the *page* to render correctly via the proxy by rewriting `Host`, `X-Forwarded-Host`, `X-Forwarded-Proto`, `X-Forwarded-Port` on that one route (Caddy's `reverse_proxy { header_up ... }`) — Logto's internal admin-vs-core routing decision reads `X-Forwarded-Host` (not raw `Host`) when `TRUST_PROXY_HEADER=1` is set, so both headers must be overridden together — but that only fixes page rendering, not the OIDC flow itself, which is bound to `window.location.origin` no matter what headers the proxy sends.

Diagnose fast: reproduce the exact `/oidc/auth?...redirect_uri=...` request with `curl -L`, once with the proxied hostname's redirect_uri (expect `400 oidc.invalid_redirect_uri`) and once with the literal endpoint's redirect_uri (expect a normal `303` into sign-in). That distinguishes "proxy header bug" from "this can never work through a different hostname."

**Correct answer:** don't try to proxy this kind of service under a friendly hostname at all — access it directly via its literal configured endpoint (`http://localhost:PORT`). This is also *why* real production deployments of such apps intentionally keep the admin surface reachable only via `localhost` + an SSH tunnel rather than any public/custom domain — the local test failure is validating that same constraint, not fighting it.

## Cleanup checklist (temporary means temporary)
1. Stop the Caddy process.
2. `rm -rf` the temp Caddyfile/override directory.
3. Remove the `/etc/hosts` lines added (`sudo sed -i '/foo\.local/d' /etc/hosts`).
4. Restore `/etc/nsswitch.conf` from the backup made in Gotcha 1, if it was changed.
5. If asked to "keep the server running as-is" while only tearing down the `.local` plumbing: do NOT recreate/restart the app container just to reset a now-stale `ENDPOINT` env var back to `localhost` — that violates "as-is". Leave it and just tell the user the OIDC issuer will report the stale hostname until they explicitly ask for that follow-up change.

Each of steps 1–4 that touches `/etc/hosts` or `/etc/nsswitch.conf` needs `sudo`; on a machine with fingerprint-gated sudo, expect to prompt the user to physically touch the sensor per command (see `sudo-interactive-tty-via-hub`).
