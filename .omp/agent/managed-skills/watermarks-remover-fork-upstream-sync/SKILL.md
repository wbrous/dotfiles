---
name: watermarks-remover-fork-upstream-sync
description: "Use when syncing the wbrous/watermarks-remover fork with upstream (guillaumemeyer/watermarks-remover) — via an open \"Merge upstream into fork\" PR with conflicts, or by directly fetching upstream main and merging into the fork's main. Covers known Makefile/clean_staged.py/container_meta.py conflict resolutions, the pre-commit hook blocking on intentional watermark test fixtures, the pre-push resign hook misfire, running the test suite in a temp venv, and propagating to the system (global git hooks + omp extension only)."
---

## When
Syncing `wbrous/watermarks-remover` (fork) with upstream `guillaumemeyer/watermarks-remover`.

**Check first whether a PR is open**: `gh pr list --repo wbrous/watermarks-remover --state open`. If none (the usual case since PRs #1/#2 merged), use the **direct-merge fallback**.

## Direct-merge fallback (no open PR)
1. `git fetch origin && git fetch https://github.com/guillaumemeyer/watermarks-remover.git main:refs/remotes/upstream-check --force` (no `upstream` remote configured).
2. `git log --oneline main..upstream-check | wc -l` — if 0, already current; `git update-ref -d refs/remotes/upstream-check` and stop.
3. `git merge --no-commit --no-ff upstream-check` in the primary checkout (push access exists).
4. Resolve conflicts (see below). Conflict ids from the `conflict://` tool get renumbered after each resolve — re-read the list before bulk-resolving. A merge may also be conflict-free.
5. Verify: no `git diff --diff-filter=U` after `git add`, py_compile changed files, Makefile `.PHONY` script, and the **full test suite** (below).
6. Commit: `WATERMARKS_REMOVER_DISABLE=1 git commit --no-edit`.
7. Push: `GIT_PRE_PUSH_RESIGNED=1 git push origin HEAD:main`.
8. Cleanup: `git update-ref -d refs/remotes/upstream-check`, `git fetch origin`, confirm `git status -sb` in sync.

## Running tests (no .venv in repo, system python lacks pytest)
`python3 -m venv /tmp/wm-venv && /tmp/wm-venv/bin/pip install -q -r requirements-dev.txt && /tmp/wm-venv/bin/python -m pytest -q` (~30s, ~1500 tests; CI uses only requirements-dev.txt). Delete `/tmp/wm-venv` afterwards.

## Propagating to the system (user wants ONLY omp + git hooks, nothing else)
After pushing, from the checkout run exactly:
- `./service/scripts/install_global_hooks.sh` — re-vendors all of `service/scripts` into `~/.local/share/watermarks-remover/` and refreshes `~/.config/git/hooks/pre-commit` (hooksPath/mode settings preserved).
- `./integrations/omp/install.sh` — copies the extension to `~/.omp/agent/extensions/remove-watermarks.ts`. User must restart omp or `/reload-plugins`.
Do NOT install skills (claude/codex/grok/cursor via install_skill.py / make install-*). Verify with `diff -rq service/scripts ~/.local/share/watermarks-remover/service/scripts -x __pycache__` and a throwaway-repo commit with a ZWSP file (should be blocked, rc=1) plus a clean file (rc=0).

## Makefile `.PHONY` verification
```python
import re
mk = open("Makefile").read()
m = re.search(r"^\.PHONY:(.*?)(?=\n\S)", mk, re.S | re.M)
targets = m.group(1).replace("\\\n"," ").split()
missing = [t for t in targets if not re.search(rf"^{re.escape(t)}:", mk, re.M)]
print(len(targets), missing)
```

## Known conflict resolutions
- **Makefile `.PHONY`** — take the union of both sides' targets, dedup; verify each has a definition.
- **service/scripts/clean_staged.py `_changed()`** — upstream centralized into `result_has_changes()` in `common.py` (strictly stronger than the fork's byte-length fix). Take upstream's side when it supersedes; compare logic, not just side.
- **service/scripts/container_meta.py frontmatter value-hit** (2026-10, 3 hunks) — fork had `_is_provenance_tag_value` (6-word cap, commit efdd88a) fixing "descriptive key nuked"; upstream replaced it with `named_value_is_ai(key, val)` + `GENERATOR_NAME_KEYS` + `AI_FREE_TEXT_MARKER_RE` (name-based, also used for HTML meta, has tests/test_prose_values_not_provenance.py). **Take upstream (`@theirs`) for all hunks**; fork helper had no other references or tests. Full suite passed.
General rule: when both sides patched the same bug, compare logic and take upstream's if equal-or-better.

## Pre-commit hook block (expected)
Global hook (`core.hooksPath` → `~/.config/git/hooks/pre-commit`, backed by vendored `check_staged.py`, mode=check) blocks merge commits on intentional watermark test fixtures (`tests/test_backup_preserved.py`, `test_hook_written_file.py`, `test_lightweight_skill.py`). Commit with `WATERMARKS_REMOVER_DISABLE=1 git commit --no-edit`. Don't set mode clean or disable globally. Gitleaks still runs.

## Push gotcha
Global pre-push resign hook can mis-resolve `@upstream..HEAD` (detached worktree or fresh merge commit) and try to rebase the whole history. Always push with `GIT_PRE_PUSH_RESIGNED=1 git push origin HEAD:main`.

## Facts
- Fork: `wbrous/watermarks-remover`; upstream: `guillaumemeyer/watermarks-remover`. Checkout: `~/Documents/Development/watermarks-remover`.
- PR-exists case: fetch `refs/pull/N/head`, merge into fork main in a temp worktree (`/tmp/wm-resolve`), same resolution/commit/push steps; pushing a base containing the head auto-merges the PR (verify with `gh pr view N --json state,mergedAt`).
- Test-workspace helpers: installed scripts at `~/.local/share/watermarks-remover/service/scripts/{audit_dir,clean_file}.py`; `audit_dir.py --json` exits 1 when findings exist (expected).
