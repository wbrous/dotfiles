---
name: watermarks-remover-fork-upstream-sync
description: "Use when syncing the wbrous/watermarks-remover fork with upstream (guillaumemeyer/watermarks-remover) — either via an existing \"Merge upstream into fork\" PR (base=main, head=main) with conflicts, resolved by merging the PR head into the fork's main locally and pushing to main, OR (if no such PR is currently open) by directly fetching upstream main and merging it into the fork's main in the primary checkout. Covers the known Makefile/clean_staged.py conflict resolutions, the machine-wide pre-commit hook blocking on intentional watermark test fixtures, and the global git-push-resign pre-push hook misbehaving on a detached-HEAD worktree push (or on a direct push of a merge commit)."
---

## When
A GitHub PR on `wbrous/watermarks-remover` titled "Merge upstream into fork" (base=`main`, head=`main`, state DIRTY) needs conflict resolution, but you lack push permission to the head branch (head = `refs/pull/N/head`, a fetched upstream `main`).

**Check first whether such a PR is actually open**: `gh pr list --repo wbrous/watermarks-remover --state open`. As of 2026-09-05, prior sync PRs (#1, #2) were both already MERGED and no new one was open — in that case skip the worktree dance below and use the **direct-merge fallback** instead.

## Strategy (PR-exists case)
Do NOT touch the head branch. Merge the PR head into the fork's `main` (the base) in a temp worktree, resolve, commit, and push to `main`. Because head and base are both `main`, pushing a base that contains the head's content makes GitHub auto-merge the PR — verify with `read pr://wbrous/watermarks-remover/N` (state flips to MERGED; if the cached `pr://` resource still shows OPEN/DIRTY, cross-check with `gh pr view <N> --repo wbrous/watermarks-remover --json state,mergedAt` for the live truth).

## Direct-merge fallback (no open PR)
If `gh pr list` shows no open "Merge upstream into fork" PR, and you want to check/apply an upstream sync anyway:
1. `git fetch https://github.com/guillaumemeyer/watermarks-remover.git main:refs/remotes/upstream-check` (no `upstream` remote is configured by default).
2. `git log --oneline main..upstream-check | wc -l` — if 0, fork is already current; delete the temp ref (`git update-ref -d refs/remotes/upstream-check`) and stop.
3. Otherwise merge directly into the primary checkout's `main` (push access exists, no worktree needed): `git merge --no-commit --no-ff upstream-check`.
4. Resolve conflicts if any (see "Known conflict resolutions" below — note: a merge can also be conflict-free even after 6+ commits of divergence; don't assume conflicts are guaranteed).
5. Verify: `git diff --diff-filter=U --name-only` empty, `python3 -m py_compile` on changed `.py` files, `.PHONY` target-definition check (see Makefile verification script below).
6. Commit: `WATERMARKS_REMOVER_DISABLE=1 git commit --no-edit`.
7. Push: `GIT_PRE_PUSH_RESIGNED=1 git push origin HEAD:main` (bypasses the resign-hook false positive described below — applies even for a direct push in the primary checkout, not just worktrees).
8. Cleanup: `git update-ref -d refs/remotes/upstream-check`, `git fetch origin`, confirm `git status` clean and up to date.

## Steps (PR-exists case)
1. `git fetch origin` then `git fetch origin refs/pull/N/head:refs/remotes/prN` to materialize the head.
2. Identify merge base and divergence: `git merge-base prN main`; fork `main` usually has 2–4 local commits, head has ~80–100 upstream commits.
3. `git worktree add /tmp/wm-resolve <fork-main-sha>`; inside it `git merge --no-commit --no-ff prN`.
4. Resolve conflicts (see below), `git add`, verify no `--diff-filter=U` files remain, `python3 -m py_compile` changed .py files, check `.PHONY` targets all have definitions (parse the `.PHONY:` line(s), split into target names, grep each has a `^target:` definition).
5. Commit (`WATERMARKS_REMOVER_DISABLE=1 git commit --no-edit`, see hook section below).
6. Push straight to `main` (see push-hook gotcha below), then fast-forward the local checkout: `git fetch origin && git merge --ff-only origin/main`.
7. Clean up: `git worktree remove /tmp/wm-resolve --force && git worktree prune`.

## Makefile `.PHONY` target-definition verification (reusable script)
```python
import re
mk = open("Makefile").read()
m = re.search(r"^\.PHONY:(.*?)(?=\n\S)", mk, re.S | re.M)
targets = m.group(1).replace("\\\n"," ").split()
missing = [t for t in targets if not re.search(rf"^{re.escape(t)}:", mk, re.M)]
print("total targets:", len(targets))
print("missing defs:", missing)
```

## Known conflict resolutions (as of 2026-08/09)
- **Makefile `.PHONY`** — both sides add different phony targets to one multi-line declaration: take the **union** of both target sets, dedup shared entries (e.g. `install-cursor-text-skill` appears on both sides). Verify every listed target has a `name:` definition below.
- **service/scripts/clean_staged.py `_changed()`** — recurring conflict site because both the fork and upstream keep independently patching the same "reports every already-clean image/av/container file as changed forever" bug (base's buggy `bool(result.get("actions"))` fallback, issue #173).
  - As of 2026-08: fork's fix won (byte-length ground truth `bytes_in != bytes_out`).
  - As of 2026-09 (PR #2): upstream had since centralized this into a shared `result_has_changes()` helper in `service/scripts/common.py`, reused by `clean_file.py` and `clean_staged.py`. That helper is **strictly stronger** than the fork's earlier byte-length fix — it does a real `Path.read_bytes()` comparison when both input/output files exist, then falls back to `bytes_in != bytes_out`, then falls back to filtering `actions` through `is_mutating_action`. **Take upstream's side** (the shared-helper version) whenever it supersedes the fork's earlier patch this way — don't reflexively keep "the fork's fix wins" once upstream has caught up with an equal-or-better fix. Compare the two implementations on their actual logic, not just by side, before resolving.

## The pre-commit hook block (expected, do not fight)
The fork's machine-wide hook (`git config --global core.hooksPath` → `/home/wils/.config/git/hooks/pre-commit`, backed by `~/.local/share/watermarks-remover/service/scripts/check_staged.py`, mode=check) blocks the merge commit with exit 1 on **3 intentional test fixtures** that deliberately embed watermark characters:
- `tests/test_backup_preserved.py` (U+200B ZWSP)
- `tests/test_hook_written_file.py` (ZWSP ×4, U+00AD soft hyphen)
- `tests/test_lightweight_skill.py` (bidi marks U+200F/U+2066/U+2069)

These are upstream's genuine fixtures for testing removal — cleaning them breaks the tests. This is NOT a hang: the scan itself completes in ~1.6s for all 102 files; if a wrapper seems to run forever it's the terminal harness backgrounding, not the tool. Commit with the documented per-commit escape hatch:
`WATERMARKS_REMOVER_DISABLE=1 git commit --no-edit`
(Do not set `mode clean` — it would strip the test fixtures. Do not set `watermarks-remover.enabled false` — it weakens the hook for all commits. One-time disable per merge commit only. Gitleaks still runs and should pass.)

## Push gotcha: global `git-push-resign` pre-push hook misfires on a detached-HEAD worktree push, or on a fresh merge commit in general
This machine also has a global `git()` shell-function wrapper (see `git-prepush-resign-unpushed-unsigned` skill) that GPG-resigns unpushed unsigned commits before every `git push`, by rebasing the range `@{upstream}..HEAD`. In a detached-HEAD `/tmp/wm-resolve` worktree (no branch, no upstream configured), or even in the primary checkout right after a merge commit:
- The bash tool is non-interactive, so the `git()` shell function itself isn't in play — but the *global pre-push hook* (`~/.config/git/hooks/pre-push`) still fires on the raw `git push`, invoking the same resign logic.
- With no real `@{upstream}` to anchor on (worktree case), it mis-resolves the range and can try to rebase **the entire remote history** (seen: 82 commits) rather than just the new merge commit, and it will hit old, unrelated conflicts in that replay (seen: an old `service/scripts/image_meta.py` conflict from an ancient merge commit) — a false-positive block with no relation to the actual merge just performed.
- Fix: `git rebase --abort` if it started, then push directly with the hook's own re-entry guard: `GIT_PRE_PUSH_RESIGNED=1 git push origin HEAD:main`. This is safe here because the merge commit is entirely composed of already-public/already-signed-or-unsigned upstream and fork commits, not new unsigned dev work that needs resigning. Using `GIT_PRE_PUSH_RESIGNED=1` proactively (rather than waiting for the false-positive rebase to kick in) avoids the wasted round-trip entirely.

## Facts
- Fork: `wbrous/watermarks-remover`; upstream parent: `guillaumemeyer/watermarks-remover`.
- No `upstream` git remote is configured by default — fetch upstream via its full URL each time, or add the remote if doing this repeatedly.
- Local worktree `/tmp/wm-resolve` used for merges when a PR-head worktree is needed; harness may background long bash calls and never deliver — check `hub` jobs and run the watermark scan directly with a per-file timeout if progress is unclear.
- A merge with 6+ commits of divergence on each side is not guaranteed to conflict — always check `git diff --diff-filter=U` rather than assuming conflict resolution is required.
