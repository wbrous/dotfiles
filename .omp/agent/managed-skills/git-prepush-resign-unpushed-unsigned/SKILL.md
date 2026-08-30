---
name: git-prepush-resign-unpushed-unsigned
description: "Use when setting up or debugging the global pre-push hook that GPG-resigns unpushed unsigned commits before push, or the one-command git push/dotfiles push flow — covers the fundamental pre-push limitation (a hook alone cannot complete a push in one command; stale-SHA \"remote rejected\" error even though the re-invoked push lands), the GIT_PRE_PUSH_RESIGNED re-entry guard, the shell-level git() function routing every git push through ~/.local/bin/git-push-resign (generic, any repo) and dotfiles() routing through the same script via GIT_DIR/GIT_WORK_TREE, gpg-agent default-cache-ttl 300 for single-fingerprint batches, the dev-time unsigned vs push-time signed split (commit.gpgsign=false on ~/.dotfiles), the new-branch/no-upstream footgun where resigning is silently skipped, headless testing with a throwaway no-passphrase GPG key, and which pieces of this setup are dotfiles-synced vs machine-local when cloning onto a new machine."
---

# Pre-push GPG resign of unpushed unsigned commits — one-command `git push` for every repo

Split dev-time signing from push-time signing: managed-skill auto-commits and dotfiles survey commits are deliberately UNSIGNED locally (`commit.gpgsign=false` set on the ~/.dotfiles bare repo), so no fingerprint prompt fires while the user may be away. At push time the user IS present, so unpushed unsigned commits get GPG-signed before they leave the machine. Already-pushed commits are NEVER rewritten.

## Architecture (2026-08, current)

- `~/.config/git/hooks/pre-push` — global (core.hooksPath = ~/.config/git/hooks) safety net: resign-then-abort for any push that bypasses the shell wrapper below (other shells, IDEs, scripts, cron).
- `~/.local/bin/git-push-resign` — the ONE-COMMAND engine. Generic: works against whatever repo the caller's `git rev-parse`/`GIT_DIR` resolves to, not hardcoded to dotfiles. Resigns unpushed unsigned commits on the current branch's `@{upstream}` range, then `exec`s the real `git push "$@"`.
- `~/.bashrc`:
  ```sh
  # Shadows the real git — EVERY `git push` in an interactive shell goes
  # through the resign step first, so it never hits the hook's abort path.
  git() {
      if [ "${1:-}" = "push" ]; then
          shift 1
          command git-push-resign "$@"
      else
          command git "$@"
      fi
  }

  # dotfiles bare-repo alias reuses the same engine via GIT_DIR/GIT_WORK_TREE
  # instead of duplicating the resign logic.
  dotfiles() {
      if [ "${1:-}" = "push" ]; then
          shift 1
          GIT_DIR="$HOME/.dotfiles" GIT_WORK_TREE="$HOME" command git-push-resign "$@"
      else
          git --git-dir="$HOME/.dotfiles/" --work-tree="$HOME" "$@"
      fi
  }
  ```
- `gpg-agent.conf`: `default-cache-ttl 300` / `max-cache-ttl 300` (WAS 0). One fingerprint scan caches the passphrase ~5 min so a batch of amend-signs prompts ONCE. File is root:root 644 — edits need sudo; gpg-agent reads it only at startup → `systemctl --user restart gpg-agent.service` after changing. NOTE the printf-escaping trap when writing it via sudo sh -c (use a `<<'EOF'` heredoc instead).

Previously there was a dotfiles-only `~/.local/bin/dotfiles-push` script and a plain `git push` from any other repo hit the hook's abort-and-ask-to-rerun path. Both are gone: `git-push-resign` is the single generic engine, and the `git()` shell function makes EVERY interactive `git push` one-command, not just dotfiles. `dotfiles-push` was deleted.

## What's dotfiles-synced vs machine-local (matters when cloning onto a new machine)

Dotfiles-tracked (restored automatically on clone):
- `~/.bashrc` → the `git()`/`dotfiles()` functions.
- `~/.config/git/config` → `core.hooksPath`, `[coauthor-hook]` trailer setting, `commit.gpgsign = true`.
- `~/.config/git/hooks/{pre-push,pre-commit,pre-commit.pre-watermarks-remover,prepare-commit-msg}` → gitleaks scan, resign-safety-net, coauthor trailer injection.
- `~/.local/bin/git-push-resign` → the resign engine itself (added 2026-08-29, commit 942dc01).

NOT dotfiles-tracked (must be redone by hand on a fresh machine, or accepted as a gap):
- `~/.gnupg/gpg-agent.conf` — root:root owned, outside `$HOME`'s git-visible ownership boundary, holds the `default-cache-ttl 300` tweak. A fresh machine gets gpg-agent's default `ttl 0` (fingerprint prompt per amend-sign in a resign batch) until this is redone.
- The rest of `~/.local/bin` (mise/tool shims like `gh`, `claude`, `python3.11`, `pi`, `omp`, etc.) is intentionally left untracked — only hand-written scripts like `git-push-resign` get added, not vendor-managed shims.
- `~/.local/bin` on `PATH` is handled by the tracked `.bashrc`/omarchy rc (`export PATH="$HOME/.local/bin:$PATH"`), so that part IS automatic.

