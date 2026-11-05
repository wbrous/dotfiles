---
name: omp-commit-bypasses-git-hooks
description: omp commit commits lack Signed-off-by/Co-authored-by trailers or skip gitleaks pre-commit; global prepare-commit-msg hook never fires; use the commit wrapper script.
---

## Symptom
Commits made with `omp commit` have no `Signed-off-by:` trailer (and no gitleaks pre-commit scan), although plain `git commit` in the same repo gets them from the global hooks (`core.hooksPath = ~/.config/git/hooks`).

## Root cause (verified by tracing argv with a PATH git shim)
`omp commit` does NOT call `git commit`. It runs `git commit-tree -S <tree> -p <parent>` and then moves the ref natively. `commit-tree` runs no hooks, and not even a `reference-transaction` hook fires. Commits are still GPG-signed (`-S`). `omp commit` has no flag for hooks, trailers, or signoff (flags: --push, --dry-run, --no-changelog, --legacy, -c, -m). `omp` is a native binary, so `commitCreate` is not readable as JS source.

The hook itself is fine: `~/.config/git/hooks/prepare-commit-msg` appends `Signed-off-by` whenever commit.gpgsign=true and the signing key exists, and `Co-authored-by` only when `OMPCODE=1` and `coauthor-hook.trailer` is set. Don't debug the hook.

## Fix: `~/.local/bin/commit` wrapper (bash script, on PATH)
1. Record HEAD, run `omp commit "$@"` (exit on failure).
2. Skip the amend for --dry-run/--help; error if HEAD didn't move.
3. Run `env -u OMPCODE GIT_EDITOR=true git commit --amend --no-edit --quiet`. Amend DOES run hooks; the hook is idempotent (no duplicate trailers), and the amend re-signs the commit.
4. Reject `--push` (it would push before the amend rewrites the commit); the user runs `git push` afterwards (the .bashrc `git` function resigns and pushes).

## Key gotchas
- `env -u OMPCODE` is REQUIRED. The user wants `Co-authored-by` ONLY when the agent runs `git commit` itself inside omp, never for their own `commit` command. Inside an omp session `OMPCODE=1` is inherited, so without unsetting it the trailer leaks in.
- `omp commit --dry-run` output is ANSI/progress-noisy and shows `scope: null` as literal `chore(null)`; don't scrape it to feed `git commit -m`, amend instead.
- The amend's gitleaks scan sees an empty staged diff, so it does not scan what omp just committed.
- `~/.local/bin` is on PATH twice, so `type -a commit` lists it several times; harmless.
- `~/.local/bin/omp` is an ELF binary; don't `cat` it.

## Verify
In a scratch repo: `commit` then `git log -1 --format=%B` shows exactly one `Signed-off-by`, zero `Co-authored-by` (even with OMPCODE=1 set), and `%G?` is `G`. Control: a plain `git commit -m x` with OMPCODE=1 still gets both trailers.
