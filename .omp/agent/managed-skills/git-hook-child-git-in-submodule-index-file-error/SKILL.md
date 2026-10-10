---
name: git-hook-child-git-in-submodule-index-file-error
description: "A git hook (pre-commit etc.) that runs git -C submodule ... fails with \"index file open failed: Not a directory\" or hangs the commit; also how to test hooks against a real submodule."
---

## Symptom
A repo hook calls `git -C apps/x/sub status` (or any git in a submodule). During `git commit` it dies with
`fatal: .git/index: index file open failed: Not a directory`. Run by hand it works.

## Cause
Git exports repo-describing variables to hooks, notably `GIT_INDEX_FILE=.git/index` (relative). A child git inherits it. In a submodule `.git` is a FILE (`gitdir: ...`), so `.git/index` is not a path.

## Fix
Scrub the vars for that call only:
`env -u GIT_INDEX_FILE -u GIT_DIR -u GIT_WORK_TREE -u GIT_PREFIX git -C <submodule> status --porcelain -- <path>`

## Testing a hook
A nested plain repo hides this bug (its `.git` is a directory). Test in a throwaway repo with a REAL submodule (`git submodule add <bare.git>`, assert `[ -f sub/.git ]`). Make it hermetic: `GIT_CONFIG_GLOBAL` temp file with `commit.gpgsign=false`, `protocol.file.allow=always`, `GIT_CONFIG_SYSTEM=/dev/null`, and wrap runs in `timeout` — an unsigned/blocked commit otherwise waits on gpg/fingerprint and hangs the tool. Prove the test by reverting the fix and confirming it fails with the real error.

## Related
- A repo-local `core.hooksPath` replaces the global one; chain to the global pre-commit from the local hook.
- Committing with fingerprint GPG: use a PTY bash call and `git commit -F file`; see skill git-commit-gpg-fingerprint-timeout-retry.
- A hook cannot include changes made inside a submodule; have it block and print the 3 commands (add+commit in submodule, `git add <submodule>`).
