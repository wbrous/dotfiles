# Hooks, global config, and worktrees

Global `core.hooksPath`, per-repo hooks, XDG isolation, submodule hook env, and vendoring tools so they survive checkout deletion.

## Global hooks dir and sharing it safely

**Symptom:** setting `git config --global core.hooksPath` replaces `.git/hooks` for every repo that doesn't set its own — can shadow husky/`.pre-commit-config.yaml` or an existing gitleaks hook.

**Fix:** before installing, check for existing managers:
```sh
find <dev-root> -maxdepth 2 -iname ".husky" -o -maxdepth 3 -iname ".pre-commit-config.yaml"
```
If a `pre-commit` already exists without your marker comment, `mv` it aside to `pre-commit.pre-<yourtool>` and have your hook `exec`/chain to it when executable. On idempotent reinstall (your marker present) overwrite in place. On uninstall, restore the chained hook and only `--unset core.hooksPath` if the managed dir is now empty. Test with a fake foreign hook: install, confirm both outputs fire, uninstall, confirm byte-for-byte restore.

_Migrated from: git-global-hooks-and-omp-command-vendoring_

## Vendor tools into a data home, never reference the checkout

**Symptom:** a repo ships a tool + installer wiring a global hook or agent extension, then breaks when the user `rm -rf`s the checkout.

**Fix:** `cp -R` (not symlink) the runtime into `~/.local/share/<tool>/` on every install (idempotent: `rm -rf` destination subtree first); both hook and extension read a config file (`~/.config/<tool>/global-hooks.conf` with `TOOL_HOME=...`), never a checkout path. Copy the hook script and extension file into their install targets too, vendor installer/uninstaller into `$DATA_HOME/bin/` plus a `.vendor-info` file, and verify independence by `mv`-ing the checkout aside and re-running.

_Migrated from: git-global-hooks-and-omp-command-vendoring_

## Diff-corruption pre-commit guard

**Symptom:** a bad patch leaves old+new lines both in place (duplicate back-to-back `if (...)` openers sharing one body, exact-duplicate adjacent added lines) or unresolved `<<<<<<<`/`=======`/`>>>>>>>` markers — and the commit lands.

**Fix:** install the reusable guard `~/.local/share/git-hooks/pre-commit-diff-corruption-guard` (symlinked as `pre-commit`) scanning `git diff --cached --unified=0` added lines for: adjacent near-duplicate control openers (`if`/`for`/`while`/`switch`/`catch`/`else if`), exact-duplicate adjacent added lines, merge markers. Filename parsing handles `a/`/`b/` and mnemonic (`c/`/`i/`/`w/`/`o/`) prefixes. Global: `git config --global core.hooksPath ~/.local/share/git-hooks` (check for hook managers first, above). Per-repo: copy into `.githooks/pre-commit`, `chmod +x`, `git config core.hooksPath .githooks`. Bypass: `git commit --no-verify`. Verify with a real `git commit` in a throwaway repo asserting exit 1, not just running the script.

_Migrated from: git-diff-corruption-precommit-hook_

## Diagnosing committed diff corruption after the fact

**Symptom:** `git show --stat` says "4 ++--" but the diff looks garbled, or `tsc` fails right after a "clean 2-line change" — the file contains both old and new lines stacked (e.g. two `if (choice?.finish_reason ...)` lines sharing one `{`/body).

**Fix:** `git show --stat HEAD`, `git show HEAD` (distrust the hunk view if it smells wrong), `read` the real file at the changed range ±10 lines, delete the stale line per duplicated pair, re-run `tsc --no-emit` (or equivalent).

_Migrated from: git-diff-duplicate-if-corruption_

## Isolating `git config --global` in tests (XDG trap)

**Symptom:** a test harness setting `HOME=$(mktemp -d)` still mutates the real `~/.config/git/config` (e.g. `core.hooksPath` → deleted tmp dir, breaking hooks machine-wide).

**Cause:** global scope is NOT only `$HOME/.gitconfig` — git also reads `$XDG_CONFIG_HOME/git/config`. Reassigning `HOME` alone leaves `XDG_CONFIG_HOME` pointing at the real config.

