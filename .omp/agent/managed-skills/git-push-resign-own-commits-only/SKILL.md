---
name: git-push-resign-own-commits-only
description: "git push auto-resign wrapper rebases other authors' unpushed commits, conflicts mid-rebase; sign only user.email commits via git-resign-own."
---

# Symptom
`git push` prints "re-signing N unpushed unsigned commit(s)", then `CONFLICT` during
`git rebase --rebase-merges --exec 'git commit --amend --no-edit -S'` and
"resign rebase failed". Usually a shared repo where teammates' unsigned commits are unpushed locally
(e.g. after merging their branch).

# Recovery
1. `git rebase --abort` (returns to original HEAD; reflog confirms).
2. Fix the scripts below so only own commits are signed.

# Files (machine-wide, not in a repo)
- `~/.local/bin/git-push-resign`: wrapper called by the `git()` function in `~/.bashrc` for `git push` and `dotfiles push`.
- `~/.config/git/hooks/pre-push`: safety-net hook (core.hooksPath); aborts push after rewriting.
- `~/.local/bin/git-resign-own <upstream-ref> | --new-branch`: shared helper both call.

# Helper design (git-resign-own)
- Own = commit author email == `git config user.email`; unsigned = no `gpgsig` header in `git cat-file -p` (not `%G?`, which says E for unknown keys).
- Rebase starts at `<oldest own unsigned>~1` (or `--root`), not upstream.
- Refuse (exit 1) if a foreign-authored commit sits above an own unsigned one: rebase would give it a new SHA. Bypass with `command git push`.
- Capture `git log` output in a variable, not `mapfile < <(...)`, so a bad ref fails loudly.
- Hook detects a rewrite by comparing `git rev-parse HEAD` before/after; only then aborts push.

# Testing
Throwaway repo + fake `gpg.program` script that prints a PGP armor block (and `[GNUPG:] SIG_CREATED` on stderr for `--status-fd`) so `-S` works without a fingerprint prompt. Set `GIT_ALLOW_SECRETS=1` (global gitleaks hook), and push the base with `GIT_PRE_PUSH_RESIGNED=1` to bypass the hook. Verify: foreign-only no-op, own-below-foreign refuses, foreign-below-own keeps foreign SHA, already-signed no-op, bad ref non-zero, root commit. Finally `git-push-resign --dry-run` in the real repo.
