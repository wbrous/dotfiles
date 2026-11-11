# Bun Monorepos (Hono + Prisma + Workspaces)

Covers Bun workspace monorepos with Hono backends, Prisma, typed RPC clients, Docker builds, and publishable-library scaffolding.

## Bun + Hono + Prisma backend with typed RPC client

Pattern: Bun + Hono + Prisma backend (`apps/backend`) paired with a typed client package (`packages/api-client`) sharing types via Hono RPC (`hc`) — no hand-written fetch wrapper or OpenAPI codegen. Export the mounted route tree as `AppType = typeof app`; `hc<AppType>(baseUrl)` gives a fully typed client; adding a backend route makes it available on the client after a type-only rebuild.

```
package.json                 # root: "workspaces": ["apps/*", "packages/*"]
tsconfig.base.json           # shared strict compiler options, extended by each package
apps/backend/
  prisma/schema.prisma       # SQLite for zero-config dev; swap provider+DATABASE_URL for Postgres
  src/env.ts                 # zod-validated env vars, throws at import time if invalid
  src/db.ts                  # PrismaClient singleton (globalThis cache to survive --watch reload)
  src/routes/*.ts            # one Hono sub-app per resource, zValidator on every mutating input
  src/app.ts                 # mounts routes + onError handler; exports `type AppType = typeof app`
  src/index.ts               # `export default { port, fetch: app.fetch }` — Bun.serve entry
packages/api-client/
  src/client.ts              # createApiClient() wraps hc<AppType>
  src/index.ts               # barrel export
  tsup.config.ts             # dts:true, format esm — builds dist/{index.js,index.d.ts}
```

Key gotchas:

1. **`tsconfig` `types` field**: use `"types": ["bun"]`, NOT `"bun-types"`. Bun installs `@types/bun`; TS's `types` array resolves against `@types/<name>`, so the entry must be `"bun"`. `"bun-types"` throws `TS2688: Cannot find type definition file for 'bun-types'`.
2. **`hc`'s return type isn't nameable**: `hono/client` only exports `hc` and narrow utility types; the `Client<T, Prefix>` intersection lives in an internal `./types` module not in the package's public `exports` map. `export type ApiClient = ReturnType<typeof createApiClient>` is the correct/only option (matches Hono's own RPC docs pattern).
3. **Backend as a client devDependency**: the api-client only needs `AppType` at *type* level. Put `"@org/backend": "workspace:*"` under `devDependencies`, not `dependencies`. Give the backend an `exports` map like `"exports": { "./app-type": { "types": "./src/app.ts" } }` and import with `import type { AppType } from "@org/backend/app-type"`.
4. **Prisma `DATABASE_URL="file:./dev.db"` is relative to `schema.prisma`'s directory** (i.e. `prisma/dev.db`), not the package root.
5. **Verification loop**: `bun run prisma:generate && bun run prisma:migrate`, start the backend, curl routes directly (health, create, list, validation-failure, 404), then `bun run build` the api-client and run a throwaway script importing the *built* `dist/index.js` against the live server to prove RPC works end-to-end.
6. Keep the initial Prisma migration directory committed (`prisma/migrations/`); only `.db` files are gitignored/ephemeral.

_Migrated from: bun-hono-prisma-rpc-monorepo-scaffold_

## Dockerizing a Bun+Hono+Prisma backend alongside an existing compose service

Monorepo with Bun workspaces (`apps/*`, `packages/*`). One app (e.g. `apps/backend`, Hono+Prisma) needs Dockerizing and wiring into a root `docker-compose.yml` alongside an app that already ships its own `compose.yml` (e.g. `apps/identity` running Logto).

**Build context MUST be repo root.** Bun workspaces resolve `package.json`/`bun.lock` from the root. The Dockerfile lives at `apps/backend/Dockerfile` but is built with `context: .` in compose (or `docker build -f apps/backend/Dockerfile .`). Document this loudly in a comment at the top of the Dockerfile — the #1 source of confusing "module not found" build failures.

Multi-stage pattern:

1. `deps` stage: copy root `package.json`+`bun.lock` + every workspace member's `package.json` (not full source), `bun install --frozen-lockfile`. Caches across source-only changes.
2. `build` stage (from `deps`): copy the actual app source, run `bunx prisma generate`.
3. `runtime` stage (from `base`, not `deps`/`build`): copy `node_modules` and app dir from `build`, `WORKDIR` into the app, `CMD ["sh", "-c", "bunx prisma migrate deploy && bun run src/index.ts"]` — migrations apply on container start, no separate migrate step in CI/deploy.

