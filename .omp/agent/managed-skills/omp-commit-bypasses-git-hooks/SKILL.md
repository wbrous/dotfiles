---
name: omp-commit-bypasses-git-hooks
description: omp commit commits lack Signed-off-by/Co-authored-by trailers or skip gitleaks pre-commit; global prepare-commit-msg hook never fires for omp commit.
---

## Symptom
Commits made via `omp commit` are GPG-signed but lack hook-injected trailers (`Signed-off-by`, `Co-authored-by`), and the global gitleaks `pre-commit` never runs. Plain `git commit` in the same repo gets everything.

## Root cause (verified)
`omp commit` does NOT run `git commit`. Observed argv via a PATH shim for `git`:
`git commit-tree -S <tree> -p <parent>` then the ref is moved natively inside omp (not through the git binary). `commit-tree` is plumbing: no pre-commit, prepare-commit-msg, commit-msg hooks. Even a `reference-transaction` hook did not fire. omp has no flag/setting for signoff/trailers (flags: --push --dry-run --no-changelog --legacy -c -m).

So the hook/config is NOT broken; don't debug core.hooksPath, gpgsign, or the hook script.

## Diagnosis recipe (fast)
1. `git log -5 --format='%h %G? %s%n%b---'` — omp commits show `G` but no trailers.
2. Put a shim `git` first on PATH that logs `$*` then `exec /usr/bin/git "$@"`; run `omp commit` in a scratch repo; look for `commit-tree`.
3. omp's commitCreate is native code (not visible in the strings of the binary's embedded JS).

## Options to offer the user
- Use `omp commit --dry-run` for the message, then `git commit -m ...` (hooks run).
- Upstream feature request: run prepare-commit-msg before commit-tree / add --signoff.
- Post-commit wrapper function that amends the commit to append trailers (hack; re-signs; only if user wants).
Clean up scratch files in /tmp afterward.
