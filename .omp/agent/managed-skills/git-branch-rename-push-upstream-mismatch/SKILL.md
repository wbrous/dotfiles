---
name: git-branch-rename-push-upstream-mismatch
description: "Use when git push fails with \"The upstream branch of your current branch does not match the name of your current branch\" — typically after renaming a local branch (e.g. master → main) that was already tracking a differently-named remote branch. Also covers finishing the migration: pushing the renamed branch, setting it as the GitHub default branch via gh repo edit --default-branch, and safely checking whether the old branch name actually has any remote commits before trying to delete it."
---

## Symptom
```
fatal: The upstream branch of your current branch does not match
the name of your current branch.  To push to the upstream branch
on the remote, use

    git push origin HEAD:master
```
Happens when local branch was renamed (e.g. `git branch -m master main`) while still tracking a remote branch with the old name (`origin/master`) — `push.default=simple` (git's default) refuses to push because local and tracked-remote names differ.

## Fix: push the new name, retarget upstream tracking, one command
```sh
git push -u origin <new-name>
```
This creates `origin/<new-name>` on the remote (if it doesn't exist yet) and repoints the local branch's upstream to it in one shot — no need to fix `push.default` config or use the workaround `git push origin HEAD:master` suggested in the error (that would just keep pushing to the old name).

## Finish the migration on GitHub
```sh
gh repo edit OWNER/REPO --default-branch <new-name>
```
Switches the repo's default branch (what PRs target, what clone checks out). Do this *after* the push above, or GitHub will reject the switch if `<new-name>` doesn't exist as a remote ref yet.

## Before deleting the old branch name — check it actually has commits
Don't assume `origin/<old-name>` is a real branch with history just because local tracking metadata (`git branch -vv`) mentions it — that metadata can be stale from `git remote add`/initial fetch against an empty repo (e.g. `gh repo create` seeds a `master` ref pointer in the API response before any commit is ever pushed to it). Attempting to delete a ref that was never actually created as a commit fails cleanly and tells you this:
```sh
gh api -X DELETE repos/OWNER/REPO/git/refs/heads/<old-name>
# {"message":"Reference does not exist", ...} -> nothing to clean up, done
```
If it *does* exist with real commits, delete it the same way (only after confirming the default branch switch succeeded and the new branch has everything you need):
```sh
gh api -X DELETE repos/OWNER/REPO/git/refs/heads/<old-name>
```

## Verify final state
```sh
gh api repos/OWNER/REPO/branches --jq '.[].name'      # should list only <new-name>
gh api repos/OWNER/REPO --jq '.default_branch'          # should be <new-name>
```
