---
name: docker-compose-single-edge-caddy-reverse-proxy
description: "Use when converting a docker-compose stack to ROOT_DOMAIN-driven subdomain routing through one edge Caddy on 80/443; ports.yml, !override merge, *.localhost dev."
---

## Goal
User wants: one `ROOT_DOMAIN` env var, Caddy automatically routes subdomains to services over `:80`/`:443` (e.g. `accounts.domain.com` -> Logto, `api.domain.com` -> backend, `dashboard.domain.com` -> a static SPA). This supersedes an earlier port-numbered scheme (`:3000`-`:3004`) once the user asks for "real" domain routing.

## Caddyfile pattern
Use Caddy's `{$VAR}` env-var substitution per site block, NOT `:PORT` blocks:

```caddyfile
accounts.{$ROOT_DOMAIN} {
	reverse_proxy app:3001
}

api.{$ROOT_DOMAIN} {
	reverse_proxy backend:3000
}

dashboard.{$ROOT_DOMAIN} {
	root * /srv/dashboard
	encode gzip
	try_files {path} /index.html
	file_server
}
```

Caddy automatically obtains/renews HTTPS for every hostname: real ACME (Let's Encrypt) for a public domain with `:80`/`:443` reachable from the internet; its own **internal CA** (self-signed) for `localhost`/non-public hostnames — this just works offline, no ACME failure loop.

## Bind-mount the Caddyfile, don't bake it in
`COPY Caddyfile ...` in the Dockerfile only sets a sane default; also bind-mount it in compose (`./caddy/Caddyfile:/etc/caddy/Caddyfile:ro`) so routing edits take effect via `docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile` with **no rebuild, no downtime**. Only a *new static site* (new SPA build stage baked into the image) needs an actual image rebuild — document that distinction explicitly for users adding sites later.

## Local dev: use ROOT_DOMAIN=localhost, not a fake TLD
`*.localhost` resolves to `127.0.0.1`/`::1` automatically on modern OSes/browsers (RFC 6761) — confirm with `getent hosts accounts.localhost`. No `/etc/hosts` editing needed. This is the only feasible way to smoke-test domain-based Caddy routing in a sandboxed/offline environment (a fake domain like `example.test` would make Caddy retry ACME forever since it can't resolve publicly).

`curl -k` bypasses the self-signed cert warning for automated checks. For a **headless browser** managed by the eval tool, `ignore_https_errors`/`ignoreHTTPSErrors` on `browser.open` does NOT reliably bypass `net::ERR_CERT_AUTHORITY_INVALID` for the *default managed Chromium*. Workaround: launch a system Chromium binary explicitly with `app: { path: "/usr/bin/chromium", args: ["--ignore-certificate-errors"] }` — this reliably works.

## Making one env var drive everything (derive, don't duplicate)
Don't hardcode a hostname in more than one place. Derive every dependent URL from `ROOT_DOMAIN` via nested compose interpolation (confirmed working: `"${VAR:-https://accounts.${ROOT_DOMAIN}}"`), e.g.:
- Backend's `LOGTO_ISSUER` -> `https://accounts.${ROOT_DOMAIN}/oidc`
- Logto's own `ENDPOINT`/`ADMIN_ENDPOINT` -> `https://accounts.${ROOT_DOMAIN}` / `https://console.${ROOT_DOMAIN}`
- Backend's `CORS_ALLOWED_ORIGINS` -> include `https://dashboard.${ROOT_DOMAIN}`, etc.
- Dashboard build args (`VITE_LOGTO_ENDPOINT`, `VITE_BACKEND_URL`) -> same subdomain pattern

Test nested interpolation before relying on it: `ROOT_DOMAIN=x docker compose -f test.yml config` and check the resolved value.

## Overriding a vendored/included service's config without editing it
If a sub-service comes from `include: - path: vendored/compose.yml`, you can override specific keys from the root file by redeclaring the same service name:
- Scalars/maps (e.g. `environment:`) merge key-by-key — later file wins per key, other keys untouched.
- **Lists** (e.g. `ports:`) get **unioned** by default, NOT replaced — declaring `ports: []` does nothing. Use the YAML merge tag `!override` to force-replace: `ports: !override []`. Verify empirically with `docker compose -f <file> config` before trusting this, since compose merge semantics vary by key type.
- This is the correct way to make a single edge Caddy the sole host-port-binding container even when a vendored service (e.g. Logto) publishes its own ports — don't edit the vendored file.
- Bonus: check the vendored service's own env for `TRUST_PROXY_HEADER`/similar — if present, the service was already designed to sit behind a reverse proxy, which is a strong "yes, proxy this" signal.

## Cert/state persistence
Add named volumes for `/data` and `/config` in the Caddy service (e.g. `caddy-data`, `caddy-config`) so certificates and other Caddy state survive `docker compose down`/restarts — otherwise ACME re-issues certs every restart and can hit rate limits in real production.

## Verification checklist (no real DNS/public deployment needed)
1. `docker compose config --quiet` after every edit.
2. `docker compose up -d --build`; check `docker compose logs caddy` for `certificate obtained successfully ... issuer: local` per hostname.
3. `curl -sk https://<subdomain>.localhost/` for every site, including a deep SPA route (`/some/deep/path` should still 200 via `try_files ... /index.html`).
4. `docker port <caddy-container>` should list `:80`/`:443`; `docker port <other-service-container>` should list **nothing** — proves only Caddy binds host ports.
5. For OIDC-backed apps: click "Sign in" through the new domain and confirm the redirect URL's `iss` and `redirect_uri` show the new subdomains (even a `redirect_uri did not match` error from Logto is a *pass* here — it proves the whole chain wired correctly and only the one-time manual Admin Console URI registration remains, which requires real admin credentials you may not have in a fresh browser session).
