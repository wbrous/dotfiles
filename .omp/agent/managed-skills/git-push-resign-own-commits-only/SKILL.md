---
name: git-push-resign-own-commits-only
description: "git push auto-resign wrapper rebases other authors' unpushed commits, conflicts mid-rebase; sign only user.email commits via git-resign-own. Also: dotfiles push fails \"No pinentry\"/resurrects old hooks because the resign rebase rewrites $HOME."
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
- **Rebase runs in a throwaway detached `git worktree`**, never the caller's work tree (see next section). It checks `new_tip^{tree} == orig_tip^{tree}`, errors if `new_tip == orig_tip`, and advances the branch with `git update-ref refs/heads/$branch NEW OLD` (compare-and-swap, so a concurrent autosync commit isn't clobbered).

# Gotcha: dotfiles bare repo (work tree = $HOME) + in-place rebase
Symptoms: `gpg: signing failed: No pinentry` (journal: `can't connect to the PIN entry module ... IPC connect call failed`), plus stale removed tools reappearing (e.g. an old global pre-commit hook printing messages). Cause: rebasing onto an old base checks out each intermediate commit INTO $HOME, deleting files tracked only at later commits (`~/.local/bin/pinentry-fprintd`) and resurrecting old versions of live config. A failed mid-rebase leaves $HOME in that old state; `git --git-dir=$HOME/.dotfiles --work-tree=$HOME rebase --abort` restores it.
Fix: worktree isolation. In the helper, run the rebase subshell with `unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE; cd "$wt"`.
Trap: read the worktree HEAD with `cd "$wt" && git rev-parse HEAD`. `git --git-dir=$main_gitdir -C $wt rev-parse HEAD` resolves against the MAIN repo's HEAD and silently returns the unsigned original tip.

# Testing
Throwaway repo + fake `gpg.program` script that prints a PGP armor block (and `[GNUPG:] SIG_CREATED` on stderr for `--status-fd`) so `-S` works without a fingerprint prompt. Set `GIT_ALLOW_SECRETS=1` (global gitleaks hook), and push the base with `GIT_PRE_PUSH_RESIGNED=1` to bypass the hook. Pass the fake gpg via `GIT_CONFIG_COUNT/KEY_n/VALUE_n` env so it survives into the temp worktree. Commit author email must equal `user.email` or the helper no-ops (exit 0, nothing signed). Assert on real `gpgsig` header counts, not exit codes. Verify: foreign-only no-op, own-below-foreign refuses, foreign-below-own keeps foreign SHA, already-signed no-op, bad ref non-zero, root commit, bare+work-tree layout keeps tip-only files, failing signer leaves branch/work tree untouched. Finally `git-push-resign --dry-run` in the real repo.
