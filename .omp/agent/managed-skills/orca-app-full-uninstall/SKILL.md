---
name: orca-app-full-uninstall
description: "Use when the user wants to fully uninstall/remove the Orca desktop app (Orca.AppImage / orca-ide) and everything it wired into other AI coding tools — e.g. \"remove orca completely\", \"uninstall orca\", \"orca is hooking into all my agents, get rid of it\". Orca injects itself widely: its own state dir, per-tool hook configs, orca-cli skill copies, omp/pi extensions, and app files — a simple rm -rf of one folder misses most of it."
---

## Why this is hard
Orca is not a single app install — it self-installs hooks/skills into nearly every AI coding tool on the machine. A naive removal of `~/.orca` or the AppImage leaves dozens of dangling references.

## Full footprint checklist (verified on this machine, re-check for drift)
1. **App files**: `~/Applications/Orca.AppImage`, `install-orca.sh`, `orca-ide-extracted`, `~/.local/bin/orca-ide`, `~/.local/share/applications/orca-ide.desktop`, `~/.local/share/icons/orca-ide.png`
2. **Orca's own state**: `~/.orca` (agent-hooks scripts per tool), `~/.config/orca` (profiles, browser partition, auth, usage stats, shell wrappers, terminal history)
3. **`orca-cli` skill** — copied/symlinked into nearly every tool's skills dir: `~/.claude/skills`, `~/.pi/agent/skills`, `~/.agents/skills`, `~/.hermes/skills`, `~/.factory/skills`, `~/.commandcode/skills`, `~/.grok/skills`, `~/.config/devin/skills`. `find ~ -maxdepth 4 -iname orca-cli` to enumerate.
4. **omp/pi extensions**: `orca-titlebar-spinner.ts`, `orca-prefill.ts`, `orca-agent-status.ts` under `~/.omp/agent/extensions` AND `~/.pi/agent/extensions`, plus a copy at `~/.config/amp/plugins/orca-agent-status.ts`. Also check `~/.omp/agent/managed-skills` for an orca-authored managed skill (e.g. `orca-mise-config-stomp`).
5. **Hook wiring injected into other tools' hook/settings JSON** — Orca inserts a shell snippet like `if [ -f '/home/USER/.orca/agent-hooks/<tool>-hook.sh' ] ...` into every lifecycle event. Found in: `~/.codex/hooks.json`, `~/.gemini/config/hooks.json`, `~/.cursor/hooks.json`, `~/.factory/settings.json`, `~/.commandcode/settings.json`. Some files (factory, commandcode, cursor) are *entirely* Orca's doing — safe to reset `"hooks"` to `{}`. Others (codex, gemini) mix Orca entries with unrelated integrations (e.g. `herdr`) — must surgically strip only entries containing `orca` (grep the JSON blob per-entry, don't nuke the whole file). Use Python json load/filter, not naive sed, to avoid corrupting JSON.
6. **Orca-only standalone hook files** (whole file is Orca, just delete): `~/.grok/hooks/orca-status.json(.bak)`, `~/.copilot/hooks/orca.json`.
7. **Stale backups**: files like `~/.claude/settings.json.bak` may be pre-Orca-install backups Orca left behind — safe to delete once the live config is already clean.
8. **`~/orca/workspaces/`** — NOT part of the app install. This is real project data: git worktrees Orca created for actual repos. **Never delete without asking** — check each worktree with `git status --short` for uncommitted work first. Prefer moving to a backup location (e.g. `~/Documents/Development/orca-workspace-backup`) over deleting outright.
9. **Dotfiles bare repo**: if the user tracks `$HOME` via a bare git repo (`~/.dotfiles`), most of the above paths are tracked there too. `git --git-dir=~/.dotfiles --work-tree=~ ls-files | grep -i orca` to find them. Stage deletions with `git add -A -- <paths>` (note: a single bad/untracked pathspec makes the whole `git add` invocation fail with no files staged — use `xargs` over a pre-verified `ls-files | grep` list rather than a hand-typed pathspec list). Commit the surgically-edited hook-config files (codex/gemini/cursor/factory/commandcode) as a separate commit from the pure deletions, since they're `M` not `D`/untracked.
10. Sweep for stragglers after: `~/.cache/*/*orca*` (e.g. claude-cli-nodejs pty cwd cache keyed on old `.config/orca` path), and `~/.omp/agent/sessions/-orca-workspaces-*` session dirs left pointing at the old (now-moved) workspace path.

## General approach
1. Enumerate first (`find ~ -maxdepth 4 -iname "*orca*"`, `grep -rl "orca" <hook config dirs>`) before deleting anything — footprint drifts across Orca versions.
2. Ask the user before touching `~/orca/workspaces` (or wherever Orca stores its managed worktrees) — that's user data, not app state.
3. For mixed JSON hook configs, edit programmatically (Python `json` module) to remove only Orca-authored entries; never regex/sed a JSON file with embedded shell strings.
4. If dotfiles-tracked, commit the removal so it doesn't silently resurrect on next `dotfiles pull`/checkout.
