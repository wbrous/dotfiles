---
name: git-prepush-resign-unpushed-unsigned
description: "Use when setting up or debugging the global pre-push hook that GPG-resigns unpushed unsigned commits before push, or the one-command dotfiles-push wrapper — covers the fundamental pre-push limitation (cannot complete a push in one command; stale-SHA \"remote rejected\" error even though the re-invoked push lands), the GIT_PRE_PUSH_RESIGNED re-entry guard, the dotfiles() function routing push through ~/.local/bin/dotfiles-push, unsigned-detection via git cat-file gpgsig header (not %G?), per-commit counting, gpg-agent default-cache-ttl 300 for single-fingerprint batches, the dev-time unsigned vs push-time signed split (commit.gpgsign=false on ~/.dotfiles), and headless testing with a throwaway no-passphrase GPG key."
---

# Pre-push GPG resign of unpushed unsigned commits — hook + one-command wrapper

Split dev-time signing from push-time signing: managed-skill auto-commits and dotfiles survey commits are deliberately UNSIGNED locally (`commit.gpgsign=false` set on the ~/.dotfiles bare repo), so no fingerprint prompt fires while the user may be away. At push time the user IS present, so unpushed unsigned commits get GPG-signed before they leave the machine. Already-pushed commits are NEVER rewritten.

## Architecture on this machine (2026-08)

- `~/.dotfiles` bare repo, alias `dotfiles='git --git-dir=$HOME/.dotfiles/ --work-tree=$HOME'`; remote `origin` → github.com/wbrous/dotfiles.git, upstream `origin/main`.
- `~/.config/git/hooks/pre-push` — global (core.hooksPath = ~/.config/git/hooks): resign-then-abort safety net for any repo pushed with plain `git push`.
- `~/.local/bin/dotfiles-push` — ONE-COMMAND wrapper: resign then exec the real push (the flow the user actually wants).
- `.bashrc` — `dotfiles` is now a FUNCTION, not an alias:
  ```sh
  dotfiles() {
      if [ "${1:-}" = "push" ]; then
          shift 1
          command dotfiles-push "$@"
      else
          git --git-dir="$HOME/.dotfiles/" --work-tree="$HOME" "$@"
      fi
  }
  ```
- `gpg-agent.conf`: `default-cache-ttl 300` / `max-cache-ttl 300` (WAS 0). One fingerprint scan caches the passphrase ~5 min so a batch of amend-signs prompts ONCE. File is root:root 644 — edits need sudo; gpg-agent reads it only at startup → `systemctl --user restart gpg-agent.service` after changing. NOTE the printf-escaping trap when writing it via sudo sh -c (use a `<<'EOF'` heredoc instead).

## CRITICAL: why pre-push cannot push in one command (empirically verified)

Git's pre-push hook runs AFTER the refs-to-send are resolved. If the hook re-signs (rewrites) the commits and then re-invokes the push with a guard, the NESTED push succeeds (remote gets the signed commit) BUT the outer git then retries with its STALE pre-rebase SHA → `! [remote rejected] ... incorrect old value provided` / exit 1. The user sees "failed to push" even though the push landed. **There is no way to make pre-push complete a push cleanly in one command.** Hence the wrapper.

## One-command flow: `dotfiles push` (the wrapper, ~/.local/bin/dotfiles-push)

```sh
branch=$(git --git-dir=... --work-tree=... rev-parse --abbrev-ref HEAD)
base="$(... rev-parse --abbrev-ref --symbolic-full-name @{upstream})"   # e.g. origin/main
base="${base#refs/remotes/}"
unpushed="$(... rev-list "$base"..HEAD)"
# unsigned = commit object has NO `gpgsig` header:
for sha in $unpushed; do
  git ... cat-file -p "$sha" | grep -q '^gpgsig' || to_sign="$to_sign $sha"
done
if [ -n "$to_sign" ]; then
  git ... rebase --rebase-merges --exec 'git commit --amend --no-edit -S' "$base"
  # one fingerprint scan; ttl=300 covers the batch
fi
export GIT_PRE_PUSH_RESIGNED=1   # ← CRITICAL: global pre-push hook exits immediately (re-entry guard)
exec git --git-dir=... --work-tree=... push "$@"   # exact args preserved (--force, -u, ...)
```

`export GIT_PRE_PUSH_RESIGNED=1` before the exec push is what stops the global pre-push hook from re-scanning/aborting during the wrapper's push. Without it the nested push gets aborted by the hook.

## Unsigned detection: `git cat-file -p <sha> | grep -q '^gpgsig'`, NOT `git log %G?`

`%G?` returns `E` (can't verify — missing/unknown key) for a signed commit when that key isn't present, which would wrongly skip it. A commit is unsigned iff its object has no `gpgsig` header.

## Pre-push hook (safety net) — key details

- Input: stdin lines `<local-ref> <local-oid> <remote-ref> <remote-oid>`; argv[1]=remote name, argv[2]=remote url.
- All-zeros remote-oid = brand-new branch → resign from `--root`.
- Count COMMITS (NCOMMITS from the unsigned list), not refs — counting refs under-reports (pushed 2 commits on 1 ref but hook said "re-signed 1").
- After resigning: EXIT 1 + "re-run the push command" message (two-step flow, only for non-dotfiles repos).
- Re-entry guard at top: `[ "${GIT_PRE_PUSH_RESIGNED:-}" = "1" ] && exit 0`.
- gitleaks pre-commit fires per amend (global hook) — normal, passes for SKILL.md content.

## Testing headless (no fingerprint needed)

Throwaway no-passphrase key in isolated GNUPGHOME:
```sh
rm -rf /tmp/gnupg && mkdir -p /tmp/gnupg && chmod 700 /tmp/gnupg && export GNUPGHOME=/tmp/gnupg
cat > /tmp/kp <<'EOF'
%no-protection
Key-Type: eddsa
Key-Curve: ed25519
Key-Usage: sign
Name-Real: T
Name-Email: t@t.t
Expire-Date: 0
%commit
EOF
gpg --batch --generate-key /tmp/kp
FP=$(gpg --list-secret-keys --with-colons | awk -F: '/^fpr/{print $10; exit}')
git config user.signingkey "$FP"
```
Scratch-topology gotcha: a bare "dotfiles" repo + separate bare remote + work-tree must be set up so `@{upstream}` actually resolves (fetch + `branch.<name>.remote/merge`) BEFORE testing the wrapper, else it silently skips resigning and just pushes. Use a sed-modified copy of dotfiles-push pointing DOT_GIT_DIR/DOT_WORK_TREE at the scratch paths.

## Gotchas

- The wrapper resolves `@{upstream}`; if upstream resolution FAILS it currently silently pushes unsigned (`base=""` → empty unpushed → "nothing to re-sign"). Acceptable for first push of a new branch, but a latent footgun — guard if it matters.
- gitleaks global pre-commit runs on every amend during resign — expected noise.
- `Signed-off-by` trailer (prepare-commit-msg hook) is gated on commit.gpgsign=true; dotfiles repo has it false → no signoff trailer on dotfiles commits, only Co-authored-by (OMPCODE=1).
