---
name: git-undo-merged-pr-with-dependent-commits
description: Use when asked to revert/undo a merged PR on shared main and git revert -m 1 conflicts because later commits (renames/moves) build on the merge; rebuild main via worktree + cherry-pick instead.
---

# Undo a merged PR when later commits depend on it

## Triage first (read-only)
1. `gh pr view N --json mergeCommit,mergedBy,mergedAt`; `git fetch`; `git log --graph origin/main`.
2. Dry-run `git revert -m 1 <merge> --no-commit` in a **throwaway worktree** (`git worktree add --detach /tmp/probe <tip>`). Many rename/delete conflicts => later commits moved files the merge added; a plain revert will also undo your own later work. Stop and tell the user before touching main.
3. List what the merge brought in: `git log a..merge^2` (author per commit) vs `merge-base..merge^1`. Commits from the user's own side that arrived only via the merge must be replayed, not just the last one — cherry-picking only the latest commit conflicts.

## Rebuild (when user says: go back before the merge, cherry-pick mine)
1. `git branch backup/pre-revert-main <old tip>` (keep the escape hatch).
2. `git worktree add -b rebuild /tmp/rebuild <first-parent-before-merge>`; cherry-pick the user's commits oldest-first, dry-running in a probe first.
3. On conflicts where the other side added content to files you deleted/restructured (modify/delete): keep their file and port their new content into your new doc locations; repoint dead links. Never silently drop another author's additions.
4. Verify in the worktree: no merge commits, typecheck/tests for touched packages, link check.
5. Re-`git fetch`, confirm origin/main unchanged, no open PRs, check branch protection, then `git push --force-with-lease=main:<inspected sha> origin HEAD:main`. Only with explicit user instruction.
6. `git worktree remove`, then `git reset --hard origin/main` in the main checkout.

## Gotchas
- Docker bind-mounting a nonexistent `./path/file` creates a root-owned *directory* there; after moving a mounted file the stale root-owned dir blocks branch switches/reverts (`cannot rmdir`). Needs `sudo rm -rf`; use a worktree meanwhile.
- The PR head branch (e.g. dev-bang) still contains the merge; warn the user it can reintroduce it.
- PR stays shown as merged on GitHub after the force-push.
