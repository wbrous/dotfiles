---
name: dotfiles-bare-repo-gitleaks-hook
description: "Use when setting up a public dotfiles git repo via the bare-repo + worktree trick (git --git-dir=$HOME/.dotfiles --work-tree=$HOME), or wiring a gitleaks pre-commit hook for it — covers the status.showUntrackedFiles trick to avoid tracking every file, the modern gitleaks CLI (protect deprecated; use git diff --staged | gitleaks stdin), the core.hooksPath global-config collision that silently disables repo-local hooks, wiring gitleaks as a new file inside an existing global hooks dir instead of overriding hooksPath (preserves other global hooks like a prepare-commit-msg signoff/co-author trailer), a GIT_ALLOW_SECRETS=1 deliberate-bypass env var, and the gotcha that prepare-commit-msg hooks are silent (test by reading the actual commit message body, not console output)."
---

## Bare repo setup
```bash
git init --bare $HOME/.dotfiles
alias dotfiles='git --git-dir=$HOME/.dotfiles/ --work-tree=$HOME'
dotfiles config --local status.showUntrackedFiles no
```
`status.showUntrackedFiles no` = only explicitly `dotfiles add <path>`ed files ever show up in `status`/get committed. This is the real safety mechanism against "track 999999 files" — not `.gitignore` maintenance, deliberate one-file-at-a-time `add`.

Add files one at a time, review each for secrets before adding (`grep -riE 'token|secret|key|password' <file>`), never `add -A` / `add .`.

## gitleaks CLI: `protect` deprecated
Modern gitleaks (v8.20+) only has `dir`/`git`/`stdin` subcommands. `gitleaks protect --staged` may still run but is unreliable/removed depending on version — don't rely on it. Use:
```bash
git diff --staged | gitleaks stdin --redact -v
```
This also sidesteps custom `GIT_DIR`/`GIT_WORK_TREE` env vars breaking gitleaks' own internal git invocation (symptom: `error: unknown option 'staged'` fed into a plain `git diff --no-index` usage dump — gitleaks shelled out to git wrong under custom env).

## CRITICAL gotcha: `core.hooksPath` is global and NOT additive
If the user already has `core.hooksPath` set unconditionally in `~/.config/git/config` (e.g. for a `prepare-commit-msg` hook adding Signed-off-by/co-author trailers — see `git-scoped-coauthor-trailer` skill), that path applies to **every** repo including a new bare dotfiles repo. Setting a **local** `core.hooksPath` override on the dotfiles repo to point at its own `hooks/` dir will silently **kill** the global hook for that repo — it's a full replacement, not additive, since it's a single-value config key.

**Correct fix: don't override hooksPath at all.** Add gitleaks as a NEW file (`pre-commit`) directly inside the *existing* global hooks dir (e.g. `~/.config/git/hooks/pre-commit`), alongside whatever's already there (`prepare-commit-msg` etc.) — different hook name, no collision, no permission conflict even if the existing hook file is root-locked.

By default this scans **every** repo's staged diff pre-commit, which is usually what you actually want for secret-leak protection generally. Add a deliberate bypass:
```sh
#!/bin/sh
if [ "${GIT_ALLOW_SECRETS:-}" = "1" ]; then
  echo "GIT_ALLOW_SECRETS=1 set — skipping gitleaks scan."
  exit 0
fi
git diff --staged | gitleaks stdin --redact -v
if [ $? -ne 0 ]; then
  echo "gitleaks found secret. commit blocked. (bypass: GIT_ALLOW_SECRETS=1 git commit ...)"
  exit 1
fi
exit 0
```
`chmod +x`. Usage to intentionally commit something gitleaks false-positives on: `GIT_ALLOW_SECRETS=1 git commit -m "..."`.

(If truly need per-repo scoping instead of global scanning, add a `GIT_DIR_ABS` check inside the script comparing `git rev-parse --git-dir` resolved to an absolute path, rather than touching `hooksPath`.)

## Testing gotcha: `prepare-commit-msg` hooks are silent
`prepare-commit-msg` edits the commit message file directly — it prints nothing to console on success. Don't verify "did the global hook still fire" by eyeballing command output (that only proves whatever hook *did* run, e.g. gitleaks' banner) — read the actual commit body:
```bash
git log -1 --format=%B
```
A false "still works" conclusion from absence-of-console-noise is a real trap — verify by content, not silence.

## Verification matrix (run for real, don't assume)
1. Fake-secret file, correctly shaped (e.g. `AKIA` + 16 alnum for AWS — AWS's own placeholder example `AKIAIOSFODNN7EXAMPLE` is allowlisted by gitleaks and gives a false negative if reused verbatim) → commit should be blocked, exit nonzero, `git log` unchanged.
2. Clean file → commit succeeds, `git log -1 --format=%B` shows the expected trailer(s) intact.
3. Bypass env var → commit succeeds even with the fake secret present.
4. A different, unrelated repo (`mkdir -p /tmp/x && git init`) → confirm global-hooks-dir hooks (trailer, gitleaks if globally scoped) still apply there too, and any repo-scoping logic behaves as designed.
Clean up test repos (`rm -rf`) and unstage/reset any test commits after.
