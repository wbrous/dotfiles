---
name: git-push-rejected-after-upstream-history-rewrite
description: "Use when git push to main (or any branch) is rejected with \"fetch first\" / \"Updates were rejected because the remote contains work that you do not have locally\", and git fetch shows the remote ref was force-updated to commits with the same messages but different SHAs than local history — indicates the remote history was rewritten (rebase/filter/squash) upstream, not a normal divergence. Also covers google-voice-ws / google-voice-client repo specifically."
---

## Symptom

`git push` fails with:

```
! [rejected]        main -> main (fetch first)
```

`git fetch` output includes `(forced update)` for the branch ref, and `git log --oneline HEAD..origin/main` / `origin/main..HEAD` show commits with **matching messages but different SHAs** on both sides — i.e. `git merge-base HEAD origin/main` returns nothing (no common ancestor at all, or a stale one far back).

This is NOT a normal "someone pushed new commits" divergence — it means the remote branch's history itself was rewritten (rebase, `filter-repo`, squash, secret-scrub, etc.) while you had an older version checked out locally.

## Diagnosis

1. `git fetch origin`
2. `git log --oneline HEAD..origin/main` and reverse — compare commit *messages*, not just count.
3. For same-message commits with different hashes, confirm content is identical:
   ```
   git diff <local-sha> <origin-sha> --stat
   ```
   Empty output = identical tree, confirms this is a pure history rewrite, not a content fork.

## Fix: don't merge diverged rewritten history — replay your new work on top

```
git branch backup-local-main        # safety net, delete once pushed
git checkout -B main origin/main    # reset local main to the rewritten upstream
git cherry-pick <your-new-commit-sha>   # replay only the commit(s) origin doesn't have
git push origin main
git branch -D backup-local-main     # cleanup; -D not -d since backup diverged from new main
```

Never `git merge`/`git pull` in this situation — with no common ancestor it either fails outright or produces a duplicate-content merge commit. Cherry-picking the specific new commit(s) onto the fresh `origin/main` is the correct minimal fix.

## Applies to

Seen in `google-voice-ws` (remote `wbrous/google-voice-client`) — upstream history was rewritten (commit SHAs changed, messages preserved) between sessions, likely from a rebase/secret-scrub. Same recipe applies generally.
