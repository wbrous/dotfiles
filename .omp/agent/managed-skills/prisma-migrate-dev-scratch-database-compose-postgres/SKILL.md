---
name: prisma-migrate-dev-scratch-database-compose-postgres
description: prisma migrate dev asks to reset schema (migrations applied but missing locally) or compose Postgres has no published port; generate migration against a scratch DB.
---

## When
`bunx prisma migrate dev --name X` in optic-fyi `apps/backend` prints "The following migration(s) are applied to the database but missing from the local migrations directory ... We need to reset the public schema". The shared dev DB was migrated from another branch. Never accept the reset. Also: the root compose `backend-postgres` publishes no host port, so `.env`'s `localhost:5433` does not work.

## Procedure
1. `docker compose up -d backend-postgres` (repo root).
2. Get the container IP: `docker inspect optic-fyi-backend-postgres-1 --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'`.
3. Load the root `.env` for `BACKEND_POSTGRES_USER/PASSWORD`, then create a scratch DB:
   `docker exec optic-fyi-backend-postgres-1 psql -U "$BACKEND_POSTGRES_USER" -d postgres -c "CREATE DATABASE optic_scratch"`.
4. `DATABASE_URL="postgres://$USER:$PASS@<container-ip>:5432/optic_scratch" bunx prisma migrate dev --name <name>` from `apps/backend`. It replays all local migrations into the empty DB and writes only the new migration directory.
5. Read the generated `migration.sql` (check for unexpected DROP COLUMN).
6. When done, `DROP DATABASE optic_scratch` and kill any backend started against it.

## Smoke-testing the backend against the scratch DB
`apps/backend/.env` lacks `LOGTO_JWKS_URI`/`LOGTO_ISSUER`; env validation fails at boot. Export placeholders (`http://localhost:3001/oidc/jwks`, `http://localhost:3001/oidc`), plus `OPENAI_API_KEY=dummy`, `LOGTO_API_RESOURCE`, `FIELD_ENCRYPTION_KEY` (64 hex), and `PORT=3055`. Device routes work without Logto; for parent routes, stub `auth/jwt` `verifyAccessToken` with `bun:test` `mock.module` in a throwaway script and seed Parent/Child/Device rows with psql. Run the server as a named `bash` service: a background `( ... &)` subshell dies with the call.
