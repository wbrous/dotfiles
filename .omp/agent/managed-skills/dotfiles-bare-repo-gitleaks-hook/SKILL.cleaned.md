---
name: dotfiles-bare-repo-gitleaks-hook
description: "Use when setting up or maintaining the bare-repo dotfiles workflow, wiring/debugging the gitleaks pre-commit hook, or running the fan-out scout survey to find and add new/untracked config, skills, or AI-tool dotfiles under $HOME — covers the status.showUntrackedFiles trick, the modern gitleaks CLI (stdin, not protect --staged), the global core.hooksPath collision, the GIT_ALLOW_SECRETS bypass (including the git config user.signingkey GPG-fingerprint false positive), syncing managed-skills into the dotfiles repo, recurring live-secret traps in AI-tool config dirs (Context7 ctx7sk keys duplicated across .gemini/settings.json + .gemini/config/mcp_config.json + .claude.json, GitHub Copilot auth.db oauth_tokens, Figma-linux Electron session/cookie profiles, GitLab glpat- tokens embedded in innocuous-looking files like .codex/config.toml, .gemini/config/mcp_config.json, .gemini/settings.json, glab-cli/config.yml), and the \"pathspec is beyond a symbolic link\" git-add failure when a candidate path (e.g. ~/.claude/skills/name, ~/.codex/skills/name, ~/.gemini/config/skills/name, ~/.pi/agent/skills/name) is actually a symlink into a system- or harness-owned skill store (~/.agents/skills/*)."
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

### Known false positive: `user.signingkey` in `~/.config/git/config`

gitleaks' `generic-api-key` rule (entropy-based) flags a GPG `user.signingkey` line (a 40-hex-char fingerprint) as a potential secret. It is not one — a GPG key fingerprint/ID is a **public** identifier meant to be shared so others can verify signatures; the actual private key material lives in `~/.gnupg`, never in git config. Confirm the flagged line really is `signingkey = <40 hex chars>` (not some other high-entropy value pasted into the same file), then commit with `GIT_ALLOW_SECRETS=1`.

## Verification matrix (don't skip any leg)

1. Real secret (properly-shaped, e.g. `AKIA` + 16 alnum for AWS — a too-long or literal AWS-doc-example key gives a false negative) → commit blocked, exit 1, nothing lands (`git log` unchanged).
2. Clean file → commit succeeds, `Signed-off-by`/other trailer present in `git log -1 --format=%B`.
3. `GIT_ALLOW_SECRETS=1` bypass → commit succeeds even with a real secret staged.
4. An unrelated repo (`/tmp/testrepo`, `git init`) → confirm scoping/global behavior matches intent.

## Fan-out scout survey for curating a large existing ~/.config tree — or for periodic "what's new" sweeps

