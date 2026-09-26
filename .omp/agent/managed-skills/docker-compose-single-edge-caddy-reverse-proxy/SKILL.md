---
name: docker-compose-single-edge-caddy-reverse-proxy
description: "Use when converting a docker-compose stack to ROOT_DOMAIN-driven subdomain routing through one edge Caddy instance; also covers Logto's ADMIN_ENDPOINT/ENDPOINT subdomain requirement."
---

## Single edge Caddy, ROOT_DOMAIN-driven subdomain routing

Pattern: one Caddy container is the *only* thing publishing host ports
(`:80`/`:443`); every other service (`backend`, `app`/Logto, static SPA
builds) is reachable only on the internal Docker network. `caddy/Caddyfile`
uses Caddy's `{$ROOT_DOMAIN}` env-var substitution per site block instead of
hardcoded domains/ports, so changing one `ROOT_DOMAIN` var in `.env` moves
the whole stack.

- Bind-mount `caddy/Caddyfile` (don't bake it into the image) so pure
  routing edits take effect via `docker compose exec caddy caddy reload
  --config /etc/caddy/Caddyfile` — no rebuild, no downtime. Only rebuild
  when adding a new *static* site (new Dockerfile build stage) or changing
  Vite build-time `ARG`s baked into a dashboard bundle.
- `*.localhost` (including multi-level, e.g. `admin.accounts.localhost`)
  resolves to loopback automatically per RFC 6761 on modern OSes/browsers —
  confirmed via `getent hosts` — no `/etc/hosts` editing needed for local
  dev. Caddy detects non-public hostnames and issues certs from its own
  internal CA instead of attempting ACME.
- Persist `caddy-data`/`caddy-config` as named volumes so certs survive
  restarts.
- For browser automation against these self-signed local domains: launch a
  system Chromium binary directly with
  `app: { path: "/usr/bin/chromium", args: ["--ignore-certificate-errors", "--allow-insecure-localhost"] }`
  — the default managed browser's `ignore_https_errors` tab option is not
  sufficient for `net::ERR_CERT_AUTHORITY_INVALID`. If `browser.open` times
  out after switching binaries, `pkill -f chromium` first (stale profile
  lock from a previous launch) and retry.

## Logto ENDPOINT/ADMIN_ENDPOINT: must be separate origins, never a shared path

Logto's Admin Console **cannot** be routed as a path under the same origin
as `ENDPOINT` (e.g. `accounts.example.com/admin`). Verified live: Caddy can
correctly proxy `accounts.$ROOT_DOMAIN/admin/*` to the admin console
container and the initial `index.html`/JS bundle loads fine, but the
console SPA's own client-side router has no concept of an `/admin` base
path — it renders "404 Not Found" for its own default route the moment
React Router takes over. This is a router/basename limitation baked into
the console build, not a proxy-config problem, and isn't fixable by also
setting `ADMIN_ENDPOINT` to include the path suffix.

Logto's docs also gate `ADMIN_ENDPOINT` on an *exact-origin* CORS check
(https://docs.logto.io/logto-oss/troubleshooting-oss: "If ADMIN_ENDPOINT is
specified, only requests from the origin of ADMIN_ENDPOINT will be
allowed"), reinforcing that `ENDPOINT` and `ADMIN_ENDPOINT` are designed to
be distinct origins.

Fix: use a dedicated subdomain for the admin console, e.g.
`admin.accounts.$ROOT_DOMAIN` (nested under the auth subdomain rather than
a bare unrelated `console.$ROOT_DOMAIN`, if you want to avoid introducing
an unrelated top-level name) — one more Caddy site block
(`reverse_proxy app:3002`), one more `ADMIN_ENDPOINT` env value. Confirmed
working end-to-end: correct redirect to `/sign-in?app_id=admin-console`,
correct page title "Logto Console", real sign-in form rendered, no router
404.
