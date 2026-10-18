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

## Removed (all need secrets this fork lacks, or target upstream infra)

release.yml (DOCKERHUB_*, BOT_PAT, pushes to ghcr.io/logto-io), repository-dispatch.yml (dispatches to logto-io/cloud, BOT_PAT), changesets.yml (BOT_PAT, BOT_GPG_*), pen-tests.yml (ZAP vs upstream edge image, workflow_run on Release), master-codecov-report.yml and Codecov steps in main.yml (CODECOV_TOKEN), update-pr-metadata.yml and close-stale.yml (upstream triage), rerun.yml + integration-test's rerun-on-failure, alteration-compatibility-integration-test.yml, and main.yml's `main-alteration` job (needs `@logto/core@*` git tags; fork has none -> `git describe` "No names found").
Also dropped main-dockerize's `additional_connector_args=--cloud` build arg.

## Triage recipe

1. `gh api repos/optic-fyi/logto/actions/workflows --paginate -q '.workflows[]|[.name,.path]|@tsv'`
2. Per-workflow stats: `gh run list -R optic-fyi/logto --limit 300 --json workflowName,conclusion -q 'group_by(.workflowName)[]|...'`
3. Failure cause: `gh run view <id> --json jobs` for failed job/step names, then job logs. `--log-failed` does NOT work while the run is still in progress; use `gh api repos/optic-fyi/logto/actions/jobs/<jobId>/logs --allow-escape-sequences | sed -E 's/\x1b\[[0-9;]*[A-Za-z]//g'`.
4. Classify: "Input required: token", "Username and password required", "Parameter token or opts.auth is required" => missing secret => remove. A failure inside code we own (check/lint/test on our packages) => FIX, don't delete the workflow.
5. `gh run list --commit` needs the FULL sha; short sha errors with "run or job ID required".

## Gotchas

- Global pre-commit hook runs `git diff --staged | gitleaks stdin`; deleting upstream workflow lines containing the public integration-test `SECRET_VAULT_KEK` trips `generic-api-key`. It is a public test fixture in upstream's integration-test.yml, so `GIT_ALLOW_SECRETS=1` is legitimate for that commit -- but verify the finding first (`git diff --staged | gitleaks stdin --redact -v --no-banner`).
- Global watermarks-remover hook blocks merges touching upstream locale files with zero-width/RTL chars; `WATERMARKS_REMOVER_DISABLE=1` for those commits.
- `packages/optic-ui` is source-only (exports map -> src); its `check` script is `tsc --noEmit` and REQUIRES `packages/optic-ui/tsconfig.json` (without one tsc prints help and exits 1). Keep it.
- The upstream `experience` integration test `overrides.test.ts` asserts the primary-button computed background is the branding color (e.g. rgb(0,0,255)). Our Optic UI theming overrides it (we got rgb(223,170,86)-like values), so `run-logto (experience, *)` fails by design of our theme. Either fix the theme to honour branding colors or exclude that suite; do not just rerun.
- Integration tests are flaky upstream, which is why they had `rerun-on-failure`; we removed it, so rerun manually with `gh run rerun <id> --failed`.