**Fix:**
```sh
export HOME=$(mktemp -d)
export XDG_CONFIG_HOME="$HOME/.config"
```
Most bulletproof: `GIT_CONFIG_GLOBAL=$(mktemp)` to pin global scope at an explicit throwaway file. Recovery: `git config --global --show-origin --get core.hooksPath` to see what leaked, restore or re-run the installer's uninstall path.

_Migrated from: git-config-xdg-config-home-not-isolated-by-home_

## Hooks calling git inside a submodule

**Symptom:** a hook running `git -C apps/x/sub status` dies with `fatal: .git/index: index file open failed: Not a directory`; by hand it works.

**Cause:** git exports `GIT_INDEX_FILE=.git/index` (relative) to hooks; in a submodule `.git` is a *file* (`gitdir: ...`), so `.git/index` is not a path.

**Fix:** scrub the vars for that call only:
```sh
env -u GIT_INDEX_FILE -u GIT_DIR -u GIT_WORK_TREE -u GIT_PREFIX git -C <submodule> status --porcelain -- <path>
```
Test in a throwaway repo with a REAL submodule (`git submodule add <bare.git>`, assert `[ -f sub/.git]` — nested plain repos hide this). Hermetic test env: `GIT_CONFIG_GLOBAL` temp file with `commit.gpgsign=false`, `protocol.file.allow=always`, `GIT_CONFIG_SYSTEM=/dev/null`, wrapped in `timeout`. A hook cannot include changes made inside a submodule — have it block and print the 3 commands (add+commit in submodule, `git add <submodule>`).

_Migrated from: git-hook-child-git-in-submodule-index-file-error_

## Scoped co-author trailers + global signoff trailer

**Goal:** auto-append `Co-authored-by:` in specific project folders or repos owned by a remote account, only for agent-driven commits — plus a global `Signed-off-by:` whenever the commit will actually be GPG-signed.

**Fix:** one shared `prepare-commit-msg` hook under `~/.config/git/hooks/`, `core.hooksPath = ~/.config/git/hooks` at the top of `~/.config/git/config` (never `~/.gitconfig`). Co-author scope via `includeIf`: `[includeIf "gitdir:PATTERN"]` for folders, `[includeIf "hasconfig:remote.*.url:**/owner/**"]` (git 2.36+) for remote owners — each scope file sets only `coauthor-hook.trailer`; the hook appends only when non-empty AND `OMPCODE=1`. Signoff gate: `commit.gpgsign=true` + `user.signingkey` present + `gpg --list-secret-keys` shows `^sec`. Both trailers go through one shared `append_trailer()` helper so exactly one blank line separates the body from the trailer block, none between trailers. Verify with the fakebin/`cat -A` procedure (expect exactly one blank line before the block). `Signed-off-by:` is plaintext, not cryptographic proof — say so. Root-lock optional: `sudo chown root:root`, 755 scripts / 644 configs; to update, write to scratch then `sudo cp` over.

_Migrated from: git-scoped-coauthor-trailer_

## Safe merge recipe on shared branches (never rewrite foreign commits)

**Invariants:** never rewrite another author's commits (hashes byte-identical); sign only `user.email` commits; every destructive step needs a recorded restore point (`git rev-parse HEAD` + `git log --oneline origin/<branch> -2`; undo via `git reset --hard <restore>` + `--force-with-lease`).

**Fix:** survey read-only first (`git log --format='%h %ae %G? %ad %s'`, `git status -sb`, `git branch -r --contains <sha>`, `git stash list` — dirty tree or stashes means stop). Prefer `git config pull.rebase true` so own commits replay on top instead of burying under merges. Recipe: `git reset --hard <foreign-tip>`, `git cherry-pick --no-gpg-sign <own-shas...>` in order (`--allow-empty` with `Original-date:` trailer or `--skip` if empty), sign only own via the selective `--exec` resign (see push-signing.md), verify foreign SHAs identical and own `G`, push (`--force-with-lease` only with confirmation if the remote already has a buried order). Abort order: `git rebase --abort`, `git cherry-pick --abort`, `git apply --abort`, `git reset --hard <restore>`.

_Migrated from: shared-branch-merge-handling_
