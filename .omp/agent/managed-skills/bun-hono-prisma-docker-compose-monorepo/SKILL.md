---
name: bun-hono-prisma-docker-compose-monorepo
description: "Dockerizing a Bun+Hono+Prisma backend alongside an existing docker-compose service (e.g. Logto) via root docker-compose.yml with include; Postgres switch, workspace-root build context, port-conflict recovery."
---

## Context

Monorepo with Bun workspaces (`apps/*`, `packages/*`). One app (e.g. `apps/backend`, Hono+Prisma) needs Dockerizing and wiring into a root `docker-compose.yml` alongside another app that already ships its own `compose.yml` (e.g. `apps/identity` running Logto).

## Backend Dockerfile: build context MUST be repo root

Bun workspaces resolve `package.json`/`bun.lock` from the root. The Dockerfile lives at `apps/backend/Dockerfile` but is built with `context: .` (repo root) in compose, or `docker build -f apps/backend/Dockerfile .` manually. Document this loudly in a comment at the top of the Dockerfile — it's the #1 source of confusing "module not found" build failures otherwise.

Multi-stage pattern that works:
1. `deps` stage: copy root `package.json`+`bun.lock` + every workspace member's `package.json` (not full source), `bun install --frozen-lockfile`. This layer caches across source-only changes.
2. `build` stage (from `deps`): copy the actual app source, run `bunx prisma generate`.
3. `runtime` stage (from `base`, not `deps`/`build`): copy `node_modules` and app dir from `build`, `WORKDIR` into the app, `CMD ["sh", "-c", "bunx prisma migrate deploy && bun run src/index.ts"]` — migrations apply automatically on container start, no separate migrate step needed in CI/deploy.

Since `prisma migrate deploy` needs the Prisma CLI (a devDependency) at runtime, don't strip devDependencies from the final image unless you also install `prisma` as a separate lightweight step — simplest is to just keep the full `bun install` result.

## Root `.dockerignore` goes at repo root, not per-app

Since build context is root, `.dockerignore` must also live at root (Docker looks for it next to the context, not next to the Dockerfile, unless using per-Dockerfile BuildKit ignore files). Exclude `**/node_modules`, `**/dist`, `**/.env`, and any large unrelated app directories (e.g. a git-submodule-based app like Logto with its own huge `node_modules`/pnpm store) to keep build context transfer fast.

## Prisma SQLite → Postgres switch

1. Change `datasource db { provider = "postgresql" ... }` in `schema.prisma`.
2. Delete the old SQLite migration directory entirely — SQLite migration SQL (`DATETIME`, no `CONSTRAINT ... PRIMARY KEY` syntax) is not valid Postgres SQL and won't apply.
3. Spin up a throwaway local Postgres container (`docker run -d -e POSTGRES_USER=... -e POSTGRES_PASSWORD=... -e POSTGRES_DB=... -p <port>:5432 postgres:17-alpine`) just to run `prisma migrate dev --name init` and regenerate a proper Postgres migration file, then remove that throwaway container. This is separate from the "real" compose Postgres.
4. Update `.env`/`.env.example` `DATABASE_URL` to `postgres://user:pass@host:port/db` format.

## Combining two compose files with `include` (Compose v2.20+/CLI v5+)

To wire an existing app's `compose.yml` (with its own `.env`, its own Postgres, hardcoded host ports) into a root compose file without rewriting it:

```yaml
include:
  - path: apps/identity/compose.yml
    env_file: apps/identity/.env

services:
  backend-postgres: ...
  backend: ...
```

This keeps the included file's env resolution scoped to its own `.env` (no variable name collisions with root-level vars, e.g. both files can use `POSTGRES_USER` safely if root uses prefixed names like `BACKEND_POSTGRES_USER` for its own services). `docker compose config` validates the merge before doing a real `up`.

## Port-conflict gotcha: don't silently kill "unrelated" containers

If the included compose file (e.g. Logto) is already running **standalone** under its own project name (`cd apps/identity && docker compose up` was run previously, creating project `identity`), running the new root-level `docker compose up` creates a **second, independent set of containers** under the root project name (e.g. `optic-fyi-app-1` vs `identity-app-1`) — same image/config, different containers — which will collide on the hardcoded host ports.

Before assuming this is a bug in the compose file: check `docker ps` and `docker inspect <container> --format '{{.Config.Labels}}'` for `com.docker.compose.project` and `.Created` timestamp. A container that's been running for days under a different project name is very likely a real, in-use deployment — not test scaffolding. **Ask the user** how to proceed (stop the standalone one and let root compose own it going forward, vs. leave it alone and only manage the new services via root compose) rather than force-killing it. Note explicitly that stopping+recreating under the new project name uses a **different named volume** (`identity_x` vs `optic-fyi_x`), so data does not carry over automatically — flag this before the user picks "consolidate."

## Verification checklist

- `docker compose config` resolves cleanly (catches include/env issues before a slow build).
- `docker compose up -d --build`, then check `docker compose ps` for all services `Up`/`healthy`.
- `docker logs <backend>` shows `prisma migrate deploy` applying the migration, then the server listening.
- Curl the actual routes through the published port (health check, one write, one read) — not just that the container is "Up".
- Curl the other included service's port too (e.g. Logto `/` returns 302, not necessarily 200 — that's the expected auth-redirect behavior, don't mistake it for failure).
