---
name: git-push-resign-rebase-blocked
description: "Use when dotfiles push (or any git push routed through ~/.local/bin/git-push-resign) fails with \"The following untracked working tree files would be overwritten by checkout\" / \"error: could not detach HEAD\" or \"cannot rebase: You have unstaged changes\" — the resign flow's rebase requires a clean worktree, and either a stale untracked file (e.g. an app/hook-recreated .bak whose path exists in an intermediate rebased tree) or any unstaged tracked-file modification blocks it."
---

## Goal

Diagnose and clear the two blockers that make `git-push-resign`'s resign-rebase abort, so `dotfiles push` completes. The resign flow (`~/.local/bin/git-push-resign`, routed via the `dotfiles()`/`git()` shell functions in `~/.bashrc`) runs `git rebase --rebase-merges --exec 'git commit --amend --no-edit -S' <upstream>` to GPG-sign all unpushed commits, then pushes. A rebase requires a clean worktree — anything untracked-at-a-colliding-path or unstaged blocks it.

## Symptom 1: untracked file would be overwritten

```
error: The following untracked working tree files would be overwritten by checkout:
   .claude/settings.json.bak
Please move or remove them before you switch branches.
Aborting
error: could not detach HEAD
git-push: ERROR — resign rebase failed. Resolve conflicts, then run 'git push' again.
```

**Why:** the rebase replays commits from `origin/main..HEAD`, checking out intermediate trees. If a path exists in some intermediate commit but was later deleted in the final history (e.g. commit `4f05772` added `.claude/settings.json.bak`, `5495e7a` deleted it), the replay needs that file on disk — and an untracked copy recreated by an app/hook (Claude, omarchy, etc.) collides.

**Diagnosis (with the dotfiles bare-repo prefix):**
```bash
DOT="git --git-dir=$HOME/.dotfiles --work-tree=$HOME"
$DOT status                          # confirm the file is untracked
$DOT ls-tree HEAD -- <path>          # NOT in HEAD => repo's final state doesn't want it
$DOT log --all --oneline -- <path>   # history shows add-then-delete => stale artifact
diff <path> <tracked-sibling>        # byte-identical to tracked file => zero data loss
fuser <path>                         # ensure no process holds it open
```

**Fix:** only after confirming it's untracked, absent from HEAD, and redundant with tracked content: `rm -f <path>`. Do NOT blanket-gitignore `*.bak` — legitimate backup files would get hidden from future dotfiles surveys.

## Symptom 2: unstaged changes block the rebase

```
git-push: re-signing 22 unpushed unsigned commit(s) (one fingerprint scan)...
error: cannot rebase: You have unstaged changes.
error: Please commit or stash them.
git-push: ERROR — resign rebase failed. Resolve conflicts, then run 'git push' again.
```

**Why:** the resign rebase cannot run on a dirty worktree. Common source: a tracked dotfile modified outside git (e.g. `~/.omp/agent/config.yml` rewritten by the omarchy-theme-sync script's yq in-place edit — reformats `{}` flow style, quote style, adds trailing newline, plus the intended theme change).

**Fix:** commit the change if it's intended (e.g. theme now pointing at the live Omarchy theme) or stash it; then re-run. `git stash` works too if the change shouldn't be committed yet.

## Re-running the push

The `dotfiles` shell function is only in `~/.bashrc` (interactive shells); in a script/agent shell invoke the binary directly:

```bash
cd ~ && GIT_DIR="$HOME/.dotfiles" GIT_WORK_TREE="$HOME" command git-push-resign
```

This re-runs the whole resign+push; it re-scans and re-signs any still-unsigned commits. No rebase is left half-done after a failure (git aborts cleanly; verify with `ls ~/.dotfiles/rebase-merge ~/.dotfiles/rebase-apply`).

## Verification after success

```bash
GIT_DIR="$HOME/.dotfiles" GIT_WORK_TREE="$HOME" git status   # up to date with origin/main
GIT_DIR="$HOME/.dotfiles" GIT_WORK_TREE="$HOME" git rev-list --count HEAD..origin/main  # 0
GIT_DIR="$HOME/.dotfiles" GIT_WORK_TREE="$HOME" git cat-file -p HEAD | grep -q '^gpgsig'  # signed
```

## Notes

- The colliding `.bak` may be recreated by a running app/hook; if push keeps failing on the same regenerated path, that's the signal to fix the generator or add a targeted ignore, not to fight the rebase.
- gitleaks runs on every re-signed commit during the rebase (`--exec 'git commit --amend -S'`); it scans each amended commit, so expect the gitleaks logo per commit in the output — "no leaks found" each time is normal.
