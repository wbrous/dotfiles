---
name: git-diff-corruption-precommit-hook
description: "Use when the user wants to prevent corrupted-diff commits (old+new lines both left in place, e.g. duplicate back-to-back if (...) openers, or unresolved merge-conflict markers) from landing — installs/references the reusable pre-commit hook at ~/.local/share/git-hooks/pre-commit-diff-corruption-guard, either globally via git config --global core.hooksPath or per-repo via .githooks/."
---

## What

A Python pre-commit hook (`~/.local/share/git-hooks/pre-commit-diff-corruption-guard`,
symlinked as `~/.local/share/git-hooks/pre-commit`) that scans ADDED lines in
`git diff --cached --unified=0` and blocks the commit when it finds:

1. Two adjacent added lines that are near-duplicate control-statement openers
   with the same leading keyword (`if`/`for`/`while`/`switch`/`catch`/`else if`)
   — the signature of a bad patch application that left the old condition line
   in place instead of replacing it with the new one (e.g. two `if (...)  {`
   lines sharing one body — invalid syntax).
2. Exact duplicate adjacent added lines (same "old+new both landed" corruption
   for non-control-flow lines).
3. Unresolved merge-conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`) in staged
   content.

Filename parsing handles both standard (`a/`/`b/`) and mnemonic (`c/`/`i/`/`w/`/`o/`)
diff prefixes — don't hardcode `+++ b/`, some git configs use `diff.mnemonicPrefix`.

## Global install (all repos, current + future)

```
git config --global core.hooksPath ~/.local/share/git-hooks
```

Caveat: this REPLACES the default `.git/hooks` dir for every repo that doesn't
set its own `core.hooksPath`. Before doing this, check for existing hook
managers (husky `.husky/`, `pre-commit` `.pre-commit-config.yaml`) that would
get shadowed:

```
find <dev-root> -maxdepth 2 -iname ".husky" -o -maxdepth 3 -iname ".pre-commit-config.yaml"
```

If none found, global install is safe. If found, prefer the per-repo route
below for those specific repos, or integrate the guard's logic into the
existing hook manager instead.

## Per-repo install (git-tracked, doesn't touch global config)

```
mkdir -p .githooks
cp ~/.local/share/git-hooks/pre-commit-diff-corruption-guard .githooks/pre-commit
chmod +x .githooks/pre-commit
git config core.hooksPath .githooks
```

## Bypass

`git commit --no-verify` for confirmed false positives (e.g. legitimately
nested same-keyword conditionals — rare but possible).

## Verifying it's wired up correctly

Don't just run the script manually — prove it fires via a real `git commit` in
a throwaway repo:

```
tmp=$(mktemp -d) && cd "$tmp" && git init -q
git config user.email t@t.com; git config user.name t
git config core.hooksPath ~/.local/share/git-hooks   # or .githooks for per-repo
# ... commit a baseline file, then stage a corrupted version, then:
git commit -m "bad"   # should exit 1 and print the BLOCKED message
rm -rf "$tmp"
```

## Related

See `git-diff-duplicate-if-corruption` skill for the manual diagnosis/fix
procedure when this pattern is discovered after the fact (already committed).
This hook prevents it before commit; that skill fixes it after.
