---
name: dotfiles-bare-repo-gitleaks-hook
description: "Use when setting up a public dotfiles git repo via the bare-repo + worktree trick (git --git-dir=$HOME/.dotfiles --work-tree=$HOME), or wiring a gitleaks pre-commit hook for it — covers the status.showUntrackedFiles trick to avoid tracking every file, the modern gitleaks CLI (protect deprecated; use git diff --staged | gitleaks stdin), the core.hooksPath global-config collision that silently disables repo-local hooks, wiring gitleaks as a new file inside an existing global hooks dir instead of overriding hooksPath (preserves other global hooks like a prepare-commit-msg signoff/co-author trailer), a GIT_ALLOW_SECRETS=1 deliberate-bypass env var, and the fan-out scout survey workflow for batch-adding a large existing ~/.config tree (including that AI-tool MCP config files like mcp.json routinely embed live API keys/PATs and must be excluded or templated)."
---

## Setup

```bash
git init --bare $HOME/.dotfiles
alias dotfiles='git --git-dir=$HOME/.dotfiles/ --work-tree=$HOME'
dotfiles config --local status.showUntrackedFiles no
```

`status.showUntrackedFiles no` means only explicitly `dotfiles add`ed files ever show up — no accidental mass-add, no `.gitignore` maintenance. Always add one file/dir at a time, never `add -A`/`add .`.

For scripting (no shell alias available), use env vars instead of an alias:
```bash
GIT_DIR=$HOME/.dotfiles GIT_WORK_TREE=$HOME git <cmd>
```

## gitleaks hook — modern CLI, no `protect` subcommand

Newer gitleaks versions dropped `detect`/`protect` from `--help` (only `dir`/`git`/`stdin`/`completion`/`version` listed). `gitleaks protect --staged` may still nominally run but its internal git invocation breaks under custom `GIT_DIR`/`GIT_WORK_TREE` env (`error: unknown option 'staged'` from a mis-invoked `git diff --no-index`). Skip gitleaks' internal git call entirely — pipe the diff in yourself:

```bash
git diff --staged | gitleaks stdin --redact -v
```

## Critical gotcha: global `core.hooksPath` silently kills repo-local hooks

If `~/.config/git/config` sets `core.hooksPath` unconditionally (e.g. for a global signoff/co-author `prepare-commit-msg` hook — see `git-scoped-coauthor-trailer` skill), a bare repo's local `hooks/` dir is **never consulted** — `core.hooksPath` is a single-value key, local repo config silently overrides global, not merges with it. Symptom: a hand-rolled `.dotfiles/hooks/pre-commit` never fires, with no error — `prepare-commit-msg`-injected trailers (e.g. `Signed-off-by:`) silently vanish from commits in that repo.

**Wrong fix**: setting `core.hooksPath` locally on the bare repo to point elsewhere — this fixes the gitleaks hook but kills the global `prepare-commit-msg` hook for that repo (different single-value key collision, same root cause).

**Right fix**: don't touch `hooksPath` at all. Add a **new file** with a different hook name into the *existing* global hooks dir (`~/.config/git/hooks/pre-commit`, alongside `prepare-commit-msg`) — git hook filenames don't collide with each other, and both fire independently from the same `hooksPath`. Verify by checking `git log -1 --format=%B` for the trailer (not just console noise — `prepare-commit-msg` silently rewrites the message file, it doesn't print anything, so absence of console output is NOT proof it didn't run).

## Global bypass flag

Scope the gitleaks hook globally (fires in every repo on the machine, not just `.dotfiles`) with a deliberate escape hatch:

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
Usage: `GIT_ALLOW_SECRETS=1 git commit -m "..."`. Named `GIT_ALLOW_SECRETS` (not `ALLOW_SECRETS`) to avoid ambiguity with unrelated env vars.

## Verification matrix (don't skip any leg)

1. Real secret (properly-shaped, e.g. `AKIA` + 16 alnum for AWS — a too-long or literal AWS-doc-example key gives a false negative) → commit blocked, exit 1, nothing lands (`git log` unchanged).
2. Clean file → commit succeeds, `Signed-off-by`/other trailer present in `git log -1 --format=%B`.
3. `GIT_ALLOW_SECRETS=1` bypass → commit succeeds even with a real secret staged.
4. An unrelated repo (`/tmp/testrepo`, `git init`) → confirm scoping/global behavior matches intent.

## Fan-out scout survey for curating a large existing ~/.config tree

For a home directory with 100+ `.config` entries plus dozens of top-level dotfiles/dirs, don't read them all yourself — fan out ~8 scout subagents in parallel, each covering a cluster of paths, each producing one-line-per-path verdicts: `DEF ADD` (clean, useful) / `MAYBE` (needs scrub or is a judgment call) / `SHOULDN'T ADD` (secrets or account/session data) / `COULD GO` (stale cruft, e.g. `*.bak` files unrelated to the git decision). Explicitly instruct scouts to grep for secret patterns (`token|secret|password|api[_-]?key|auth|credential|bearer`) and to name-but-not-reproduce any found value.

Recurring finding: **AI coding-tool config directories are secret minefields.** `~/.claude.json`, `~/.codex/config.toml`, `~/.gemini/settings.json`, `~/.config/opencode/opencode.json`, and especially a harness's `mcp.json` routinely embed live plaintext API keys/PATs (Context7 `ctx7sk-*`, Figma `figd_*`, GitHub `ghp_*`, GitLab `glpat-*`) directly in `mcpServers`/`env` blocks — these are almost never safe to commit as-is; the same key is often duplicated across 3+ of these files. A clean subset (e.g. `hooks.json`, `AGENTS.md`, `config.yml`, or a `managed-skills/` library dir with no embedded credentials) frequently coexists in the same tool's config dir and can be cherry-picked. A tool's actual persistent skill/knowledge library (e.g. `~/.omp/agent/managed-skills/*/SKILL.md`) is usually pure text and safe — grep it too, but expect false positives from skill descriptions merely *mentioning* the words "token"/"api_key" in prose (verify each hit is a real embedded value, not documentation).

Also check subdirectories one level deeper than a single scout pass might catch (e.g. an app's `plugin_config/<x>/config.json` holding a password) even when the top-level directory looks like plain config — recurse into likely secret-bearing filenames (`obs-websocket/config.json`, `.docker/.token_seed`, browser NMH manifest dirs) explicitly.