## CRITICAL: why the pre-push hook alone cannot push in one command (empirically verified)

Git's pre-push hook runs AFTER the refs-to-send are resolved by the outer `git push` process. If the hook rewrites the commits (new SHAs from re-signing) and exits 0, the OUTER git still sends the stale pre-rebase SHA it already resolved before the hook ran. The remote then either rejects it as non-fast-forward (that stale commit is not a descendant of the now-pushed resigned commit) or the outer send races/duplicates the hook's own push. **There is no way to make the hook complete a push cleanly in one command by itself.** The only fix is to do the resign BEFORE `git push` is even invoked — i.e. in the calling shell, not in a hook. Hence `git-push-resign` + the `git()` function.

## One-command flow: any `git push` (via the `git()` shell function → `git-push-resign`)

```sh
branch="$(git rev-parse --abbrev-ref HEAD)"                      # bail (plain push) if detached/no branch
base="$(git rev-parse --abbrev-ref --symbolic-full-name @{upstream})"  # e.g. origin/main
base="${base#refs/remotes/}"
unpushed="$(git rev-list "$base"..HEAD)"
# unsigned = commit object has NO `gpgsig` header:
for sha in $unpushed; do
  git cat-file -p "$sha" | grep -q '^gpgsig' || to_sign="$to_sign $sha"
done
if [ -n "$to_sign" ]; then
  git rebase --rebase-merges --exec 'git commit --amend --no-edit -S' "$base"
  # one fingerprint scan; ttl=300 covers the batch
fi
export GIT_PRE_PUSH_RESIGNED=1   # ← CRITICAL: global pre-push hook exits immediately (re-entry guard)
exec git push "$@"               # exact args preserved (--force, -u, ...); GIT_DIR/GIT_WORK_TREE inherited from env
```

`export GIT_PRE_PUSH_RESIGNED=1` before the exec push is what stops the global pre-push hook from re-scanning/aborting during the wrapper's push. Without it the nested push gets aborted by the hook.

`dotfiles push` sets `GIT_DIR`/`GIT_WORK_TREE` env vars before calling the same script — plain `git` commands (`rev-parse`, `rev-list`, `cat-file`, `rebase`, `push`) all honor those envs identically to `--git-dir`/`--work-tree` flags, so no logic duplication is needed.

## Unsigned detection: `git cat-file -p <sha> | grep -q '^gpgsig'`, NOT `git log %G?`

`%G?` returns `E` (can't verify — missing/unknown key) for a signed commit when that key isn't present, which would wrongly skip it. A commit is unsigned iff its object has no `gpgsig` header.

## Pre-push hook (safety net) — key details

- Input: stdin lines `<local-ref> <local-oid> <remote-ref> <remote-oid>`; argv[1]=remote name, argv[2]=remote url.
- All-zeros remote-oid = brand-new branch → resign from `--root`.
- Count COMMITS (NCOMMITS from the unsigned list), not refs — counting refs under-reports (pushed 2 commits on 1 ref but hook said "re-signed 1").
- After resigning: EXIT 1 + "re-run the push command" message. This ONLY fires when a push bypasses the shell `git()` function (e.g. a non-interactive shell, IDE git integration, or script that calls the real `git` binary directly) — normal interactive terminal use never sees it anymore.
- Re-entry guard at top: `[ "${GIT_PRE_PUSH_RESIGNED:-}" = "1" ] && exit 0`.
- gitleaks pre-commit fires per amend (global hook) — normal, passes for SKILL.md content.

## Known footgun: brand-new branch / no upstream yet silently skips resigning

`git-push-resign` resolves `@{upstream}` to compute the unpushed range. On the FIRST push of a new branch (no upstream configured yet), `@{upstream}` resolution fails, `base` is empty, `to_sign` stays empty, and the script just execs `git push "$@"` with commits unsigned — no error, no warning. Verified empirically: pushing a brand-new branch with 2 unsigned commits landed both as `%G? = N` (no signature) on the remote. The *second* push onto that now-tracked branch resigns correctly. Acceptable for the common case (dotfiles/managed-skill commits get resigned on the next push regardless), but a real gap if the first-ever push of a branch must land signed — guard explicitly (e.g. fall back to `--set-upstream`'s target ref name and diff against the remote's already-known tip) if that case matters.

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
To test `git-push-resign` itself (not the `git()` shell function, which only exists in an interactive bash with `.bashrc` sourced): `cd` into a scratch repo with a real remote and `@{upstream}` set (push once with `-u` first, since the new-branch footgun above means the first push won't exercise resigning), add an unsigned commit, then invoke `git-push-resign` directly with `~/.local/bin` on `PATH` — bash tool sessions are non-interactive and do NOT have the `git()`/`dotfiles()` functions, so calling plain `git push` in one will hit the raw hook's abort path, not the wrapper.

## Gotchas

- gitleaks global pre-commit runs on every amend during resign — expected noise.
- `Signed-off-by` trailer (prepare-commit-msg hook) is gated on commit.gpgsign=true; dotfiles repo has it false → no signoff trailer on dotfiles commits, only Co-authored-by (OMPCODE=1).
- `command git-push-resign` / `command git` inside the `git()`/`dotfiles()` functions is required to avoid infinite recursion into the function itself when the function's own body needs to run the real git or the wrapper script.
