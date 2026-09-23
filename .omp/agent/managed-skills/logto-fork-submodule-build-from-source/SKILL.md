---
name: logto-fork-submodule-build-from-source
description: "Use when working on optic-fyi/monorepo's apps/identity Logto stack and needing to make UI/branding changes to Logto itself, rebuild the app image, or diagnose why docker compose up --build fails after pulling submodule updates — covers the apps/identity/logto git submodule (fork of logto-io/logto, tracks its own master branch, has a root Dockerfile exposing 3001) wired into compose.yml's app service via build: { context: ./logto, dockerfile: Dockerfile } instead of the prebuilt ghcr.io/logto-io/logto image, and the DB-migration mismatch gotcha: if the fork's master has newer/different DB alterations than whatever seeded the local logto-postgres-data volume, the app container crash-loops with \"Found undeployed database alterations, you must deploy them first\" — fix for local dev (no real data yet) is docker compose down -v && docker compose up -d --wait --build to wipe and reseed fresh, since the compose entrypoint only runs db seed --swe (idempotent) not alteration deploy."
---

## Setup

`apps/identity/logto` is a git submodule pointing at `optic-fyi/logto` (a fork of `logto-io/logto`), tracking its own `master` branch — independent from the monorepo's branch.

`apps/identity/compose.yml`'s `app` service builds from it instead of pulling a prebuilt image:

```yaml
app:
  build:
    context: ./logto
    dockerfile: Dockerfile
```

The fork's root `Dockerfile` is Logto's standard multi-stage build (pnpm monorepo, `node:22-alpine`, `EXPOSE 3001`). A full build takes ~3.5 minutes (pnpm install + `pnpm -r build` across the whole monorepo).

## First-time clone

```bash
git submodule update --init apps/identity/logto
cd apps/identity
cp .env.example .env
docker compose up -d --wait --build
```

## Making UI/branding changes

1. Edit files under `apps/identity/logto/`.
2. Commit + push inside the submodule to `optic-fyi/logto`.
3. Bump the pointer in the monorepo:
   ```bash
   cd apps/identity/logto && git checkout <new-commit>
   cd ../../.. && git add apps/identity/logto && git commit
   ```
4. Rebuild: `docker compose up -d --wait --build`.

## Gotcha: DB alteration mismatch after rebuilding

If the fork's `master` has diverged (newer DB migrations) from whatever version last seeded the local `identity_logto-postgres-data` volume, the app container crash-loops:

```
pre      error Found undeployed database alterations, you must deploy them first by npm run alteration deploy command.
index    error Error: Undeployed database alterations found.
```

The compose entrypoint (`npm run cli db seed -- --swe && npm start`) only runs `db seed --swe`, which is idempotent/skips if already seeded — it does NOT run `alteration deploy`. For local dev with no real data to preserve, the fix is simply to wipe and reseed:

```bash
docker compose down -v
docker compose up -d --wait --build
```

Symptom looks like a connection failure from the outside (`smoke-test.sh` gets `curl: (56) Recv failure: Connection reset by peer`) because the container is mid-restart-loop when probed — check `docker compose logs app --tail 40` to see the actual `Undeployed database alterations` error before assuming it's a build/network issue.
