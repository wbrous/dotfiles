---
name: logto-fork-sync-upstream-merge
description: "Sync optic-fyi/logto fork (apps/identity/logto) with logto-io/logto upstream without losing our commits; pnpm-lock conflicts, watermarks hook block, frozen-lockfile failure."
---

# Sync Logto fork with upstream

Fork lives at `apps/identity/logto` (submodule, origin `optic-fyi/logto`, branch `master`). Past syncs were MERGE commits ("Merge branch 'logto-io:master'"), so keep that style: do NOT rebase (rewrites our signed commits).

## Steps
1. `cd apps/identity/logto`; check `git status` clean, `git remote -v`. The `upstream` remote may be missing: `git remote add upstream https://github.com/logto-io/logto.git && git fetch upstream --no-tags`.
2. Survey: `git rev-list --left-right --count master...upstream/master`, `git log upstream/master..master`. Save `git rev-parse HEAD` as restore point.
3. `git merge --no-ff --no-edit upstream/master`. Expect ONLY `pnpm-lock.yaml` to conflict (we add `sonner`/optic-ui deps next to upstream bumps).
4. Resolve lock hunks keeping BOTH our additions and upstream's new versions (use `conflict://N` writes). Confirm no markers remain.
5. Commit the merge. The global watermarks-remover hook blocks it (upstream locale files contain legit ZWSP/ZWNJ/RTL marks in ar/es/fa-ir/it; also "not scanned" scss warnings). Use `WATERMARKS_REMOVER_DISABLE=1 git commit --no-edit` rather than stripping upstream strings.
6. Verify `pnpm install --frozen-lockfile --ignore-scripts`. It likely fails with `no entry for 'source-map-js@1.2.1'`: upstream override `source-map-js@>=1.0.0 <1.2.2: ^1.2.2` removed 1.2.1 but our `@tailwindcss/node` snapshot still references it. Fix by hand: change that one line to `source-map-js: 1.2.2`.
   - DON'T run `pnpm install --lockfile-only` / `--no-frozen-lockfile` and commit the result: local pnpm 9.15.9 reformats ~48 hunks (libc fields, eslint peer suffixes, gitHosted resolution) = churn. If you did, `git checkout pnpm-lock.yaml` and hand-patch only the semantic line. Also `--lockfile-only` wipes `node_modules`; re-run frozen install to restore.
7. Smoke: `pnpm --filter @logto/experience... --filter @logto/account... --filter '!@logto/experience' --filter '!@logto/account' run --if-present build`, then `pnpm build` in packages/experience and packages/account.
8. Commit lockfile fix (same hook bypass if needed), `git push origin master` (fast-forward, no force).
9. Then follow `logto-fork-submodule-build-from-source`: wait for "Optic image" workflow, commit submodule pointer in monorepo, pin image on server. Upstream syncs may add DB alterations; back up DB first.
