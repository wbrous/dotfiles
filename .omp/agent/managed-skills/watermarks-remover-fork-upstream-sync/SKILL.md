---
name: watermarks-remover-fork-upstream-sync
description: "Use when syncing the wbrous/watermarks-remover fork with upstream (guillaumemeyer/watermarks-remover) — via an open \"Merge upstream into fork\" PR with conflicts, or (if none open) by directly fetching upstream main and merging into the fork's main — and then propagating the result to the user's machine (vendored ~/.local/share/watermarks-remover, global git hook, omp extension). Covers known Makefile/clean_staged.py/container_meta.py conflict resolutions, the pre-commit hook blocking on intentional watermark fixtures, and the pre-push resign hook misfiring."
---

## When
User asks to "merge upstream into main / update our code / propagate to my system" for `wbrous/watermarks-remover` (fork of `guillaumemeyer/watermarks-remover`).

**Check first whether a sync PR is open**: `gh pr list --repo wbrous/watermarks-remover --state open`. Prior sync PRs (#1, #2) were MERGED; as of 2026-10-12 none open -> use the **direct-merge fallback**.

## Direct-merge fallback (no open PR) — worked 2026-10-12 (32 upstream commits, 1 conflicted file)
1. `git fetch origin && git fetch https://github.com/guillaumemeyer/watermarks-remover.git main:refs/remotes/upstream-check --force` (no `upstream` remote configured).
2. `git log --oneline main..upstream-check | wc -l` — 0 means already current; delete temp ref and stop.
3. `git merge --no-commit --no-ff upstream-check` in the primary checkout.
4. Resolve conflicts (below). With the omp `conflict://` tool: ids are renumbered after each resolve and `conflict://*` only accepts currently-registered ids — resolve the first, then re-read the file to get live ids.
5. Verify: `git diff --diff-filter=U --name-only` empty (after `git add`), no `<<<<<<<` markers, `py_compile` changed .py, `.PHONY` check script below, then full tests (below).
6. `WATERMARKS_REMOVER_DISABLE=1 git commit --no-edit`
7. `GIT_PRE_PUSH_RESIGNED=1 git push origin HEAD:main`
8. `git update-ref -d refs/remotes/upstream-check; git fetch origin`; status should be clean/up to date.

## Running tests
No `.venv` and system python lacks pytest. Throwaway venv: `python3 -m venv /tmp/wm-venv && /tmp/wm-venv/bin/pip install -q -r requirements-dev.txt && /tmp/wm-venv/bin/python -m pytest -q` (~30s, stdlib-only service otherwise; matches CI). Remove `/tmp/wm-venv` afterwards.

## Propagate to the system (after push)
The machine uses **vendored copies**, not symlinks to the checkout (`~/.local/share/watermarks-remover/.vendor-info` records the source). Refresh with, from the repo root:
- `./service/scripts/install_global_hooks.sh` (re-vendors `service/scripts`, hooks, bin; re-copies `~/.config/git/hooks/pre-commit`; keeps existing `core.hooksPath` and chained hook)
- `./integrations/omp/install.sh` (copies extension to `~/.omp/agent/extensions/remove-watermarks.ts`; user must restart omp or `/reload-plugins`)
Verify: `diff -rq service/scripts ~/.local/share/watermarks-remover/service/scripts -x __pycache__`, `diff -q` the omp extension and `service/scripts/git_hooks/pre-commit` vs `~/.config/git/hooks/pre-commit`. Smoke: in a `mktemp -d` git repo, committing a file with U+200B must exit 1; a clean file must commit.
No `remove-ai-marks`/clean-user-facing-text skill was installed for claude/codex/grok as of 2026-10-12, so skip `install_skill.py` unless the user has one installed (check `ls ~/.claude/skills ~/.grok/skills ~/.codex/skills`).

## PR-exists case
Don't touch the head branch. `git fetch origin refs/pull/N/head:refs/remotes/prN`; in `git worktree add /tmp/wm-resolve <main-sha>` do `git merge --no-commit --no-ff prN`, resolve, commit (`WATERMARKS_REMOVER_DISABLE=1`), push with `GIT_PRE_PUSH_RESIGNED=1 git push origin HEAD:main` (GitHub auto-merges the PR since head==base content), then `git fetch origin && git merge --ff-only origin/main`, `git worktree remove /tmp/wm-resolve --force && git worktree prune`. Cross-check state with `gh pr view N --json state,mergedAt` if cached `pr://` looks stale.

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
- **Makefile `.PHONY`**: union of both sides' targets, dedup; every target needs a definition.
- **service/scripts/clean_staged.py `_changed()`**: both sides keep patching the "clean files reported changed forever" bug. Upstream's shared `result_has_changes()` in `common.py` is stronger than the fork's byte-length fix — take upstream. Compare actual logic, don't reflexively keep the fork's.
- **service/scripts/container_meta.py (2026-10)**: fork's `_is_provenance_tag_value` (6-word cap on frontmatter value hits, `_PROVENANCE_VALUE_WORD_LIMIT`) vs upstream's `GENERATOR_NAME_KEYS` + `AI_FREE_TEXT_MARKER_RE` + `named_value_is_ai(name, value)` (used in frontmatter inspect/clean and HTML meta). Upstream supersedes the fork's patch and has tests (`tests/test_prose_values_not_provenance.py`). Take **upstream (@theirs)** for all 3 hunks (helper block + two call sites); no other refs to the fork helper existed. General rule: when both sides fix the same false-positive, take upstream's once it is structurally stronger and tested; grep for remaining references to the dropped helper.

## Pre-commit hook block (expected)
Global hook (`core.hooksPath` -> `~/.config/git/hooks/pre-commit`, backed by vendored `check_staged.py`, mode=check) blocks merge commits on intentional fixtures (`tests/test_backup_preserved.py`, `test_hook_written_file.py`, `test_lightweight_skill.py`) that embed ZWSP/soft-hyphen/bidi chars. Use one-time `WATERMARKS_REMOVER_DISABLE=1 git commit --no-edit`; never set mode clean or disable globally. Gitleaks still runs.

## Push gotcha
Global pre-push resign hook can try to rebase the whole remote history on a detached worktree or fresh merge commit and hit unrelated old conflicts. Avoid by `GIT_PRE_PUSH_RESIGNED=1 git push origin HEAD:main` up front (`git rebase --abort` if it already started).

## Facts
- A merge with many commits of divergence may conflict in only one file or none — always check `--diff-filter=U`.
- Harness may background long bash calls; run scans directly with timeouts if unclear.
