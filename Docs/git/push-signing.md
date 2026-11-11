# Push signing and resign flow

Committing unsigned during work, GPG-resigning at push time (fingerprint-gated), and recovering when the resign rebase stalls.

## Push-time resign design (unsigned dev, signed push)

**Symptom:** want `git commit` to never block on a fingerprint touch, but every pushed commit signed.

**Cause:** `commit.gpgsign=true` forces a physical touch per commit.

**Fix:** split the two phases — dev-time commits unsigned, push-time resign via a wrapper:
- Set `commit.gpgsign=false` locally on repos like `~/.dotfiles`; signing happens only at push.
- Shell-level `git()` function routes every `git push` through `~/.local/bin/git-push-resign` (generic, any repo); `dotfiles()` routes through the same script via `GIT_DIR`/`GIT_WORK_TREE`.
- The script rebases unpushed commits with `exec git commit --amend --no-edit -S`, then pushes.
- `gpg-agent` `default-cache-ttl 300` keeps a short window so a small batch needs few touches.
- Pre-push hook limitation: a hook alone cannot complete a push in one command — the hook resigns, the first push then fails with stale-SHA "remote rejected", and the re-invoked push lands. The `GIT_PRE_PUSH_RESIGNED` re-entry guard handles this.
- New-branch/no-upstream footgun: the wrapper must set upstream explicitly or the resign rebase has no base.

_Migrated from: git-prepush-resign-unpushed-unsigned_

## Only sign your own commits on shared branches

**Symptom:** a blanket resign rebase changes foreign authors' commit SHAs.

**Fix:** replay with `--no-gpg-sign` plus a selective exec:
```sh
git rebase --no-gpg-sign --exec 'if [ "$(git log -1 --format=%ae HEAD)" = "<your-email>" ]; then git commit --amend --no-edit -S; fi' <base>
```
`--no-gpg-sign` is load-bearing — without it `commit.gpgsign=true` signs every replayed commit including foreign ones. `~/.local/bin/git-resign-own` (run by the global pre-push hook) implements exactly this selective exec.

_Migrated from: git-push-resign-own-commits-only, shared-branch-merge-handling_

## Resign rebase blocked: unstaged changes

**Symptom:** `cannot rebase: You have unstaged changes` before any gpg prompt.

**Cause:** an app wrote to a tracked file (e.g. `.config/Omacom/omawrite.conf`, `.omp/agent/last-changelog-version`) between commits.

**Fix:** commit the tree clear first, then push again:
```sh
dotfiles commit -a -m "update"
dotfiles push
```

_Migrated from: git-push-resign-rebase-blocked, git-prepush-resign-unpushed-unsigned_

## Resign rebase blocked: "gpg: signing failed: Operation cancelled"

**Symptom:** rebase halts mid-flight at an `exec` resign step.

**Cause:** each `exec git commit --amend --no-edit -S` is a *separate* gpg-agent signing operation — one fingerprint touch does NOT cover the whole batch despite the log line suggesting otherwise. A missed/expired touch halts the rebase cleanly at that step; nothing is corrupted.

**Fix:** the user runs `git rebase --continue` (or `git --git-dir=$HOME/.dotfiles --work-tree=$HOME rebase --continue`) in their own terminal, touching the sensor at each new pinentry prompt — once per remaining commit. Agents cannot do this (no physical sensor). `git status` shows "Last commands done" / "Next commands to do" with the exact remaining count and is safe to inspect read-only.

_Migrated from: git-prepush-resign-unpushed-unsigned_

## Resign rebase blocked: root-owned file from a container

**Symptom:**
```
warning: unable to unlink 'path/to/file': Permission denied
error: The following untracked working tree files would be overwritten by merge
```
`git rebase --abort` can then fail the same way, leaving the repo stuck mid-rebase (`.git/rebase-merge/done` and `git-rebase-todo` both list the same `pick`).

**Cause:** a Docker container (or other root process) wrote a file into the repo tree as root — e.g. `prisma migrate dev` in a runtime image defaulting to root with a bind mount. The file is untracked-but-blocking; a non-root user can't unlink it during checkout.

**Fix:**
1. Reclaim ownership (real PTY for fingerprint sudo, never `sudo -n`):
```sh
sudo chown -R <user>:<group> <blocking-dir>
```
2. If `git rebase --abort` then complains "would be overwritten by reset" for the same path: diff the untracked file against the target commit's blob (`git diff --no-index <file> <(git show <sha>:<path>)`). Identical → just `rm` the stray copy, then abort again.
3. Confirm clean: `git status --short --branch` shows no "rebase in progress" and the expected `ahead N`.
4. Re-run `git push`; the wrapper rebases/resigns from a clean base.

**Permanent fix:** make the image not write root-owned files — add `USER <user>` (check the base image ships a matching UID/GID user, e.g. `oven/bun:1.3-alpine` ships `bun` at 1000:1000) in the final stage, add `--chown=<user>:<user>` to every `COPY --from=...` into that stage, and verify with `docker run --rm <image> sh -c 'whoami && id && ls -la <path>'`.

_Migrated from: git-resign-rebase-blocked-by-root-owned-file_

## Resign rebase conflict inside a replayed merge commit

**Symptom:** `--rebase-merges` resign rebase stops on `CONFLICT` in a merge replayed as `merge -C <sha> <label>`; output says "resign rebase failed. Resolve conflicts, then run 'git push' again."

**Fix:**
1. `git status` → note the `merge -C <sha>` line; `<sha>` is the ORIGINAL merge commit, still reachable.
2. Resolve each conflict using the merge's parents as ground truth:
```sh
git diff <sha>^1 <sha>^2 -- <file>
git log <sha>^2 -- <file>
```
Prefer what the original merge recorded. Modify/delete: check references, `git rm` if the original merge dropped it (`git cat-file -e <sha>:<path>`). Add/add: `git checkout --ours/--theirs <file>` ("ours" = rebased HEAD side during merge replay).
3. Verify before continuing — must be empty (identical to the original merge):
```sh
git diff --cached <sha> --stat
```
Non-empty means the new base leaked changes in; inspect each file (e.g. one side calling APIs absent from the other's resolved version won't compile). Restore the reconciled version with `git checkout <sha> -- <path>`.
4. `GIT_EDITOR=true git rebase --continue` (filter noisy gitleaks output). Later merges may conflict again; repeat. Then compile and `git push`.
5. After finishing, check for silently dropped features vs `origin/<branch>` (e.g. `git grep -c Symbol`) and report to the user; don't fix unasked.

_Migrated from: git-resign-rebase-merge-conflict-verify-against-original_

## Commits hang waiting for a fingerprint touch

**Symptom:** `git commit` from a background tool hangs ~2 minutes, then:
```
gpg: signing failed: Timeout
fatal: failed to write commit object
```

**Cause:** `commit.gpgsign=true` + fingerprint-gated pinentry waits for a physical touch that a background shell can never surface.

**Fix:** run the commit in a real PTY (hub start with `pty: true`) and tell the user to touch the sensor now. `gpg-agent` caches the key for only `default-cache-ttl` (often 300s), so each new commit can need a fresh touch. Message-quoting pitfall through a `bash -c` wrapper: `-m "..."` with parens/newlines breaks the shell (pathspec errors). Write the message to a temp file and use `git commit -F /tmp/commit_msg.txt` instead — mandatory for multi-line/bullet messages.

_Migrated from: git-commit-gpg-fingerprint-timeout-retry_
