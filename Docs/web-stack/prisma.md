# Prisma

Covers Prisma migration workflows: scratch-database migration generation when the shared dev DB has drifted, and migration-history immutability.

## Generating a migration against a scratch DB (shared dev DB drifted)

**Symptom.** `bunx prisma migrate dev --name X` in `apps/backend` prints "The following migration(s) are applied to the database but missing from the local migrations directory ... We need to reset the public schema". The shared dev DB was migrated from another branch — never accept the reset. Also: the root compose `backend-postgres` may publish no host port, so `.env`'s `localhost:5433` doesn't work.

**Procedure:**

1. `docker compose up -d backend-postgres` (repo root).
2. Get the container IP: `docker inspect <project>-backend-postgres-1 --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'`.
3. Load the root `.env` for `BACKEND_POSTGRES_USER/PASSWORD`, then create a scratch DB: `docker exec <container> psql -U "$BACKEND_POSTGRES_USER" -d postgres -c "CREATE DATABASE optic_scratch"`.
4. `DATABASE_URL="postgres://$USER:$PASS@<container-ip>:5432/optic_scratch" bunx prisma migrate dev --name <name>` from `apps/backend`. It replays all local migrations into the empty DB and writes only the new migration directory.
5. Read the generated `migration.sql` (check for unexpected `DROP COLUMN`).
6. When done, `DROP DATABASE optic_scratch` and kill any backend started against it.

**Smoke-testing the backend against the scratch DB:** the app's `.env` may lack values env validation requires (e.g. `LOGTO_JWKS_URI`/`LOGTO_ISSUER`, `OPENAI_API_KEY`, API resource, `FIELD_ENCRYPTION_KEY` (64 hex), `PORT`). Export placeholders (`http://localhost:3001/oidc/jwks`, `dummy`, etc.). For parent routes, stub the auth `verifyAccessToken` with `bun:test` `mock.module` in a throwaway script and seed rows with psql. Run the server as a named `bash` service: a background `( ... &)` subshell dies with the call.

_Migrated from: prisma-migrate-dev-scratch-database-compose-postgres_

## Migration-history immutability

**Symptom.** A PR/diff deletes or squashes an existing Prisma migration folder under `prisma/migrations/`, or regenerates history after removing scaffolding models.

**Cause.** Deleting/squashing an already-applied migration breaks history for any environment that applied it — Prisma's `_prisma_migrations` table tracks applied migration names, and a missing folder causes drift/history-mismatch errors on next `migrate dev`/`migrate deploy`. Correct fix when scaffolding models are removed (e.g. a demo `ExampleCounter` table): keep the old migration file, and add a **new** migration on top that explicitly drops the stale table(s). Never delete or rewrite history.

**Regenerating a proper follow-up migration:**

1. Restore the deleted migration folder from git history: `git show <initial-commit>:path/to/migrations/<old>/migration.sql > /tmp/old.sql`, recreate the folder, copy it back.
2. Remove any squashed/incorrect migration folder created in its place.
3. Reset the local dev DB so history reapplies cleanly from `init` onward, then let `prisma migrate dev` diff the *current* `schema.prisma` (scaffolding models removed) against the reapplied history — it auto-generates `DROP TABLE`/etc. for anything no longer in the schema, alongside `CREATE TABLE` for new models.

**Prisma's AI-agent consent guard.** `prisma migrate reset` (and similarly destructive commands) detect agent invocation and refuse to run, printing a required disclosure format and demanding the user explicitly consent via a `PRISMA_USER_CONSENT_FOR_DANGEROUS_AI_ACTION` env var set to the literal text of the user's consent message (no newlines/quotes). **Never bypass this by rerunning with a fabricated consent value.** Stop, explain plainly: exact command, motivation, that it irreversibly destroys all data, that it must never run against production, and your assessment of whether the target DB is dev/prod based on what's known (e.g. a throwaway local docker-compose container created this session vs. an env pointing at a real deployment). Ask the user directly. Only proceed after an unambiguous "yes" in the same conversation — no prior message counts as implicit consent.

_Migrated from: prisma-migration-history-immutability_
