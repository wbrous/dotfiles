---
name: dotfiles-survey-verdict-map
description: "Machine-specific verdict map for dotfiles scout surveys on this Arch/Omarchy box: which $HOME config paths are DEF ADD, MAYBE, or NO — plus survey mechanics."
---

# dotfiles-survey-verdict-map

Known-good / known-bad verdicts for the dotfiles fan-out scout survey on this
machine (Wils' Arch/Omarchy desktop), so future surveys don't re-derive them
from scratch. Use with the `dotfiles-bare-repo-gitleaks-hook` skill's scout
survey and the `/dotfiles-scan` extension prompt. Verdicts produced by full
scout sweeps on 2026-08-28, 2026-09-05 and 2026-10-26.

## DEF ADD (clean, committed — skip re-verifying, but re-check "already tracked")

- `.config/hypr/**` — 12 real personalized files (apps/{cider,hermes,pulsemeeter}.lua,
  autostart.lua, bindings.lua, hypridle.conf, hyprland.lua, hyprlock.conf,
  hyprsunset.conf, looknfeel.lua, monitors.lua, xdph.conf), NOT omarchy-store symlinks.
  Plus `apps/tern.lua` (2026-10).
- `.config/omarchy/plugins/wils.*` — `wils.notifications`, `wils.gallium-cheatsheet`,
  `wils.indicators`, `wils.audio`.
- `.config/omarchy/hooks/theme-set.d/{omarchy,20-zen,30-cider}-theme-sync.sh`, `10-owe-sync`.
- `.config/autostart/org.fcitx.Fcitx5.desktop` + `limine-snapper-notify.desktop`
  (+ `com.abdownloadmanager.desktop`, `jetbrains-toolbox.desktop`).
- `.config/gh/hosts.yml` (no token), `.config/gtk-3.0/bookmarks`, `.config/fcitx5/conf/xcb.conf`,
  `.config/tensaku/config.toml`, `.config/pulsemeeter/config.json`, `.config/pupgui/config.ini`,
  `.config/aether/settings.json` + `blueprints/Aether.json`, `.config/Android Open Source Project/Emulator.conf`,
  `.config/hyprland-preview-share-picker/config.yaml`, `.bash_logout`, `.gemini/projects.json`.
- Added 2026-10 (hand-authored, with contract comments): `.config/nvim/lua/plugins/lualine-transparent.lua`,
  `.config/wireplumber/wireplumber.conf.d/kef-lsx-no-suspend.conf`, `.config/hyprland-mimeapps.list`,
  `.config/xdg-desktop-portal/hyprland-portals.conf`, `.config/strata/settings.toml`,
  `.config/tern/settings.json`, `.config/cursor/cli-config.json`, `.config/uad/config.toml`,
  `.local/bin/{active-terminal-cwd,git-resign-own,mitm-passthrough-enable,mitm-passthrough-disable,omarchy-launch-screensaver,omp-launch,omp-launch-cwd,pinentry-fprintd,tern-launch-cwd}`,
  `.local/share/applications/so.stencil.tern{,.open,.url}.desktop`.

## MAYBE (skip by default, list only)

- ALL vendor skill dirs (`.claude/skills/*`, `.codex/skills/*`, `.gemini/config/skills/*`,
  `.pi/agent/skills/*`, `.agents/skills/*`, `.grok/skills/*`, `.commandcode/skills/*`,
  `.factory/skills/*`, `.hermes/skills/*`, `.config/devin/skills/*`) — symlinks into
  `~/.agents/skills` or `/usr/share/omarchy/default/agents/skills`.
- `.codex/skills/.system/*`, `.claude/skills/synced/`, `.claude/plugins/marketplaces/*`,
  `.grok/docs/**`, `.grok/README.md` — vendor-installed/regenerable.
- Backups: every `*.bak*`, `*.omarchy-upgrade-to-quattro.*`, `.config/hypr/old-conf-backup-*`,
  `.config/hypr/strata-keybind-backup-*`, `.omp/agent/APPEND_SYSTEM.md.old`.
- Stubs/regenerable/UI-state: 0-byte lazygit/lazydocker/gtk-4.0 files, `.config/nvim/lazy-lock.json`,
  `.config/codexctl/version-ids.json`, `.copilot/{config,settings}.json`, `.grok/hooks/herdr*`,
  `.pi/agent/extensions/herdr-agent-state.ts`, opencode/udiskie herdr/strata hook stubs,
  `.config/{calibre,FigCraft,vectorcraft,photocraft ui+preferences,pdfcraft,Pinta,tern/files.json,strata/tabs.toml,QtProject.conf,tool_state}`,
  `.config/obs-studio/plugin_config/rtmp-services/*`, `.config/fcitx5/**` (except xcb.conf), `.config/cava/**`
  (4 shaders carry a third party's email in a header), `.config/omarchy/lock-designs/*.qml` (117 files, clean but never bulk-decided),
  `.npmrc`/`.zshrc` (installer one-liners), `.config/Equicord/*` (settings.json is account-linked).
- Third-party checkouts with own `.git`: `.config/omarchy/plugins/{daniel-marr.omafilee,io.github.elevate08.qs-bitwarden-cli,robzolkos.github}`; `.local/bin/vykey` (vendored).
- Generated `.local/share/applications/*.desktop` (webapps, wine, electron, fcitx, JDK, JetBrains, Steam) and `.local/bin` binaries/symlinks into tool installs.
- Generated Omarchy themes: `.config/omarchy/themes/{pink,spectrum-os,aether,ame-quattro}`.

## NO — live credentials on disk (NEVER commit)

- Context7 key `ctx7sk-…` duplicated across `.omp/agent/mcp.json`, `.codex/config.toml` (+`.bak`),
  `.gemini/config/mcp_config.json`, `.gemini/settings.json`, `.config/opencode/opencode.json`.
- `.omp/agent/mcp.json` (ctx7sk, figd_ x2, glpat-, ghp_), `.omp/auth-broker.token`,
  `.omp/run/collab-hosts/*.json` (bearer token), `.claude/.credentials.json`, `.claude.json` (+ `.claude/backups/*`),
  `.claude/daemon/control.key`, `.config/glab-cli/config.yml`, `.config/manicode/credentials.json`,
  `.config/remarkable-xovi-installer/config.json`, `.config/aether/wallhaven.json`, `.bash_history`,
  `.pi/agent/auth.json`, `.hermes/.env` + `auth.json`, `.convex/config.json` (JWT), `.docker/.token_seed`,
  `.cloudflared/{cert.pem,orgbot.json}`, `.config/opencode/service.json` (password),
  `.config/obs-studio/plugin_config/obs-websocket/config.json` (server_password),
  `.config/photocraft/control-token`, `.config/passless/extension_key.pem`, `.config/pulse/cookie`, `.pager/`.
- Account identity: `.copilot/config.json`, `.config/Equicord/settings/settings.json`.

## NO — machine data (runtime/session/db/cache/browser)

- Browser/Electron profiles under `.config` (hermes-desktop, discord, zen, chromium, brave, chrome, figma-linux, Signal, 1Password, Bitwarden...).
- Sessions/history: `.claude/{projects,history.jsonl,jobs,daemon}`, `.copilot/{session-state,session-store.db*,logs,...}`,
  `.grok/{sessions,memtrace,logs}`, `.cline/{data,kanban}/**`, `.pi/pi-acp/*`, `.config/manicode/projects/**`.
- SQLite + wal/shm: `.codex/*.sqlite*`, `.omp/agent/{agent,history}.db*`, `.omp/stats.db`, `.crush/crush.db`, `.config/github-copilot/auth.db`.
- `.codex/.tmp`, `.docker/buildx`, `.config/dconf/user`, logs, locks, sockets, pids, `.pulse-cookie`, `.steampid`, `.emulator_console_auth_token`.

## Survey mechanics (fast path)

1. Snapshot: `git --git-dir=$HOME/.dotfiles --work-tree=$HOME ls-tree -r --name-only HEAD > /tmp/trk`
   (user prompts sometimes write `'$HOME/.dotfiles'` in single quotes — use a real expanded path).
   Filter with `grep -vFxf` (NOT `comm`; locale sort-order complaints).
2. Candidates: `find <dir> \( -type f -o -type l \) | grep -vFxf /tmp/trk` per cluster; prune noise
   (projects, sessions, cache, node_modules, .git). `.config` has 100k+ untracked files in browser/app dirs; narrow to config-y roots.
3. Write per-cluster path lists to /tmp/survey/*.txt, pre-filter .bak/log/lock/cache into MAYBE/NO yourself,
   and point scouts at the list files (7 scouts in one `task` batch finishes in ~45s).
4. **Scouts over-call DEF ADD** (state files, generated stubs, recent-path files, files with third-party emails).
   Independently re-verify: strict secret-shape grep + email/IP grep + read each file. Commit only hand-authored,
   durable, secret-free files. Scouts were right on NO for password-bearing files.
5. Commit sequentially one path at a time (`add -- path`, `commit -m "Add path"`); verify each commit has exactly 1 file.
   Hook appends `Co-authored-by: wbrous-dev-ai` trailer automatically.
6. Another process may commit to `.dotfiles` mid-survey (2026-10: watermarks-remover removal `1c8d892`); a tracked-count
   delta mismatch means check `git log <snapshot>..HEAD` before suspecting your own commits.
