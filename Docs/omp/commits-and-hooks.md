# omp: commits, hooks, and vendored global tooling

Scope: making `omp commit` run global git hooks, and installing machine-wide tooling that survives checkout deletion.

## `omp commit` skips global git hooks — `commit` wrapper fix

**Symptom:** commits made with `omp commit` lack `Signed-off-by:` / `Co-authored-by:` trailers and skip the gitleaks pre-commit scan, although plain `git commit` gets them from global hooks (`core.hooksPath = ~/.config/git/hooks`).

**Cause:** `omp commit` does NOT call `git commit`. Verified by tracing argv with a PATH git shim: it runs `git commit-tree -S <tree> -p <parent>` then moves the ref natively. `commit-tree` runs no hooks (not even `reference-transaction`). Commits are still GPG-signed (`-S`). `omp commit` has no flag for hooks/trailers/signoff (flags: `--push`, `--dry-run`, `--no-changelog`, `--legacy`, `-c`, `-m`). The hook itself (`~/.config/git/hooks/prepare-commit-msg` appends `Signed-off-by` when `commit.gpgsign=true` and the key exists, `Co-authored-by` only when `OMPCODE=1` and `coauthor-hook.trailer` is set) is fine — don't debug it.

**Fix:** `~/.local/bin/commit` bash wrapper:

1. Record HEAD, run `omp commit "$@"` (exit on failure).
2. Skip the amend for `--dry-run`/`--help`; error if HEAD didn't move.
3. Run `env -u OMPCODE GIT_EDITOR=true git commit --amend --no-edit --quiet`. The amend DOES run hooks; the hook is idempotent (no duplicate trailers), and the amend re-signs the commit.
4. Reject `--push` (it would push before the amend rewrites the commit); user runs `git push` afterwards.

**Gotchas:**
- `env -u OMPCODE` is REQUIRED. `Co-authored-by` is wanted only when the agent runs `git commit` itself inside omp, never for the user's own `commit`. Inside an omp session `OMPCODE=1` is inherited, so without unsetting it the trailer leaks in.
- `omp commit --dry-run` output is ANSI/progress-noisy and shows `scope: null` as literal `chore(null)`; don't scrape it to feed `git commit -m` — amend instead.
- The amend's gitleaks scan sees an empty staged diff, so it does not scan what omp just committed.
- In a scratch repo verify: `commit` then `git log -1 --format=%B` shows exactly one `Signed-off-by`, zero `Co-authored-by` (even with `OMPCODE=1` set), and `%G?` is `G`. Control: plain `git commit -m x` with `OMPCODE=1` still gets both trailers.

_Migrated from: omp-commit-bypasses-git-hooks_

## Global tooling that survives checkout deletion — vendor into a data dir

**Symptom:** a repo installs machine-wide tooling (a `core.hooksPath` git hook, an omp/Claude extension symlinked into `~/.omp/agent/extensions` or `~/.claude/...`). It works until the user `rm -rf`s the repo — then every future `git commit` or `/slash-command` silently breaks (dangling symlink, hook exits nonzero).

**Cause:** the naive install symlinks straight into the checkout or hardcodes the checkout's absolute path.

**Fix pattern:**
1. Pick one data home: `~/.local/share/<project>/`, overridable via env var (`<PROJECT>_DATA_HOME`).
2. The installer (run once from inside the checkout) **vendors**: `cp -R` the implementation (scripts, extension `.ts`/`.js`) into that data home. Real copy, not a symlink.
3. Generated config (e.g. `~/.config/<project>/global-hooks.conf` sourced by the hook, or an env var the extension reads) points at the **data home**, never the checkout path.
4. Anything in a third-party-managed location (`core.hooksPath` dir, `~/.omp/agent/extensions/`) must be a **copy of the vendored file**, not a symlink into the checkout.
5. Uninstall scripts reference only `$HOME`-relative paths, never the checkout, so they work after the checkout is gone.
6. Re-running the installer re-vendors (`rm -rf` old dir, `cp -R` fresh) — that is the update mechanism, not `git pull`.

**Verification that proves it:** `mv` the checkout aside, then exercise the real behavior (run the vendored script directly, run an actual `git commit` through the hook) from a shell with a valid cwd — pass an explicit safe `cwd` like `/tmp`, because a bash tool's persistent shell with a stale cwd inside the moved dir fails every command with "working directory does not exist". Then move the checkout back.

_Migrated from: checkout-independent-global-tooling_

## Fully removing vendored global tooling (hook + extension + dotfiles)

**Symptom:** need to remove a machine-wide tool installed as `core.hooksPath` hook + `~/.omp/agent/extensions` file + vendored data dir, including dotfiles tracking.

**Procedure:**
1. **Scope first:** "remove X's hooks/extensions" means only X's files, not all hooks/extensions.
2. **Survey (read-only):** `git config --global core.hooksPath`; `ls -la` the hooks dir (a chained foreign hook exists as `pre-commit.pre-<tool>` — restore with `mv -f` over `pre-commit`, chmod +x, don't just delete); extension `~/.omp/agent/extensions/<tool>.ts` (+ `.bak`); data/config `~/.local/share/<tool>`, `~/.config/<tool>`; check source checkout `git status` clean and branch == origin; mentions via `grep -rIl -i '<tool>|<ENV_VAR>' ~/.config ~/.local/bin ~/.bashrc ~/.omp/agent/extensions ~/.omp/agent/managed-skills ~/.claude ~/.gitconfig` (do NOT grep `~/.local/share/omp/sessions`); `git --git-dir=$HOME/.dotfiles --work-tree=$HOME ls-files | grep -i <tool>`.
3. **Remove:** restore chained hook, delete extension/data/config/checkout (use `cwd=/tmp`); delete the tool's managed skills; edit other skills' stale mentions; delete `.bak` debris only after `cmp` shows IDENTICAL.
4. **Commit dotfiles:** `git add -u -- <explicit paths>` then `OMPCODE=1 git --git-dir=... -c commit.gpgsign=false commit` (unsigned to avoid fingerprint prompt; pre-push resigns). Never push unasked.
5. **Verify:** in a mktemp repo, the thing the old hook blocked now commits; a realistic fake secret (random `ghp_` + 36 chars, NOT AWS's documented EXAMPLE key which gitleaks allowlists) is still blocked by gitleaks. Re-grep just before finishing — autosync/survey processes may reintroduce mentions mid-task.

**Gotcha:** bash output can vanish when a script uses `${PIPESTATUS[0]}` with `grep -v` filtering, or ends on a failing `grep` under set-e-style chains. Write a throwaway script to /tmp, run `bash file`, then delete it.

_Migrated from: uninstall-vendored-global-tool-hook-extension-dotfiles_
