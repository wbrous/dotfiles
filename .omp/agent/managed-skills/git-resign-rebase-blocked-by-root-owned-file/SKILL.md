---
name: git-resign-rebase-blocked-by-root-owned-file
description: "Use when the git-push-resign wrapper's rebase (or a plain rebase) fails/aborts with \"unable to unlink ... Permission denied\" then \"untracked working tree files would be overwritten\"; also git rebase --abort itself fails the same way. Caused by a bind-mounted Docker container (e.g. Prisma migrate) writing files as root into the repo tree."
---

## Symptom

`git push` (via the `git-push-resign` wrapper, or any interactive rebase) fails mid-pick:

```
warning: unable to unlink 'path/to/file': Permission denied
error: The following untracked working tree files would be overwritten by merge:
   path/to/file
Please move or remove them before you merge.
Aborting
```

Rebase is left mid-flight (`git status` shows "interactive rebase in progress"; `.git/rebase-merge/done` and `git-rebase-todo` may show the same commit listed as both done and still-pending — this is not corruption, just the failed-pick bookkeeping).

Then `git rebase --abort` **also fails** with the same class of error:

```
error: The following untracked working tree files would be overwritten by reset:
	path/to/file
Please move or remove them before you reset.
Aborting
fatal: could not move back to <sha>
```

## Root cause

A file the target commit tracks already exists on disk, untracked (or at least unremovable), and is **owned by root** — typically because a Docker container with the repo bind-mounted (e.g. `prisma migrate dev` run inside a container without `user: "${UID}:${GID}"`) wrote it as root. Your user has no write permission on the file (or its parent dir), so git can neither unlink it during checkout nor clear it during reset/abort.

## Fix

1. Confirm the culprit: `stat <path>` — look for `Uid: (0/root)`.
2. Reclaim ownership via interactive sudo (fingerprint auth has no passwordless `-n`; use a PTY-capable bash call): `sudo chown -R <you>:<you> <parent-dir-of-file>`.
3. Sanity-check content before deleting anything: `git diff --no-index <disk-file> <(git show <sha>:<path>)` — if empty, it's identical to the committed blob.
4. If content matches (or you don't need it), `rm -rf` the now-owned-by-you conflicting path directly — this clears the block for both the stalled pick and `git rebase --abort`.
5. Run `git rebase --abort`; it should now succeed and land you back on the pre-rebase commit with a clean tree (`git status --short --branch`).
6. Re-run `git push` — the resign wrapper will redo the rebase+sign (requires a fresh fingerprint touch) and this time the checkout succeeds since the path is no longer root-owned.

## Prevent recurrence

If the offending path is Docker-generated (e.g. Prisma migrations in a bind-mounted app dir), the container is writing as root. Fix at the source: add `user: "${UID}:${GID}"` to the relevant `docker-compose.yml` service, or generate the artifact on the host instead of in-container. Otherwise every subsequent migration/build will re-create root-owned files and reproduce this exact failure.
