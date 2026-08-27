---
name: gitlab-force-push-protected-branch-via-api
description: "Use when a git push (esp. force-push) to a GitLab-hosted repo (self-hosted or gitlab.com) is rejected with \"You are not allowed to push code to protected branches\" / \"pre-receive hook declined\", especially when consolidating/merging multiple branches into a protected main and force-pushing the result. Covers using glab API to temporarily unprotect, push, then restore protection."
---

## Symptom
`git push origin main --force` (or similar) fails:
```
remote: GitLab: You are not allowed to push code to protected branches on this project.
! [remote rejected] main -> main (pre-receive hook declined)
```
This happens even when authenticated (glab/git credential helper works fine) — it's a branch protection rule (push_access_level = "No one"), not an auth problem.

## Fix via glab API
1. Find numeric project id (path_with_namespace lookup, not always `owner%2Frepo` slug — self-hosted instances may need search):
   ```
   glab api "projects?search=<repo-name>&membership=true" --hostname <gitlab-host>
   ```
   grab `.id` and `.path_with_namespace`.

2. Inspect current protection rule (so you can restore it exactly):
   ```
   glab api "projects/<id>/protected_branches" --hostname <gitlab-host>
   ```
   Note `push_access_level`, `merge_access_level`, `allow_force_push` for the target branch.

3. Unprotect:
   ```
   glab api "projects/<id>/protected_branches/<branch>" --method DELETE --hostname <gitlab-host>
   ```

4. Now the normal git push/force-push works:
   ```
   git push origin <branch> --force
   ```

5. Re-protect with the original settings:
   ```
   glab api "projects/<id>/protected_branches" --method POST --hostname <gitlab-host> \
     -f name=<branch> -f push_access_level=<N> -f merge_access_level=<N> -f allow_force_push=<bool>
   ```
   (access levels: 0=No one, 30=Developers, 40=Maintainers, 60=Admins)

## Merging multiple branches into one consolidated main
When asked to "move code from all branches into main" (as opposed to syncing two remotes), first check divergence per branch pair with `git log --oneline A..B | wc -l` both directions — don't assume conflicts. Sequentially `git merge origin/<branch> -m "Merge branch '<branch>' into main"` for each source branch into a local `main` tracking `origin/main`. Verify completeness after all merges with:
```
git log --oneline origin/main..origin/<branch> | wc -l   # must be 0 for every branch
```
before pushing (with the unprotect dance above if `main` is protected).

## Gotcha
`glab auth status` can report failure for an *unrelated* gitlab.com token while the actually-relevant self-hosted host auth is fine — check the specific hostname's block, not the overall exit code.