Since `prisma migrate deploy` needs the Prisma CLI (a devDependency) at runtime, don't strip devDependencies from the final image unless you also install `prisma` separately — simplest is to keep the full `bun install` result.

**Root `.dockerignore` goes at repo root**, not per-app (Docker looks for it next to the context, not the Dockerfile, unless using per-Dockerfile BuildKit ignore files). Exclude `**/node_modules`, `**/dist`, `**/.env`, and large unrelated app dirs (e.g. a git-submodule app like Logto with its own huge `node_modules`/pnpm store).

### Prisma SQLite → Postgres switch

1. Change `datasource db { provider = "postgresql" ... }` in `schema.prisma`.
2. Delete the old SQLite migration directory entirely — SQLite migration SQL (`DATETIME`, no `CONSTRAINT ... PRIMARY KEY` syntax) is not valid Postgres SQL.
3. Spin up a throwaway local Postgres (`docker run -d -e POSTGRES_USER=... -e POSTGRES_PASSWORD=... -e POSTGRES_DB=... -p <port>:5432 postgres:17-alpine`) just to run `prisma migrate dev --name init` and regenerate a proper Postgres migration file, then remove it. Separate from the "real" compose Postgres.
4. Update `.env`/`.env.example` `DATABASE_URL` to `postgres://user:pass@host:port/db` format.

### Combining two compose files with `include` (Compose v2.20+/CLI v5+)

```yaml
include:
  - path: apps/identity/compose.yml
    env_file: apps/identity/.env
```

Keeps the included file's env resolution scoped to its own `.env` (no variable-name collisions with root-level vars; root can use prefixed names like `BACKEND_POSTGRES_USER`). `docker compose config` validates the merge before a real `up`.

### Port-conflict gotcha: don't silently kill "unrelated" containers

If the included compose file (e.g. Logto) is already running **standalone** under its own project name (`cd apps/identity && docker compose up` → project `identity`), running the root-level `docker compose up` creates a **second, independent set of containers** under the root project name — same image/config, different containers — colliding on hardcoded host ports. Before assuming a bug: check `docker ps` and `docker inspect <container> --format '{{.Config.Labels}}'` for `com.docker.compose.project` and `.Created`. A container running for days under a different project name is likely a real in-use deployment. **Ask the user** how to proceed (stop the standalone one vs. leave it), rather than force-killing. Note: stopping+recreating under the new project name uses a **different named volume** (`identity_x` vs `root_x`) — data does not carry over; flag this before they pick "consolidate."

**Verification checklist:** `docker compose config` resolves; `docker compose up -d --build`, all services `Up`/`healthy`; backend logs show `prisma migrate deploy` then server listening; curl the routes through the published port (health, one write, one read); curl the other included service's port too (e.g. Logto `/` returns 302 — that's the expected auth-redirect, not failure).

_Migrated from: bun-hono-prisma-docker-compose-monorepo_

## Dockerizing a workspace frontend that imports a sibling tsup-built package

**Symptom.** Docker build of a Bun-workspace frontend importing a sibling package (e.g. `@scope/api-client`, `dist/` gitignored/build-only) fails with `error TS5083: Cannot read file '.../tsconfig.base.json'` or `Cannot find module '@scope/backend/app-type'` (TS2792) — even though nothing at runtime needs that type-only dependency. If the type-only source itself needs `prisma generate` first, tsup's `dts: true` rollup fails resolving those types too.

**Fix.** Build the consuming package in a Docker stage with the *full source* of every package in the type-resolution chain, plus the root tsconfig — not just `package.json` files:

```dockerfile
FROM base AS deps
COPY package.json bun.lock ./
COPY apps/backend/package.json apps/backend/package.json
COPY apps/frontend/package.json apps/frontend/package.json
COPY packages/api-client/package.json packages/api-client/package.json
RUN bun install --frozen-lockfile

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

Check `git ls-files packages/*/dist` before assuming a workspace package's build output is checked in — if empty and `.gitignore` excludes `dist`, every Docker build must rebuild it from source.

**Related: baking Vite env into a Docker image.** `VITE_*` vars are inlined at `vite build` time, not read at container runtime. Pass them as Docker build ARGs, not `environment:` in compose:

```dockerfile
FROM api-client AS build
ARG VITE_BACKEND_URL
ENV VITE_BACKEND_URL=${VITE_BACKEND_URL}
COPY apps/frontend apps/frontend
RUN cd apps/frontend && bun run build
```

Changing a `VITE_*` value later requires a rebuild (`docker compose build frontend`), not just a restart.

**Related: serving the static build with Caddy (no host install).** Final stage `caddy:2-alpine`, copying only `dist/` + an app `Caddyfile`. SPA routing needs an `index.html` fallback:

```
:80 {
	root * /srv
	encode gzip
	try_files {path} /index.html
	file_server
}
```

Verify: `curl -o /dev/null -w '%{http_code}' http://localhost:PORT/some/deep/route` → `200`, not `404`.

_Migrated from: bun-workspace-docker-tsup-dts-crosspkg-build_

## `bun install` fails on a private GitHub git dependency

**Symptom.** `bun install` → `error: "git clone" for "@scope/pkg" failed`, or after removing the lockfile `GET https://api.github.com/repos/<org>/<repo>/tarball/<sha> - 404`.

**Diagnosis (verified):**

1. `package-lock.json` `resolved` is `git+ssh://git@github.com/...` → bun uses SSH; no SSH key on GitHub = `Permission denied (publickey)`.
2. Without the lockfile, bun fetches the API tarball over HTTPS **unauthenticated**. Private repo → 404. Setting `GITHUB_TOKEN` / `GH_TOKEN` / `GITHUB_API_TOKEN` / `BUN_CONFIG_GITHUB_TOKEN` from `gh auth token` did NOT help.
3. Confirm privacy: `gh repo view <org>/<repo> --json visibility,viewerPermission`; `git ls-remote https://...` works via gh credential helper.

**Working workaround (verified):** clone the dep repo locally (plain `git clone` works through gh), then point the dep at it: `bun pm pkg set 'devDependencies.@scope/pkg=file:./design'` + `bun install`. Gitignore the clone. This changes `package.json` permanently, so ask the user first.

**Unverified option (offer, say untested):** `npm install` (shells out to git, uses gh creds) after `git config --global url."https://github.com/".insteadOf ssh://git@github.com/`.

**Pitfalls:** in the affected repo, `css/vendor/` was TRACKED build output — never `rm -rf` it during cleanup experiments; `git checkout -- css/vendor` to restore. Back up `package.json` / `package-lock.json` before experiments and restore after.

_Migrated from: bun-install-private-github-git-dependency-fails_

## `bun test` jsx-dev-runtime failure is a cwd problem

**Symptom.** `bun test` fails on a `.test.tsx` file with `error: Cannot find module 'react/jsx-dev-runtime' from '.../elements.test.tsx'`. Other tests pass, looking like flakiness.

**Cause.** `bun test`'s tsconfig discovery (and thus `jsxImportSource` resolution) is **cwd-relative, not file-relative**. The repo has no root-level `tsconfig.json`/`package.json` — config lives only in `bot/tsconfig.json`, which maps `jsxImportSource` to a local runtime. Running `bun test` from the repo root can't find it, so bun falls back to default `react/jsx-dev-runtime`, which isn't installed.

**Fix.** Always run tests from inside the package dir (`cd bot && bun test`), matching the package's `"test": "bun test"` script. Verified: 5 consecutive runs → all pass; from repo root → reliably reproduces the failure.

**Takeaway:** if a `bun test` failure looks unrelated to your change (JSX/module-resolution error you didn't touch), check invocation cwd before suspecting test pollution.

_Migrated from: bun-test-jsx-dev-runtime-cwd-sensitivity_

## Publishable Bun/TypeScript library scaffold

For a new Bun/TypeScript library meant for npm publishing (not an app): `package.json` exports/types setup, dual bun-build+tsc pipeline, optional-peer externalization, GitHub-prep checklist.

**package.json:** `"type": "module"`; `"module"`, `"main"`, `"types"` → `dist/index.js` / `dist/index.d.ts`; `"exports": { ".": { "types": "./dist/index.d.ts", "import": "./dist/index.js" } }` (`types` condition FIRST); `"files": ["dist"]`; `"sideEffects": false`; `"engines": { "node": ">=18" }`; `"publishConfig": { "access": "public" }` for scoped packages; `"prepublishOnly": "bun run typecheck && bun run test && bun run build"`.

**Build:** `"build": "rm -rf dist && bun build ./src/index.ts --outdir dist --target node --format esm && tsc"` — bun bundles JS; `tsc` emits `.d.ts`. tsconfig: `strict`, `declaration: true`, `emitDeclarationOnly: true`, `rootDir: src`, `outDir: dist`. **Externalize optional peers**: `--external playwright --external @scope/get-cookie` — optional peers loaded via dynamic `import()` must NOT be bundled. Mark them `peerDependencies` + `peerDependenciesMeta: { pkg: { optional: true } }`. Keep dynamic `import()` for optional peers; use local structural interfaces instead of their types so consumers without the peer stay type-safe.

**Tests:** `bun:test` with `import { describe, expect, test } from "bun:test"`. Pure functions first; avoid mocks. `bun test` runs `test/*.test.ts` automatically. Needs `@types/bun` installed.

**CLI:** scripts like `bin/refresh-cookies.ts` run via `"refresh-cookies": "bun run bin/refresh-cookies.ts"` — NOT shipped in `files` unless a real published CLI.

**GitHub-prep checklist:** `README.md` (setup, auth, API table, notable internals — biggest gap); `LICENSE` (MIT matching `license` field); `.github/workflows/ci.yml` (`oven-sh/setup-bun@v2`, then `bun install --frozen-lockfile`, typecheck, test, build on push/PR); `.gitignore` (`node_modules/`, `dist/`, `*.tsbuildinfo`, `.env`, secrets); `package.json` `repository` + `keywords`; verify with `bun pm pack --dry-run` (confirms only README/LICENSE/package.json/dist ship); verify no secrets tracked (`git add -A -n` dry-run + `git status`); stage BEFORE committing (`git add -A` — bare `git commit` with unstaged changes fails).

**Gotchas:** `mise use -g bun@1.3.14` if the `bun` shim errors ("No version is set for shim: bun"). `bun add <pkg>` puts deps in `dependencies` — move optional ones to `peerDependencies` + `peerDependenciesMeta` manually. `bun pm pack --dry-run` is the publish-contents check (bun has no `npm pack --dry-run` equivalent).

_Migrated from: bun-publishable-library-scaffold_

## Optional peerDependency: tsc TS2307 fix via ambient declaration

**Symptom.** A publishable TS library declares an optional peerDependency (e.g. a cookie-query lib, `playwright`) loaded only via dynamic `import()`. Locally `tsc --noEmit` passes (peer installed in `node_modules`), but CI fails: `error TS2307: Cannot find module '<peer>' or its corresponding type declarations.` Cause: `tsc` resolves module specifiers at **compile time even for dynamic `import()`** and `import type`. In CI, `bun install --frozen-lockfile` never installs optional peers → unresolved specifier. Same error hits downstream consumers whose `.d.ts` references the peer.

**Fix.** Add an ambient module declaration inside `src/` (must be in the tsconfig `include`), e.g. `src/<peer>-env.d.ts`:

```ts
declare module "<peer>" {
  // Declare ONLY the surface this library actually uses.
  export interface ExportedCookie { name: string; value: unknown; domain?: string }
  export class ChromiumCookieQueryStrategy {
    constructor(browser?: string);
    queryCookies(name: string, domain: string): Promise<ExportedCookie[]>;
  }
}
```

Then `import type { ExportedCookie } from "<peer>"` resolves via the ambient decl; the runtime `import("<peer>")` stays dynamic.

**Rules:** use `import type` at top level; only reference peer types in non-exported internals (if an exported signature references the peer type, emitted `dist/*.d.ts` contains the unresolved import and consumers without the peer break — verify `grep -n "<peer>" dist/<file>.d.ts` matches only comments); externalize in the bundler (`bun build ./src/index.ts --external <peer> ...`); declare `peerDependenciesMeta.<peer>.optional = true` in `package.json`.

**Verification (the CI condition):** `tsc` passing locally with the peer installed proves nothing. Simulate fresh checkout: move the peer out of `node_modules` to `/tmp`, `bun run typecheck`, restore immediately. Must pass in BOTH states. Also re-run `bun pm pack --dry-run` and inspect packed `.d.ts` files for stray peer references.

_Migrated from: ts-optional-peer-ambient-declaration_