For a home directory with 100+ `.config` entries plus dozens of top-level dotfiles/dirs, don't read them all yourself — fan out scout subagents in parallel via `task`, each covering a cluster of paths (group by tool/vendor: e.g. one cluster per AI coding tool — `.claude`, `.codex`, `.gemini`, `.cursor`, `.grok`, `.openclaude`, `.commandcode`, `.factory`, `.kimi-code`, `.copilot`, plus a `.config/<misc-tool>` cluster), each producing one-line-per-path verdicts: `DEF ADD` (clean, useful) / `MAYBE` (needs scrub, is a judgment call, auto-generated stub, or empty dir) / `SHOULDN'T ADD` (secrets or account/session data). Explicitly instruct scouts to grep for secret patterns (`token|secret|password|api[_-]?key|auth|credential|bearer|ghp_|glpat-|ctx7sk|figd_|AKIA`) and to name-but-not-reproduce any found value, and to pre-flag known-secret files (name them in the task prompt) so scouts skip reading them entirely rather than wasting a read on a file already known to hold a live credential.

**Before staging any scout-verdicted `DEF ADD` path, re-check it against the tracked file list** (`dotfiles ls-tree -r --name-only HEAD`, or a snapshot of it) — scouts sometimes verdict a path `DEF ADD` that is in fact already tracked (e.g. a shared file appearing in multiple candidate clusters, or one already committed in an earlier session). `git add` on an already-tracked unchanged path is harmless but wastes a commit-message line and muddies the "what's actually new" signal; filter the scout's file list against the tracked snapshot with a quick loop before running `dotfiles add`.

**When re-running this survey later** (e.g. "any new skills/configs since last time?"), diff the *tracked* file list (`dotfiles ls-tree -r --name-only HEAD`) against the current on-disk tree per candidate cluster — do this yourself once, cheaply, before dispatching scouts, so each scout gets an explicit, already-narrowed path list (rule: ≤3–5 explicit target paths per task is a soft guide; for this workflow give each scout its full cluster's untracked-candidate list, 5–20 paths, since scouts are read-only and the alternative is serial dispatch).

Recurring finding: **AI coding-tool config directories are secret minefields, and the trap is rarely in the obviously-named file.** `~/.claude.json`, `~/.codex/config.toml`, `~/.gemini/settings.json`, `~/.gemini/config/mcp_config.json`, `~/.config/opencode/opencode.json`, `~/.config/glab-cli/config.yml`, and especially a harness's `mcp.json` routinely embed live plaintext API keys/PATs (Context7 `ctx7sk-*`, Figma `figd_*`, GitHub `ghp_*`, GitLab `glpat-*`) directly in `mcpServers`/`env`/`args` blocks or (for `glab-cli`) a plain-looking `token:` field under a per-host key — these are almost never safe to commit as-is; the same key is often duplicated across 3+ of these files (e.g. a Context7 `ctx7sk-*` value routinely turns up simultaneously in `.gemini/settings.json`, `.gemini/config/mcp_config.json`, AND `.claude.json`'s auto-generated telemetry/tips state — check all three, not just the two "config"-looking ones). Also watch for auth-token-bearing SQLite DBs in tool config dirs (`~/.config/github-copilot/auth.db` has a populated `oauth_tokens` table) and full Electron/Chromium profile dirs (`~/.config/figma-linux` — cookies, trust tokens, session storage, `authedUserIDs` in `settings.json`) — both are `SHOULDN'T ADD` even though nothing in them looks like a "flat" secret string. A clean subset (e.g. `hooks.json`, `AGENTS.md`, `config.yml` *sibling* to the secret-bearing file — `gh/config.yml` is clean even though `gh/hosts.yml` next to it holds the oauth token — or a tool's `managed-skills/`-style library dir with no embedded credentials) frequently coexists in the same config dir and can be cherry-picked. A tool's actual persistent skill/knowledge library (e.g. `~/.omp/agent/managed-skills/*/SKILL.md`) is usually pure text and safe — grep it too, but expect false positives from skill descriptions merely *mentioning* the words "token"/"api_key"/"password" in prose (verify each hit is a real embedded value, not documentation — e.g. "password manager triggers" or "grep for the token value" in a SKILL.md body is not a leak).

Also check subdirectories one level deeper than a single scout pass might catch (e.g. an app's `plugin_config/<x>/config.json` holding a password) even when the top-level directory looks like plain config — recurse into likely secret-bearing filenames (`obs-websocket/config.json`, `.docker/.token_seed`, browser NMH manifest dirs) explicitly.

### `git add` gotcha: "pathspec '...' is beyond a symbolic link"

Many AI-tool `skills/<name>` directories (`~/.claude/skills/orca-cli`, `~/.codex/skills/omarchy`, `~/.gemini/config/skills/<name>`, `~/.pi/agent/skills/<name>`, `~/.commandcode/skills/orca-cli`, `~/.factory/skills/orca-cli`, `~/.grok/skills/orca-cli`, etc.) are **symlinks**, not real directories — pointing at a harness-owned store (`~/.agents/skills/<name>`) or a system-owned/distro store (`/usr/share/omarchy/default/agents/skills/<name>`). `git add <path-through-the-symlink>/SKILL.md` fails with `fatal: pathspec '...' is beyond a symbolic link` because git refuses to traverse through a tracked-or-not symlink component. Treat these as `MAYBE`/skip by default: the symlink target is either already tracked elsewhere (harness-owned, e.g. `~/.agents/skills/orca-cli`) or genuinely not this machine's dotfiles to own (system package, regenerated on update) — don't try to `git add -f` through them or copy the target content in; resolve with `readlink` to confirm before excluding, and only special-case adding the *canonical* (non-symlink) source path if it isn't already tracked. When a scout has no shell/readlink available, a 0-byte size on a `skills/<name>` entry plus content identical to the harness store (`~/.agents/skills/<name>`) is a reliable proxy for "this is a symlink into the shared store."

### Toolchain-generated/near-empty stubs — default to skip

`~/.kimi-code/config.toml`, `~/.copilot/config.json`, `~/.copilot/hooks/orca.json` and similar Orca/harness-managed hook-wiring files often carry a "managed by X, do not edit" header, churn on every tool launch (timestamps/flags), or are literally `{"version":1,"hooks":{}}`. These are `MAYBE` by default (safe to add, but auto-regenerated and near-zero value, drift risk) — skip unless the user asks specifically for them. Empty directories/0-byte config stubs (e.g. `~/.config/devin/skills` with no files, or a freshly-scaffolded `~/.config/lazygit/config.yml`/`~/.config/fastfetch/` with nothing written yet) can't meaningfully be tracked; note as `MAYBE` and move on — re-survey later once the user has actually customized them.
