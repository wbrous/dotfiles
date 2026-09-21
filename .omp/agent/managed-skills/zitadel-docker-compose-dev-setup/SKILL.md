---
name: zitadel-docker-compose-dev-setup
description: "Use when standing up a self-hosted Zitadel identity provider via Docker Compose for local dev (e.g. an apps/accounts folder in a monorepo) — covers the v4 Login V2 trap that otherwise forces a Traefik/nginx reverse proxy plus a separate zitadel-login container, the masterkey generation command that silently falls short of 32 chars, and required password-complexity/first-instance env vars."
---

## Zitadel v4 Docker Compose dev setup — key gotchas

Two-service stack (Postgres + Zitadel), no reverse proxy, reachable directly on `localhost:8080`.

### 1. Login V2 trap (the critical one)
Zitadel v4's default first-instance setup requires "Login V2" — a separate `zitadel-login`
Next.js container behind a path-routing reverse proxy (Traefik/nginx/Caddy), because the core
API redirects interactive sign-in to `/ui/v2/login` which only that container serves.

Fix: set on the `zitadel` service, **before first `docker compose up`** (one-time, first-instance
only setting — cannot be changed later via env var, only via Console/Admin API):

```yaml
ZITADEL_DEFAULTINSTANCE_FEATURES_LOGINV2_REQUIRED: "false"
```

This keeps the legacy login UI bundled in the main binary, served at `/ui/login` and
`/ui/console` on the same port 8080. Verify with `curl -sf http://localhost:8080/ui/console`
→ HTTP 200 with `<title>ZITADEL • Management Console</title>`.

### 2. Masterkey generation command must actually yield 32 chars
`ZITADEL_MASTERKEY` must be exactly 32 characters (used for DB-level encryption at rest).

BROKEN (yields only ~24-29 chars after stripping symbols):
```sh
openssl rand -base64 24 | tr -dc 'A-Za-z0-9' | head -c 32
```

CORRECT (larger source so filtering still leaves 32+):
```sh
openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | head -c 32; echo
```
Always verify length (`echo -n "$MK" | wc -c`) before use — silently truncating short breaks
first-instance setup with a cryptic error.

### 3. Required config
- `command: start-from-init --masterkey "${ZITADEL_MASTERKEY}" --tlsMode disabled`
- `ZITADEL_EXTERNALDOMAIN: localhost`, `ZITADEL_EXTERNALPORT: 8080`, `ZITADEL_EXTERNALSECURE: "false"`, `ZITADEL_TLS_ENABLED: "false"`
- Postgres 14-18 supported; `postgres:16-alpine` works fine.
- `ZITADEL_FIRSTINSTANCE_ORG_HUMAN_PASSWORD` must satisfy default complexity policy: 8+ chars,
  upper, lower, digit, symbol — a non-compliant value fails first-instance setup at container
  startup (check `docker compose logs zitadel`).
- Healthcheck: `["CMD", "/app/zitadel", "ready"]`, give it `start_period: 20s` — first boot
  (schema migration + first-instance setup) takes ~20-40s even though the ready check itself
  is fast once initialized.
- `depends_on: postgres: condition: service_healthy` — Zitadel will crash-loop if it starts
  before Postgres accepts connections.

### 4. Verification sequence
```sh
docker compose up -d
docker compose ps   # both services -> healthy within ~60s
curl -sf http://localhost:8080/ui/console   # HTTP 200
```
If login page never comes up despite `LOGINV2_REQUIRED=false`, only then fall back to adding
the `zitadel-login` container + reverse proxy — don't add it preemptively.
