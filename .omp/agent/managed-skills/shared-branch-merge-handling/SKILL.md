---
name: shared-branch-merge-handling
description: Handle git merges/signing on branches shared with other authors without rewriting their commits
---

# Non-Destructive Merge Handling

When the user asks to merge, pull, push with mixed authorship, or fix signing/refusal errors on a branch shared with other authors, follow this procedure. The invariants are: NEVER rewrite another author's commits (hashes must stay byte-identical), ONLY sign commits authored by `git config user.email`, and EVERY destructive step must have a verified restore point taken first.

## 1. Survey before touching anything

Run these read-only commands first and state the result to the user:

```
git log --format='%h %ae %G? %ad %s' --date=short -15
git status -sb
git branch -r --contains <foreign-sha>   # for each foreign commit: is it already pushed?
git stash list
```

Classify every commit in the working range as OWN (`user.email`, may sign) or FOREIGN (never touch). Note signed state (`%G?`: `G` signed, `N` unsigned). If the tree is dirty or stashes exist, stop and ask — do not proceed with uncommitted work.

## 2. Take a restore point

Before any rewrite, record the current tip SHA (`git rev-parse HEAD`) and confirm the remote ref matches expectations (`git log --oneline origin/<branch> -2`). After any successful rewrite, verify with `git diff <restore-sha> <new-tip> --stat` that only intended changes exist. Undo is `git reset --hard <restore-sha>` plus `git push --force-with-lease` if the remote moved.

## 3. Why burial happens

A `git merge` (including merge-style `git pull`) puts the user's existing commits UNDER the merged-in commits. A later sign-and-rebase then replays the foreign commits, changing their SHAs. Prevention: `git config pull.rebase true` replays own commits ON TOP instead — no burial, no foreign rewrite. There is no pre-merge git hook; prevention via rebase config is the mechanism.

## 4. Safe merge recipe (own commits on top, foreign hashes intact)

1. `git reset --hard <foreign-tip>` — base is exactly their commits at original hashes.
2. Re-apply ONLY own commits on top. Prefer `git cherry-pick --no-gpg-sign <own-shas...>` in original order. If a pick conflicts and the foreign side is just a template/stale version of the same file, resolve toward the user's content — but confirm which side wins per file, never assume.
3. If a cherry-pick's change is already present in the tree (empty pick), commit with `--allow-empty` using the original message/author/date to preserve history, or `--skip` if the commit is truly redundant — ask the user which.
4. Stamp original timestamps: `Original-date: <iso-strict author date>` trailer, placed FIRST in the trailer block (before Signed-off-by/Co-authored-by), grouped with no blank lines between trailers.
5. Sign ONLY own commits: replay with `git rebase --no-gpg-sign --exec 'if [ "$(git log -1 --format=%ae HEAD)" = "<email>" ]; then git commit --amend --no-edit -S; fi' <base>`. The `--no-gpg-sign` is load-bearing: without it `commit.gpgsign=true` signs every replayed commit including foreign ones.
6. Verify: `git log --format='%h %ae %G?'` must show foreign SHAs identical to step 1, own commits `G`, foreign `N`.
7. Push. If the remote already has a reordered/buried version, that requires `git push --force-with-lease` — state this explicitly and get confirmation; it rewrites the remote branch (but still no foreign commit content changes).

## 5. The signing hook

`~/.local/bin/git-resign-own` (run by the global pre-push hook) signs only own unsigned commits via the selective `--exec` in step 4.5. It must NEVER use a blanket `git commit --amend -S` rebase (that signs foreign commits) and must pass `--no-gpg-sign` to the rebase. If it refuses or misbehaves, read it before editing; after editing, `bash -n` it and test with a no-op run.

## 6. Abort protocol

If at any point the plan grows (more conflicts than the 1-2 expected, tree diverging from intent, user says stop): abort in this order — `git rebase --abort`, `git cherry-pick --abort`, `git apply --abort` (whichever apply), `git reset --hard <restore-sha>`. Then `git status --short` and `git log --oneline -3` to prove clean. Report what was NOT done. Never leave a half-rebased tree for the user to discover.
