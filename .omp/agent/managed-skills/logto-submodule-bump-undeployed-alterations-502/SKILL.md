---
name: logto-submodule-bump-undeployed-alterations-502
description: "Logto docker app crash-loops (Restarting (0)), accounts.* 502, \"Undeployed database alterations found\" after submodule bump; plain alteration deploy says 0."
---

# Logto app crash-loop after submodule bump (502 at accounts.$ROOT_DOMAIN)

## Symptoms
- `docker compose ps app` shows `Restarting (0)`; `docker inspect` -> `oom=false exit=0`, high RestartCount.
- Caddy returns 502 (DNS/cert fine; nothing listening on app:3001).
- Logs: `pre error Found undeployed database alterations` / `Error: Undeployed database alterations found.`, preceded by `Seeding skipped`.
- `npm run cli db alteration deploy` prints `Found 0 alteration to deploy` (misleading).

## Cause
Submodule (apps/identity/logto) pinned to a Logto `master` commit containing unreleased `packages/schemas/alterations/next-*` scripts. Core's startup check (`getAvailableAlterations`) counts them as pending; `deploy` without a target filters out `next-*` (`chooseAlterationsByVersion`). The compose entrypoint only ran `db seed --swe`, which skips on an existing DB.

## Fix (one-off, on the VPS)
```bash
set -a; . apps/identity/.env; set +a
docker compose exec -T postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > ~/logto-backup-$(date +%F).sql   # backup first
docker compose stop app
docker compose run --rm --no-deps --entrypoint "" app npm run cli db alteration deploy next
docker compose up -d app
```

## Permanent fix
Entrypoint in apps/identity/compose.yml: `npm run cli db seed -- --swe && npm run cli db alteration deploy next && npm start` (idempotent; verified 2nd run = 0 alterations).

## Testing pitfall
When simulating in a throwaway Postgres, set `systems.alterationState` timestamp to just below the `next-*` scripts (e.g. the first next- timestamp - 1), NOT 1700000000, or it replays 169 old alterations and fails on FK constraints.

## Related gotcha
`git pull` on VPS: `fatal: not our ref <sha>` for submodule = parent pointer committed without pushing the submodule commit. Push the submodule first (`git push --recurse-submodules=on-demand`, or `git config push.recurseSubmodules on-demand`).
