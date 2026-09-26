---
name: optic-fyi-api-client-and-docs-convention
description: "Use when updating @optic-fyi/api-client vs apps/backend, or adding docs/app/ subfolder docs in the optic-fyi monorepo."
---

## api-client stays in sync automatically — don't hand-port routes

`packages/api-client/src/client.ts` wraps Hono's `hc<AppType>` against
`apps/backend`'s exported `AppType` (`apps/backend/src/app.ts`). This means
the client's *code* never needs manual updates when backend routes change —
it's generic over the whole route tree by construction.

When asked to "update api-client to match backend", the actual work is:
1. Verify, don't rewrite: `cd packages/api-client && bun run typecheck && bun run build`.
   If both are clean and `dist/` size is roughly unchanged, the client already
   reflects the latest backend — there is no client code to edit.
2. The real gap is almost always the **README usage examples** going stale
   (new routes added to `apps/backend/src/routes/{parent,device}/*` aren't
   demonstrated). Read `apps/backend/src/routes/parent/index.ts` and
   `.../device/index.ts` to enumerate the current full route surface, then
   update `packages/api-client/README.md`'s usage examples to cover it.
3. Hono RPC client property access: hyphenated segments need bracket syntax,
   e.g. `api.parent["rule-intent"].$post(...)`, `deviceApi.device["enforcement-events"].$post(...)`.
   Path params use `[":paramName"]` bracket access with a `param:` field in
   the call options.

## docs/<app>/ convention

Each app under `apps/` gets a matching `docs/<app-name>/` folder (see
`docs/identity/` as the template). Standard files, one topic each:
- `setup.md` — local dev + Docker instructions, required env vars table,
  migrations, recurring jobs, "verifying the setup works" commands.
- `design.md` (or `decisions.md`) — *why*, not *what*: one `##` heading per
  design decision, referencing the specific source file it's justifying.
  Every claim must be grounded in an actual file read, not inferred.
- `future.md` (or a "Known gaps" section) — simplifications and TODOs
  actually found in code comments (grep for "Documented simplification",
  "not yet", "out of scope", "TODO") plus consumers/features that don't
  exist yet, so they aren't rediscovered from scratch next time.

Ground every design-doc claim in a real file read before writing it — don't
infer backend intent from route names alone; read the route handler bodies,
schema.prisma, env.ts, and crypto modules first.
