---
name: git-submodule-add-empty-repo-false-positive
description: "Use when git submodule add url path fails with \"You appear to have cloned an empty repository\" / \"You are on a branch yet to be born\" / \"unable to checkout submodule\" — before assuming the remote is truly empty, git fetch origin and check git branch -r / git log origin/main, since GitHub repos created with an auto-generated README can still trigger this false-positive if the clone raced or used a mismatched default branch name; also covers the recovery sequence (rm -rf the path AND .git/modules/path, then retry submodule add) and the trap of manually re-initializing+pushing a \"fix\" commit to what looks like an empty remote, which can produce a rejected non-fast-forward push if the remote actually already has history."
---

## Symptom

```
git submodule add <url> <path>
Cloning into '.../<path>'...
warning: You appear to have cloned an empty repository.
fatal: You are on a branch yet to be born
fatal: unable to checkout submodule '<path>'
```

## Do NOT immediately assume the remote is empty

Check the actual remote state before doing anything else:

```sh
cd <path>   # the partially-cloned dir git submodule add left behind
git fetch origin
git branch -r
git log origin/main --oneline   # or whatever the default branch is
```

If this shows real commits, the remote is NOT empty — the initial clone attempt
inside `git submodule add` just failed/raced, or hit a default-branch mismatch.

## Recovery

1. Clean up the failed partial state fully (both the working dir AND the
   registered submodule metadata git already wrote):
   ```sh
   rm -rf <path> .git/modules/<path>
   ```
2. Retry the plain command:
   ```sh
   git submodule add <url> <path>
   ```
   This now succeeds because the remote genuinely has content.

## Trap to avoid

Do not manually `git init` + create a placeholder commit + `git push` into
what you *think* is an empty remote as a "fix" — if the remote actually
already has commits (e.g. GitHub's own auto-created README), this push will
be rejected as non-fast-forward ("fetch first"), and you'll waste a round
trip discovering the remote wasn't empty after all. Just fetch/check first.
