---
name: docker-compose-single-edge-caddy-reverse-proxy
description: "Use when consolidating a docker-compose stack's exposed services behind one edge Caddy reverse proxy, especially when an included/vendored compose file (e.g. via include:) already publishes its own host ports that must be disabled without editing the vendored file."
---

## Problem

A docker-compose stack has multiple services each publishing their own
host ports directly (backend API, an included/vendored auth service like
Logto, static frontend SPAs). The goal: put a single edge Caddy container
in front of everything, so it's the only container binding host ports,
while backend/auth services become internal-network-only.

## Removing a vendored/included service's own `ports:` without editing it

If a service comes from `include:` (e.g. `apps/identity/compose.yml`)
and hardcodes its own `ports:` list, you cannot just re-declare
`ports: []` in the root file — Compose's default merge behavior for list
keys like `ports`/`volumes`/`environment` is a **union**, not a replace,
so `[]` merged with the existing list leaves the existing list unchanged.

Use the Compose Spec's `!override` YAML merge tag instead, from the root
file:

```yaml
services:
  app:  # matches the included file's service name
    ports: !override []
```

Verify with `docker compose config` before building — the `ports:` key
should disappear entirely from the resolved `app` service. This is a
supported, non-invasive way to change a merged/included service without
touching the vendored file.

## Reverse-proxying an OIDC provider (e.g. Logto) through Caddy

- Caddy's `reverse_proxy` passes the client's original `Host` header
  through unmodified by default (unlike nginx, which requires explicit
  `proxy_set_header`). This matters because Logto's `ENDPOINT`/
  `ADMIN_ENDPOINT` env vars are baked-in absolute URLs
  (`http://localhost:3001`) that must match what the browser sees — as
  long as Caddy publishes the *same* host:port that used to be published
  directly (just now via a proxy hop instead), nothing else needs to
  change.
- Check whether the auth service's compose file already sets something
  like `TRUST_PROXY_HEADER: "1"` — if so, it was already designed to sit
  behind a reverse proxy, which is a strong signal this refactor is safe
  and expected, not a hack.

## Consolidating multiple per-app Caddy containers into one

If you previously gave each static frontend its own
Dockerfile+Caddyfile+caddy container (one Caddy per app), replace them
with a single edge Caddy image that:
- Has one multi-stage Dockerfile building all the static frontends (reuse
  each app's existing build stages) and copying each `dist/` to a
  distinct path (`/srv/app-a`, `/srv/app-b`, ...).
- Has one Caddyfile with one `:PORT { }` block per service: `reverse_proxy`
  blocks for backend services, `root * /srv/app-x` + `try_files {path}
  /index.html` + `file_server` blocks for each static SPA (SPA fallback
  for client-side routing).
- Publishes every port (`3000-3004` etc.) from that single container in
  compose; every proxied service loses its own `ports:` entry.

## Verification checklist

- `docker compose config --quiet` after edits (catches YAML/merge
  mistakes before building).
- `docker port <caddy-container>` should list every port; every other
  service's `docker port` should be empty.
- `curl` each port for the expected status code (404 on an unmatched
  backend route, 302 on an OIDC/console redirect, 200 + SPA-fallback 200
  on a deep client-side route for each static app).
- Do a real end-to-end auth flow through the proxy (not just curl) — a
  cached SSO session silently refreshing a token, or a fresh sign-in,
  proves the Host-header pass-through actually works for the OIDC
  provider, which curl alone won't catch.

## Gotcha: orphaned containers holding the target ports

After swapping out old per-app services for the new consolidated one,
`docker compose up -d` may fail with "port is already allocated" because
the old containers are still running under their old service names
(now-orphaned). Fix: `docker rm -f <old-container-names>` (or `docker
compose down <old-service-name>` before removing the service definition),
then `docker compose up -d --remove-orphans`.

Also: after editing `ports:` on an existing service, `docker compose up
-d` may not recreate a container whose only change was the ports list if
it was already created moments earlier under stale config — force it with
`docker compose up -d --force-recreate <service>` and confirm via `docker
port` that the new mapping actually took effect.
