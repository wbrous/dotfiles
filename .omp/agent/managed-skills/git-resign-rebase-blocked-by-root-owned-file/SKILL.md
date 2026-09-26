---
name: git-resign-rebase-blocked-by-root-owned-file
description: "Use when the git-push-resign wrapper's rebase (or a plain rebase) fails/aborts with \"unable to unlink...Permission denied\" / \"untracked working tree files would be overwritten\" because a container wrote files into the repo as root; also covers the permanent Dockerfile fix (non-root USER matching host UID/GID) to prevent recurrence."
---

## Symptom

`git push` (via the `git-push-resign` wrapper, or a plain rebase) fails mid-rebase with:

```
warning: unable to unlink 'path/to/file': Permission denied
error: The following untracked working tree files would be overwritten by merge:
   path/to/file
Please move or remove them before you merge.
Aborting
```

`git rebase --abort` can then ALSO fail with the same "would be overwritten by reset" error, leaving the repo stuck mid-rebase (`git status` shows "interactive rebase in progress", `.git/rebase-merge/done` and `git-rebase-todo` may both list the same `pick <sha>` — the pick never completed, it just looks duplicated because of how the todo file gets re-displayed after a failed step).

## Root cause

A Docker container (or any process) wrote a file into the repo tree while running as **root**, e.g. `prisma migrate dev` executed inside a container whose runtime image defaults to root and either bind-mounts the repo or was itself the process that generated the file on a host path the agent/session later sees as part of the working tree. The file is then untracked-but-blocking (root-owned, mode 0644, dir 0755 root:root) — a non-root host user has no write permission on the parent directory to unlink it, so any checkout/reset that needs to replace that path fails.

## Recovery (agent can do this fully — no physical dependency)

1. Reclaim ownership: `sudo chown -R <user>:<user> <blocking-dir>` — requires an interactive PTY for fingerprint/password auth (see `sudo-interactive-tty-via-hub` skill): run via `bash` with `pty: true`, NOT `sudo -n`.
2. If `git rebase --abort` then fails with "would be overwritten by reset" for the same path: diff the untracked file against the target commit's blob (`git diff --no-index <file> <(git show <sha>:<path>)`). If content is identical, just `rm` the stray untracked copy — it's a leftover from the failed checkout, not something to preserve — then abort again.
3. Confirm clean state: `git status --short --branch` shows no "rebase in progress" and the expected `ahead N` count.
4. Re-run `git push`; the resign wrapper will rebase/re-sign again from a clean base — this now succeeds since the blocking path is gone/re-owned.

## Permanent fix: make the Docker image not write root-owned files

If a Dockerfile/image is what generated the root-owned file (directly, or via a bind mount), fix it at the source instead of just cleaning up each time:

- Check whether the base image already ships a non-root user matching the host's UID/GID: `docker run --rm <image> sh -c 'id <user>'` (e.g. `oven/bun:1.3-alpine` ships a `bun` user at uid/gid 1000 — this matches a typical single-user Linux dev host's default UID 1000 exactly).
- Add `USER <user>` in the Dockerfile's final/runtime stage.
- Any `COPY --from=<stage> ...` lines copying into that stage MUST add `--chown=<user>:<user>` — `USER` alone does not retroactively fix ownership of files already copied in as root; without `--chown`, the process runs as non-root but can't write into root-owned copied directories, breaking things differently.
- Verify: `docker build ...` then `docker run --rm <image> sh -c 'whoami && id && ls -la <path>'` — confirms the process identity and file ownership both match the intended non-root user before relying on it.

This closes the hole so that if the path is ever bind-mounted from the host again (dev override, debugging), files the container writes land owned by the host user, not root — no more one-off `chown` recovery needed.
