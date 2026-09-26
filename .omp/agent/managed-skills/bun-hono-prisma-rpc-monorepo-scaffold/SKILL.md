---
name: bun-hono-prisma-rpc-monorepo-scaffold
description: "Scaffolding a Bun+TypeScript+Prisma backend with a companion typed API-client package sharing types via Hono RPC; use for new apps/backend + packages/api-client style monorepo setups, not existing backends."
---

## Pattern: Bun + Hono + Prisma backend, paired with a typed client package

When asked for a "backend boilerplate" plus a "package other apps can use to call the API",
the highest-leverage combo is **Hono + Hono RPC client (`hc`)**, not a hand-written
fetch wrapper or OpenAPI codegen. Hono lets you export the mounted route tree as a
TypeScript type (`AppType = typeof app`), and `hc<AppType>(baseUrl)` gives a fully
typed client with zero duplicated request/response types. Adding a backend route
makes it available on the client automatically after a type-only rebuild.

### Repo layout
```
package.json                 # root: "workspaces": ["apps/*", "packages/*"]
tsconfig.base.json           # shared strict compiler options, extended by each package
apps/backend/
  prisma/schema.prisma       # SQLite for zero-config dev; swap provider+DATABASE_URL for Postgres/etc.
  src/env.ts                 # zod-validated env vars, throws at import time if invalid
  src/db.ts                  # PrismaClient singleton (globalThis cache to survive --watch reload)
  src/routes/*.ts             # one Hono sub-app per resource, zValidator on every mutating input
  src/app.ts                 # mounts routes + onError handler; exports `type AppType = typeof app`
  src/index.ts               # `export default { port, fetch: app.fetch }` — Bun.serve entry
packages/api-client/
  src/client.ts               # createApiClient() wraps hc<AppType>
  src/index.ts                # barrel export
  tsup.config.ts              # dts:true, format esm — builds dist/{index.js,index.d.ts}
```

### Key gotchas hit while building this
1. **`tsconfig` `types` field**: use `"types": ["bun"]`, NOT `"bun-types"`. Bun installs
   `@types/bun` which symlinks to `node_modules/@types/bun`; TS's `types` array resolves
   against `@types/<name>`, so the entry must be `"bun"`. Using `"bun-types"` throws
   `TS2688: Cannot find type definition file for 'bun-types'` even though the package
   exists in the store.
2. **`hc`'s return type isn't nameable**: `hono/client` only exports `hc` and some
   narrow utility types (`InferResponseType`, etc.) — the actual `Client<T, Prefix>`
   intersection type lives in an internal `./types` module not in the package's public
   `exports` map. `export type ApiClient = ReturnType<typeof createApiClient>` is the
   correct/only option here (matches Hono's own RPC docs pattern) — document this as an
   intentional exception if a "no ReturnType<typeof fn>" lint rule is in play.
3. **Backend as a client devDependency**: the api-client package only needs `AppType`
   at *type* level. Put `"@optic-fyi/backend": "workspace:*"` under `devDependencies`,
   not `dependencies` — the client's runtime bundle never touches backend code.
   Give the backend package.json an `exports` map like:
   ```json
   "exports": { "./app-type": { "types": "./src/app.ts" } }
   ```
   and import with `import type { AppType } from "@optic-fyi/backend/app-type"`.
4. **Prisma `DATABASE_URL="file:./dev.db"` is relative to `schema.prisma`'s directory**,
   i.e. `prisma/dev.db`, not the package root. Don't go hunting for `dev.db` at the
   package root when cleaning up — it's inside `prisma/`.
5. **Verification loop**: run `bun run prisma:generate && bun run prisma:migrate`,
   start the backend with `bun run src/index.ts` in the background, curl the routes
   directly (health, create, list, validation-failure, 404), then separately `bun run
   build` the api-client package and run a throwaway script importing the *built*
   `dist/index.js` against the live server to prove the RPC client works end-to-end,
   not just that it typechecks.
6. Keep the initial Prisma migration directory committed (`prisma/migrations/`); only
   `.db` files themselves are gitignored/ephemeral.
