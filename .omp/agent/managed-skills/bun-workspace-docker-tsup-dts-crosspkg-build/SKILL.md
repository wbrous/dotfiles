---
name: bun-workspace-docker-tsup-dts-crosspkg-build
description: "Dockerizing a Bun workspace frontend that imports a sibling package (e.g. a typed API client) built with tsup's dts: true; also covers baking Vite VITE_* build-time env into a Docker image and serving the static output via Caddy. Use when a Docker build of an app consuming a workspace package fails with Cannot find module '@scope/other-package/types-only-export' or error TS5083: Cannot read file '.../tsconfig.base.json' — not for regular runtime-only workspace deps."
---

## Problem

A Bun-workspace frontend imports a sibling package (e.g.
`@scope/api-client`) whose `dist/` is gitignored/build-only. The
package's public type surface re-exports a *type-only* import from
another workspace package (e.g. `import type { AppType } from
"@scope/backend/app-type"`), and its `tsconfig.json` does `"extends":
"../../tsconfig.base.json"`.

A naive Dockerfile that only `COPY`s each workspace member's
`package.json` (for `bun install --frozen-lockfile` layer caching) then
tries to build the consuming package's own `dist/` from source will fail
with two different errors depending on what's missing:

- `error TS5083: Cannot read file '.../tsconfig.base.json'.` — the root
  tsconfig the package's own `tsconfig.json` extends wasn't copied into
  the build stage.
- `Cannot find module '@scope/backend/app-type'` (`TS2792`, "Did you mean
  to set moduleResolution to nodenext...") — the *type-only* dependency's
  source wasn't copied in either, even though nothing at runtime needs
  it.

If the type-only source has its own build-time prerequisite (e.g. a
Prisma schema needing `prisma generate` before its generated types
exist), tsup's `dts: true` rollup step will fail resolving *those* types
too, even though the consuming build never executes any backend code.

## Fix

Build the package that needs the type-only cross-package import in a
Docker stage that has the *full source* of every package in that type's
resolution chain, plus the root tsconfig, not just its `package.json`:

```dockerfile
FROM base AS deps
COPY package.json bun.lock ./
COPY apps/backend/package.json apps/backend/package.json
COPY apps/frontend/package.json apps/frontend/package.json
COPY packages/api-client/package.json packages/api-client/package.json
RUN bun install --frozen-lockfile

# The consuming package's dts build resolves a type-only import into the
# backend's source, which transitively needs generated Prisma types.
FROM deps AS backend-types
COPY apps/backend apps/backend
RUN cd apps/backend && bunx prisma generate

FROM backend-types AS api-client
COPY tsconfig.base.json tsconfig.base.json
COPY packages/api-client packages/api-client
RUN cd packages/api-client && bun run build   # tsup, dts: true

FROM api-client AS build
COPY apps/frontend apps/frontend
RUN cd apps/frontend && bun run build          # tsc --noEmit && vite build
```

Check `git ls-files packages/*/dist` before assuming a workspace
package's build output is checked in — if it's empty and `.gitignore`
excludes `dist`, every Docker build must rebuild it from source, and this
whole chain applies.

## Related: baking Vite env into a Docker image

`VITE_*` vars are inlined into the bundle at `vite build` time, not read
at container runtime. Pass them as Docker build ARGs, not `environment:`
in compose:

```dockerfile
FROM api-client AS build
ARG VITE_BACKEND_URL
ENV VITE_BACKEND_URL=${VITE_BACKEND_URL}
COPY apps/frontend apps/frontend
RUN cd apps/frontend && bun run build
```

```yaml
services:
  frontend:
    build:
      context: .
      dockerfile: apps/frontend/Dockerfile
      args:
        VITE_BACKEND_URL: "${VITE_BACKEND_URL:-http://localhost:3000}"
```

Changing a `VITE_*` value later requires a rebuild (`docker compose build
frontend`), not just a restart — the value is compiled into the JS
bundle, there's nothing left to read at runtime.

## Related: serving the static build with Caddy (no host install)

Final stage: `caddy:2-alpine`, copying only the built `dist/` and an
app-specific `Caddyfile` — no Bun/Node runtime ships in the production
image. SPA client-side routing needs a fallback to `index.html` so a hard
reload on a deep route (e.g. `/children/abc`) doesn't 404:

```
:80 {
	root * /srv
	encode gzip
	try_files {path} /index.html
	file_server
}
```

```dockerfile
FROM caddy:2-alpine AS runtime
COPY apps/frontend/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/apps/frontend/dist /srv
EXPOSE 80
```

Verify with `curl -o /dev/null -w '%{http_code}' http://localhost:PORT/some/deep/route` — must return `200`, not `404`.
