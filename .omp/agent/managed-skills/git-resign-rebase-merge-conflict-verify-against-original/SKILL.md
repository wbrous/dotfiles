---
name: git-resign-rebase-merge-conflict-verify-against-original
description: git push pre-push resign rebase (rebase-merges) stops on CONFLICT in a merge commit; resolve and verify against the original merge.
---

## Context
The global pre-push hook re-signs unpushed unsigned commits with an interactive `--rebase-merges` rebase onto the remote tip. Merge commits get replayed (`merge -C <sha> <label>`), so old merge conflicts reappear (rerere reuses some resolutions). Output: "resign rebase failed. Resolve conflicts, then run 'git push' again."

## Procedure
1. `git status` -> note "Last commands done" and the `merge -C <sha>` line; that <sha> is the ORIGINAL merge commit (still reachable, e.g. `2e503e0`).
2. Resolve each conflict. For content conflicts decide using the merge's parents: `git diff <sha>^1 <sha>^2 -- file`, `git log <sha>^2 -- file`. Prefer what the original merge recorded.
   - Modify/delete: check references (`grep`), then `git rm` if original merge dropped it (`git cat-file -e <sha>:path`).
   - add/add: `git checkout --ours|--theirs file` (during a merge replay, "ours" = rebased HEAD side).
3. Verify BEFORE continuing: `git diff --cached <sha> --stat`. Empty = identical to the original merge. Non-empty = the new base leaked changes in; inspect each file. Example gotcha: a file taking the new base's version calls APIs absent from the other file's resolved version -> won't compile. `git checkout <sha> -- path` restores the reconciled version.
4. `GIT_EDITOR=true git rebase --continue` (filter noisy gitleaks output with grep). Later merges may conflict again; repeat.
5. Compile (`./gradlew :TeamCode:compileDebugJavaWithJavac` for Biobuzz), then `git push`.

## Also check
After finishing, compare features lost vs `origin/<branch>` (e.g. `git grep -c Symbol origin/branch` vs HEAD). Merge resolutions from earlier can silently drop features; report to user, don't fix unasked.
