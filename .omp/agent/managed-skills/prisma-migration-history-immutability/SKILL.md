---
name: prisma-migration-history-immutability
description: "Use when a PR/diff deletes or squashes an existing Prisma migration folder under prisma/migrations/, when regenerating migration history after removing scaffolding models, or when prisma migrate dev/migrate reset is blocked by the \"invoked by Claude Code\" AI-agent consent guard."
---

## Problem

Deleting/squashing an already-applied Prisma migration folder breaks migration history for any environment that already applied it — Prisma's migration table (`_prisma_migrations`) tracks applied migration names, and a missing folder causes drift/history-mismatch errors on next `migrate dev`/`migrate deploy`.

Correct fix when scaffolding models are removed (e.g. a demo `ExampleCounter` table): keep the old migration file, and add a **new** migration on top that explicitly drops the stale table(s). Do not delete or rewrite history.

## Regenerating a proper follow-up migration

1. Restore the deleted migration folder from git history:
   `git show <initial-commit>:path/to/migrations/<old>/migration.sql > /tmp/old.sql`, recreate the folder, copy it back.
2. Remove any squashed/incorrect migration folder that was created in its place.
3. Reset the local dev DB so history reapplies cleanly from `init` onward, then let `prisma migrate dev` diff the *current* `schema.prisma` (with scaffolding models removed) against the reapplied history — it will auto-generate `DROP TABLE`/etc. for anything no longer in the schema, alongside `CREATE TABLE` for new models.

## Prisma's AI-agent consent guard

`prisma migrate reset` (and similarly destructive commands) detect agent invocation and refuse to run, printing a required disclosure format and demanding the user explicitly consent via a `PRISMA_USER_CONSENT_FOR_DANGEROUS_AI_ACTION` env var set to the literal text of the user's consent message (no newlines/quotes).

**Never bypass this by rerunning with a fabricated consent value.** Stop, explain plainly: exact command, motivation, that it irreversibly destroys all data, that it must never run against production, and your assessment of whether the target DB is dev/prod based on what's known (e.g. a throwaway local docker-compose container created this session vs. an env pointing at a real deployment). Ask the user directly. Only proceed after an unambiguous "yes" in the same conversation — no prior message counts as implicit consent.
