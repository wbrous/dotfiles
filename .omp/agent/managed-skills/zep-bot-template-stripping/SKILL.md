---
name: zep-bot-template-stripping
description: "Use when asked to strip template/demo/boilerplate content from a \"zep-bot\"-style Discord bot scaffold (discord.js + Bun + Prisma + pino, with a commandHandler that auto-loads src/commands/category/name.ts and src/events/event/*.ts) while keeping all real framework functionality intact."
---

## Where the template cruft lives in this scaffold

The zep-bot boilerplate (discord.js + Bun + Prisma + pino, filesystem-driven
command/event loader, `cv2` TSX Components-V2 DSL, customId-based interaction
router, stateless `Paginator`, presence "status rotation") ships with
demo/example filler mixed into otherwise-real framework code. When asked to
"remove the template stuff, keep all functionality," strip exactly these and
nothing else:

- `src/commands/demo/` — kitchen-sink demo commands (e.g. `toolkit.ts`,
  `showcase.tsx`) that exercise buttons/modals/selects/pagination/autocomplete
  and the `cv2` DSL purely for demonstration. Delete the whole folder.
- `src/services/exampleService.ts` (+ its `.test.ts`) — fake per-guild counter
  service, doc comment literally says "Service template — copy this file".
- `src/events/ready/0Xexample*.ts` (e.g. `02exampleCron.ts`) — cron job whose
  only job is to drive `exampleService`.
- `src/utils/lifecycle.ts` (`waitForCommandRegistration`) — check first
  whether anything besides the example cron imports it; in this scaffold it
  doesn't, so it goes too.
- `ExampleCounter` model in `prisma/schema.prisma`, doc comment says
  "Template model — demonstrates this repo's conventions". Remove the model.
- The migration that created that table: if it's still the *initial*
  (never-deployed) migration, just delete the migration directory outright
  rather than hand-editing history or adding a down-migration — there's no
  production data to preserve yet.

## What is NOT template cruft (keep these — they're real framework, not demo)

- `cv2/` (elements.ts, jsx-runtime.ts, index.ts, tests) — genuine TSX
  Components-V2 DSL library, only its demo *consumer* (`showcase.tsx`) is
  template.
- Status rotation (`lib/statusRotationConfig.ts`, `statusRotationMetrics.ts`,
  `services/statusRotationService.ts`, `events/ready/00statusRotation.ts`) —
  this is a real, generic bot-presence feature, not a demo, even though it's
  config-driven. Its own `.test.ts` files stay.
- `commands/info/ping.ts`, `commands/info/help.ts`, the command/event
  handlers, `ExtendedClient`, `Paginator`, `customId` build/parse utils,
  `lib/env.ts`, `lib/logger.ts`, `lib/prisma.ts` — all real infra, keep as-is.

## Verification after stripping

1. `grep` for `lifecycle|cv2|statusRotation|exampleService|ExampleCounter`
   across `src/` to confirm nothing still imports a deleted file.
2. `bun install && bunx prisma generate` — schema with the template model
   removed should generate cleanly with zero models remaining (that's fine,
   not an error).
3. `bunx tsc --noEmit` — must be clean.
4. `bun test` — full suite must still pass; template removal should not drop
   any test count beyond the deleted example-service tests.
