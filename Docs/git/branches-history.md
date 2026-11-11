# Branches, remotes, and history rewrites

Diverged histories, renamed branches, submodule false-empties, and undoing merged PRs.

## Push rejected after upstream history rewrite

**Symptom:** `git push` fails `[rejected] main -> main (fetch first)`; `git fetch` shows `(forced update)`; `git log HEAD..origin/main` and the reverse show matching messages but different SHAs; `git merge-base HEAD origin/main` returns nothing or a stale ancestor.

**Cause:** remote history was rewritten (rebase, filter-repo, squash, secret-scrub) while you held the old version — not a normal divergence.

**Fix:** don't merge; replay your new work on top:
```sh
git branch backup-local-main
git checkout -B main origin/main
git cherry-pick <your-new-commit-sha>
git push origin main
git branch -D backup-local-main
```

_Migrated from: git-push-rejected-after-upstream-history-rewrite_

## Renamed local branch still tracks the old remote name

**Symptom:**
```
fatal: The upstream branch of your current branch does not match
the name of your current branch.
```

**Cause:** `git branch -m master main` while still tracking `origin/master`; `push.default=simple` refuses.

**Fix:** push the new name and retarget tracking in one shot (don't use the suggested `git push origin HEAD:master` — that keeps pushing to the old name):
```sh
git push -u origin <new-name>
gh repo edit OWNER/REPO --default-branch <new-name>
```
Switch the default branch only after the push lands. Before deleting `origin/<old-name>`, check it actually has commits — `git branch -vv` metadata can be stale from an empty-repo `gh repo create`:
```sh
gh api -X DELETE repos/OWNER/REPO/git/refs/heads/<old-name>
# {"message":"Reference does not exist"} -> nothing to clean up
```
_Migrated from: git-branch-rename-push-upstream-mismatch_


## SSH remote fails host-key verification; fall back to HTTPS

**Symptom:** `Host key verification failed. fatal: Could not read from remote repository.` on a `git@github.com:...` remote in a fresh sandbox with no `known_hosts` entry.

**Fix:** switch to HTTPS and let `gh` supply credentials:
```sh
git remote set-url origin https://github.com/OWNER/REPO.git
gh auth setup-git
git push --force origin main
```
Prefer adding remotes as `https://` from the start in agent/sandbox environments.

_Migrated from: git-remote-ssh-host-key-fallback-https-gh-auth_

## Bootstrapping a fresh local dir onto an existing remote branch

**Symptom:** project directory has real files but no `.git`, and the user explicitly wants it to become the new history of an existing repo's default branch (discarding old remote history).

**Fix:** prefer `https://` remotes from the start in agent/sandbox environments:
```sh
git init -b main
git add -A
git -c user.email="..." -c user.name="..." commit -m "..." --no-verify
git remote add origin https://github.com/OWNER/REPO.git
gh auth setup-git
git push --force origin main
```
Existing nested `.gitignore` files are respected automatically by root `git add -A`. Genuinely destructive — only with explicit unambiguous user instruction.

_Migrated from: git-remote-ssh-host-key-fallback-https-gh-auth_

## submodule add claims an empty repository

**Symptom:** `git submodule add <url> <path>` → "You appear to have cloned an empty repository" / "You are on a branch yet to be born".

**Cause:** often a false positive (raced clone, default-branch mismatch) — GitHub repos with an auto-generated README do have history.

**Fix:** check before assuming empty:
```sh
cd <path>
git fetch origin
git branch -r
git log origin/main --oneline
```
If commits exist, clean up fully and retry:
```sh
rm -rf <path> .git/modules/<path>
git submodule add <url> <path>
```
Trap: don't `git init` + placeholder commit + push into a "fix" — if the remote already has history the push is rejected non-fast-forward.

_Migrated from: git-submodule-add-empty-repo-false-positive_

## Undo a merged PR when later commits depend on it

**Symptom:** `git revert -m 1 <merge>` produces rename/delete conflicts because later commits moved files the merge added.

**Fix:** triage read-only first (`gh pr view N --json mergeCommit,mergedBy,mergedAt`; `git fetch`; dry-run the revert in a throwaway worktree `git worktree add --detach /tmp/probe <tip>`). If conflicts are heavy, rebuild: `git branch backup/pre-revert-main <old-tip>`, `git worktree add -b rebuild /tmp/rebuild <first-parent-before-merge>`, cherry-pick the user's commits oldest-first (list what the merge brought with `git log a..merge^2` — replay all of the user's side, not just the latest). On modify/delete conflicts keep the other side's file and port their content into new locations; never silently drop another author's additions. Verify (no merge commits, typecheck/tests, link check), re-`git fetch`, confirm no open PRs and branch protection allows it, then `git push --force-with-lease=main:<inspected-sha> origin HEAD:main` — only with explicit user instruction. Gotchas: stale root-owned dirs from Docker bind-mounts need `sudo rm -rf`; the PR head branch still contains the merge and can reintroduce it; GitHub still shows the PR as merged afterward.

_Migrated from: git-undo-merged-pr-with-dependent-commits_
