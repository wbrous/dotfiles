---
name: dotfiles-survey-verdict-map
description: "Machine-specific verdict map for dotfiles scout surveys on this Arch/Omarchy box: which $HOME config paths are DEF ADD (hypr suite, gh hosts.yml, autostart entries), MAYBE (vendor skill symlinks, backups), or NO (live credentials in mcp.json/.codex/config.toml/.gemini/*/.claude/.config/glab-cli, browser profiles, session stores, sqlite DBs) — plus the fast survey mechanics (tracked snapshot, cluster files, parallel scout batch)."
---

# dotfiles-survey-verdict-map

Known-good / known-bad verdicts for the dotfiles fan-out scout survey on this
machine (Wils' Arch/Omarchy desktop), so future surveys don't re-derive them
from scratch. Use with the `dotfiles-bare-repo-gitleaks-hook` skill's scout
survey and the `/dotfiles-scan` extension prompt. These verdicts were produced
by a full parallel-scout sweep on 2026-08-28 and re-verified before commit.

## DEF ADD (clean, already committed — skip re-verifying, but re-check "already tracked")

- `.config/hypr/**` — all 12 files (apps/{cider,hermes,pulsemeeter}.lua,
  autostart.lua, bindings.lua, hypridle.conf, hyprland.lua, hyprlock.conf,
  hyprsunset.conf, looknfeel.lua, monitors.lua, xdph.conf) are real personalized
  configs, NOT omarchy-store symlinks. Secret-scan clean (false positives only:
  `token` in xdph allow_token_by_default, `Password` bind labels).
- `.config/gh/hosts.yml` — NO token (auth is keyring-backed), clean profiles.
- `.config/gtk-3.0/bookmarks` — user bookmarks.
- `.config/fcitx5/conf/xcb.conf` — deliberate setting.
- `.config/autostart/com.abdownloadmanager.desktop` +
  `jetbrains-toolbox.desktop` — user-created entries.
- `.config/hyprland-preview-share-picker/config.yaml`.
- `.bash_logout` — stock Arch stub. `.bash_history` is NOT — see NO.
- `.gemini/projects.json` — clean project-name mapping.

## MAYBE (skip by default, list only)

- ALL vendor skill dirs: `.claude/skills/*`, `.codex/skills/{omarchy,diagnose-crash}`,
  `.gemini/config/skills/*`, `.pi/agent/skills/*`, `.agents/skills/*`,
  `.grok/skills/*`, `.commandcode/skills/*`, `.factory/skills/*`,
  `.config/devin/skills/*` — symlinks into the shared `~/.agents/skills` store
  (itself symlinked). Same content across vendors. Track `~/.agents/skills` once
  instead if versioning is wanted.
- `.codex/skills/.system/*` — vendor auto-installed system skills
  (`.codex-system-skills.marker` present), churn risk.
- Backups: `.config/hypr/old-conf-backup-20260811/*`, `*.omarchy-upgrade-to-quattro.*.bak`,
  `*.bak` config backups, `.omp/agent/APPEND_SYSTEM.md.old`.
- Stubs/empty/regenerable: `.config/lazygit/config.yml` (0B), `.config/nvim/lazy-lock.json`,
  `.config/codexctl/version-ids.json`, `.copilot/config.json` + `hooks/orca.json`,
  `.codex/hooks.json.bak`, `.claude/remote-settings.json`, `AGENTS.md.disabled`,
  `.config/manicode/{freebuff,rg,tree-sitter.wasm}` (vendored binaries),
  `.config/hermes-desktop/{Preferences,Dictionaries}`.

## NO — live credentials on disk (NEVER commit; re-check any new file matching these)

- **Context7 key `ctx7sk-a1a43f99-…` is duplicated across FOUR files**:
  `.omp/agent/mcp.json`, `.codex/config.toml` (+`.bak`), `.gemini/config/mcp_config.json`,
  `.gemini/settings.json`. If one leaks, all four locations carry the same key.
- `.omp/agent/mcp.json` — 4 live creds: ctx7sk-, figd_ ×2, glpat- (git.phermata.org), ghp_.
- `.claude/.credentials.json` — Claude OAuth sk-ant-oat01/ort01.
- `.config/glab-cli/config.yml` — live glpat- for git.phermata.org.
- `.config/manicode/credentials.json` — authToken + fingerprint + email.
- `.bash_history` — 2073 lines incl. a live Discord bot token (Authorization: MTI4Mjcz…).
- `.pi/agent/auth.json` — auth file (empty {} at scan time, will hold tokens).

## NO — machine data (runtime/session/db/cache/browser)

- Browser profiles: `.config/hermes-desktop/**` (full Chromium profile: Cookies,
  DIPS, Trust Tokens, Session Storage, GPU caches, Shared Dictionary), also
  Brave/chromium/brave-*/google-chrome*/microsoft-edge* dirs under `.config`.
- Session stores: `.claude/projects/**/*.jsonl` + `subagents/*`, `.claude/history.jsonl`,
  `.claude/jobs/*`, `.claude/daemon/*` (incl. control.key), `.copilot/session-*`,
  `.copilot/session-store.db*`, `.pi/pi-acp/*`, `.cline/kanban/**`, `.cline/data/**`,
  `.config/manicode/projects/**/chats/**` + `message-history.json` (PII),
  `.config/herdr/session.json`.
- SQLite DBs (+wal/shm sidecars): `.codex/*.sqlite*` (state/logs/goals/memories/queue),
  `.copilot/session-store.db*`, `.cline/data/db/*`, `.omp/agent/{models,history}.db*`,
  `.omp/cache/*.db*`.
- Runtime/log/socket/pid: `.omp/agent/terminal-sessions/*`, `.claude/*.{log,lock}`,
  `.config/cliamp/*`, `.config/herdr/*.{log,sock}`, `.config/hermes-desktop/logs/*`,
  `mimeinfo.cache`, `gpu_cache.json`, `install-id`, `last-changelog-version`,
  `.config/fcitx/dbus/*`, `.config/fcitx5/conf/cached_layouts`,
  `.orca/claude-agent-teams-bin/tmux` (harness shim).

## Survey mechanics (fast path for the next sweep)

1. Snapshot tracked: `git --git-dir=$HOME/.dotfiles --work-tree=$HOME ls-tree -r --name-only HEAD | sort > /tmp/trk`.
2. Candidate list: `find -L <dir> -type f | grep -vFx -f /tmp/trk` per cluster; narrow
   `.config` to config-y roots (skip browser/app-data dirs — they're 10k+ files of noise).
3. Dispatch scouts in ONE parallel `task` batch; each scout reads its cluster file and
   emits one-line `DEF ADD` / `MAYBE` / `SHOULDN'T ADD` verdicts.
4. Re-verify DEF ADDs against `/tmp/trk` before staging (skip already-tracked);
   commit one logical group or one path at a time, never `add -A`. Gitleaks hook runs
   per commit; report false-positive blocks in MAYBE, never force with GIT_ALLOW_SECRETS=1.
