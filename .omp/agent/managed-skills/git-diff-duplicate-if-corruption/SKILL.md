---
name: git-diff-duplicate-if-corruption
description: "Use when a git commit's diff for a TS/JS file shows old and new lines both present without removal markers (e.g. two if (...) lines back to back before one { block), or tsc/build fails right after a commit that \"should\" be a clean 2-line change — a corrupted/malformed diff left both old and new source lines in the file, breaking syntax."
---

## Symptom

`git show`/`git diff` for a commit displays garbled hunks: e.g. stat says "4 ++--" but the printed diff shows lines out of order, or the actual file on disk (checked via `read`) contains BOTH the old line and the new line stacked back to back — e.g.:

```ts
if (choice?.finish_reason === 'length') {
if (choice?.finish_reason?.toLowerCase() === 'length') {
  return null;
}
```

This is invalid syntax (two `if` statements sharing one `{`/body) and will fail `tsc --noEmit`.

## Root cause

The diff/patch application (or a bad manual edit) left the pre-edit line in place instead of replacing it — both old and new revisions of a line ended up committed together.

## Fix procedure

1. `git show --stat HEAD` to see which file(s) changed and how many lines.
2. `git show HEAD` — if the printed diff looks structurally odd (mismatched +/- context, duplicate-looking lines), don't trust it at a glance.
3. `read` the actual file at the changed line range (use the stat's line numbers ±10 for context).
4. Visually confirm: is there a duplicate pair of near-identical lines (old wording immediately followed by new wording, or vice versa) right before a shared closing brace?
5. If yes: use `edit` to delete the stale (old) line, keeping only the new one. Do this for every duplicated pair in the diff.
6. Re-run `tsc --noEmit -p .` (or the project's equivalent) in the affected package to confirm it now compiles clean.

## Notes
- Don't assume `git diff`'s pretty-printed hunk view is trustworthy when something already smells wrong — go read the real file content directly.
- This is a good first check whenever asked to "check the latest diff, someone messed it up."
