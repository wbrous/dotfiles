---
name: watermarks-remover-fork-upstream-sync
description: "Use when syncing the wbrous/watermarks-remover fork with upstream (guillaumemeyer/watermarks-remover) via a \"Merge upstream into fork\" PR (base=main, head=main) that has conflicts, when the PR head branch can't be pushed to — resolve by merging the PR head into the fork's main locally and pushing to main. Covers the known Makefile/clean_staged.py conflict resolutions and the machine-wide pre-commit hook blocking on intentional watermark test fixtures."
---

# Sync watermarks-remover fork with upstream (no head push)

## When
A GitHub PR on `wbrous/watermarks-remover` titled "Merge upstream into fork" (base=`main`, head=`main`, state DIRTY) needs conflict resolution, but you lack push permission to the head branch (head = `refs/pull/N/head`, a fetched upstream `main`).

## Strategy
Do NOT touch the head branch. Merge the PR head into the fork's `main` (the base) in a temp worktree, resolve, commit, and push to `main`. Because head and base are both `main`, pushing a base that contains the head's content makes GitHub auto-merge the PR — verify with `read pr://wbrous/watermarks-remover/N` (state flips to MERGED).

## Steps
1. `git fetch origin` then `git fetch origin refs/pull/N/head:refs/remotes/prN` to materialize the head.
2. Identify merge base and divergence: `git merge-base prN main`; fork `main` usually has 2–3 local commits, head has ~96 upstream commits.
3. `git worktree add /tmp/wm-resolve <fork-main-sha>`; inside it `git merge --no-commit --no-ff prN`.
4. Resolve conflicts (see below), `git add`, verify no `--diff-filter=U` files remain, `python3 -m py_compile` changed .py files, check `.PHONY` targets all have definitions.
5. Commit, then `git push origin HEAD:main` (dry-run first if unsure). Then fast-forward the local checkout: `git merge --ff-only origin/main`.
6. Clean up: `git worktree remove /tmp/wm-resolve --force && git worktree prune`.

## Known conflict resolutions (as of 2026-08)
- **Makefile `.PHONY`** — both sides add different phony targets to one multi-line declaration: take the **union** of both target sets, dedup shared entries (e.g. `install-cursor-text-skill` appears on both sides). Verify every listed target has a `name:` definition below.
- **service/scripts/clean_staged.py `_changed()`** — both sides independently fixed the base's buggy `return bool(result.get("actions"))` fallback (false "changed" for already-clean image/av/container files). The **fork's fix wins**: byte-length ground truth (`bytes_in != bytes_out` when both present), NOT upstream's `_is_modifying_action` filter. The fork's fix is the point of the merge.

## The pre-commit hook block (expected, do not fight)
The fork's machine-wide hook (`git config --global core.hooksPath` → `/home/wils/.config/git/hooks/pre-commit`, backed by `~/.local/share/watermarks-remover/service/scripts/check_staged.py`, mode=check) blocks the merge commit with exit 1 on **3 intentional test fixtures** that deliberately embed watermark characters:
- `tests/test_backup_preserved.py` (U+200B ZWSP)
- `tests/test_hook_written_file.py` (ZWSP ×4, U+00AD soft hyphen)
- `tests/test_lightweight_skill.py` (bidi marks U+200F/U+2066/U+2069)

These are upstream's genuine fixtures for testing removal — cleaning them breaks the tests. This is NOT a hang: the scan itself completes in ~1.6s for all 102 files; if a wrapper seems to run forever it's the terminal harness backgrounding, not the tool. Commit with the documented per-commit escape hatch:
`WATERMARKS_REMOVER_DISABLE=1 git commit --no-edit`
(Do not set `mode clean` — it would strip the test fixtures. Do not set `watermarks-remover.enabled false` — it weakens the hook for all commits. One-time disable per merge commit only. Gitleaks still runs and should pass.)

## Facts
- Fork: `wbrous/watermarks-remover`; upstream parent: `guillaumemeyer/watermarks-remover`.
- Local worktree `/tmp/wm-resolve` used for merges; harness may background long bash calls and never deliver — check `hub` jobs and run the watermark scan directly with a per-file timeout if progress is unclear.
