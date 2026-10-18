---
name: logto-fork-ci-workflow-triage
description: "Use when pruning or debugging GitHub Actions in the optic-fyi/logto fork (apps/identity/logto): deciding which inherited upstream workflows to keep, reading failures from gh, or after a fork sync reintroduces upstream workflows."
---

## Context

`apps/identity/logto` is the `optic-fyi/logto` fork. The monorepo (`optic-fyi/monorepo`) has NO workflows; all Actions live in the fork's `.github/workflows/`. Upstream merges can re-add deleted workflow files (modify/delete conflicts) -- re-delete them.

## Kept set (as of the prune)

- `optic-image.yml` -- ours; builds/pushes `ghcr.io/optic-fyi/logto:sha-<commit>` using only GITHUB_TOKEN. The deploy path. Never delete.
- `main.yml` -- generated-files, build, check, lint, test, dockerize. Self-contained, no secrets.
- `integration-test.yml` -- api/experience/console x dev-features; self-contained (uses upstream's public actions).
- `codeql-analysis.yml` -- needs no secrets.
- `commitlint.yml` -- PR-only.

All four non-PR workflows were fully green on fork commit 40c7fa410 (Main 6/6, CodeQL, Optic image, Integration Test 8/8).

## Removed (all need secrets this fork lacks, or target upstream infra)

release.yml (DOCKERHUB_*, BOT_PAT, pushes to ghcr.io/logto-io), repository-dispatch.yml (dispatches to logto-io/cloud, BOT_PAT), changesets.yml (BOT_PAT, BOT_GPG_*), pen-tests.yml (ZAP vs upstream edge image, workflow_run on Release), master-codecov-report.yml and Codecov steps in main.yml (CODECOV_TOKEN), update-pr-metadata.yml and close-stale.yml (upstream triage), rerun.yml + integration-test's rerun-on-failure, alteration-compatibility-integration-test.yml, and main.yml's `main-alteration` job (needs `@logto/core@*` git tags; fork has none -> `git describe` "No names found").
Also dropped main-dockerize's `additional_connector_args=--cloud` build arg.

## Triage recipe

1. `gh api repos/optic-fyi/logto/actions/workflows --paginate -q '.workflows[]|[.name,.path]|@tsv'`
2. Per-workflow stats: `gh run list -R optic-fyi/logto --limit 300 --json workflowName,conclusion -q 'group_by(.workflowName)[]|...'`
3. Failure cause: `gh run view <id> --json jobs` for failed job/step names, then job logs. `--log-failed` does NOT work while the run is still in progress; use `gh api repos/optic-fyi/logto/actions/jobs/<jobId>/logs --allow-escape-sequences | sed -E 's/\x1b\[[0-9;]*[A-Za-z]//g'`.
4. Classify: "Input required: token", "Username and password required", "Parameter token or opts.auth is required" => missing secret => remove. A failure inside code we own (check/lint/test on our packages) => FIX, don't delete the workflow.
5. `gh run list --commit` needs the FULL sha; short sha errors with "run or job ID required".
6. Waiting on runs: a foreground `sleep` loop gets killed by the tool timeout. Use `async: true, timeout: 0` and let the result be delivered; do not poll.

## Gotchas

- Global pre-commit hook runs `git diff --staged | gitleaks stdin`; deleting upstream workflow lines containing the public integration-test `SECRET_VAULT_KEK` trips `generic-api-key`. It is a public test fixture in upstream's integration-test.yml, so `GIT_ALLOW_SECRETS=1` is legitimate for that commit -- but verify the finding first (`git diff --staged | gitleaks stdin --redact -v --no-banner`).
- Global watermarks-remover hook blocks merges touching upstream locale files with zero-width/RTL chars; `WATERMARKS_REMOVER_DISABLE=1` for those commits.
- `packages/optic-ui` is source-only and a byte-for-byte vendored copy of the monorepo's `packages/ui` subset (`scripts/sync-optic-ui.ts`; `--check` verifies, never edit the fork copy). Its `check` script is `tsc --noEmit` and REQUIRES `packages/optic-ui/tsconfig.json` (without one tsc prints help and exits 1). Keep it.
- Tenant branding vs Optic theme (fixed in 40c7fa410): the Optic theming commit had deleted `use-color-theme.ts` from both apps, so tenant colours were ignored and `overrides.test.ts` (6 tests) failed on `button[name="submit"]` background. Fix: `experience/src/shared/utils/brand-color.ts` (`getBrandCssVariables`, pure + tested) maps the tenant colour onto the kit's `--primary`, `--primary-deep`, `--primary-foreground` and `--color-brand-*`; hooks in both AppBoundary files apply it on `document.body`. Optic stays default because Logto seeds every tenant with `#6139F6` (+ derived dark `#8768F8`): those values, or unparseable colours, produce NO override. `account` imports it via `@experience/shared/utils/brand-color`.
- Known weakness, deliberately not changed: `--primary-deep` (the button's ledge) is an RGB x0.8 shade, so branded buttons have a weaker "raised" ledge than Optic honey. The kit's own fill->deep pairs follow an HSL rule (hue held, lightness -14..-19, saturation varies by hue); a single global constant fits honey poorly (~30 RGB off), so a better derivation needs per-hue handling. Only do this if asked.
- When measuring a button's computed colour in a browser, wait ~400ms: `.button` has `transition: background-color 0.1s`, and an immediate read returns the mid-transition (old) colour.
- Integration tests are flaky upstream, which is why they had `rerun-on-failure`; we removed it, so rerun manually with `gh run rerun <id> --failed`.
