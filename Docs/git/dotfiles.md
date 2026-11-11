# Bare-repo dotfiles workflow

`git init --bare $HOME/.dotfiles` with `status.showUntrackedFiles no`; scripted access via `GIT_DIR=$HOME/.dotfiles GIT_WORK_TREE=$HOME git <cmd>`.

## gitleaks hook (modern CLI, no `protect`)

**Fix:** newer gitleaks dropped `detect`/`protect` from help; `gitleaks protect --staged` breaks under custom `GIT_DIR`/`GIT_WORK_TREE` (`error: unknown option 'staged'`). Pipe the diff in directly:
```sh
git diff --staged | gitleaks stdin --redact -v
```
Global bypass flag (fires in every repo):
```sh
if [ "${GIT_ALLOW_SECRETS:-}" = "1" ]; then echo "GIT_ALLOW_SECRETS=1 set — skipping gitleaks scan."; exit 0; fi
git diff --staged | gitleaks stdin --redact -v
```
Usage: `GIT_ALLOW_SECRETS=1 git commit -m "..."`. Known false positive: `user.signingkey` (40-hex fingerprint, a public identifier — key material lives in `~/.gnupg`) trips `generic-api-rule`; confirm the flagged line is really `signingkey`, then commit with the bypass.

**Critical gotcha:** if `~/.config/git/config` sets `core.hooksPath` globally, a bare repo's local `hooks/` dir is never consulted (single-value key — local overrides global, never merges). Wrong fix: setting `hooksPath` locally (kills the global `prepare-commit-msg` trailer hook for that repo). Right fix: add a new file with a different hook name into the existing global hooks dir (`~/.config/git/hooks/pre-commit` alongside `prepare-commit-msg`) — hook filenames don't collide. Verify with `git log -1 --format=%B` for the trailer, not console noise.

Verification matrix: real secret (properly-shaped, e.g. `AKIA`+16 alnum) → blocked exit 1; clean file → lands with trailer; bypass env → lands; unrelated `/tmp/testrepo` → matches intended scoping.

_Migrated from: dotfiles-bare-repo-gitleaks-hook_

## NEVER track runtime-critical files at live paths

**Symptom:** `dotfiles push` → `git-resign-own` rebase fails with `gpg: keybox '~/.gnupg/pubring.kbx' created` / `No secret key` / `INV_SGNR`, plus `.bak` files and tracked config vanishing mid-push.

**Cause:** the bare repo uses `work-tree=$HOME`. The resign rebase checks out older trees into `$HOME`, so any file tracked at its live path but absent from those older trees is deleted from disk mid-push (gpg-agent.conf/common.conf/pinentry vanish → gpg makes a fresh empty local keyring; key material in `private-keys-v1.d` untouched). Git leaves `.bak` copies when it restores them.

**Rule:** never track runtime-critical files (gpg config, pinentry, git hooks/config used for signing, anything the push itself depends on) at live paths. Track a copy under a non-live dir (e.g. `~/.local/share/<topic>/`) + install script copying to the live path.

**Recovery:** `dotfiles rebase --abort`, remove `~/.gnupg/*.bak` and the empty 32-byte `pubring.kbx`, `gpgconf --kill all; gpg --list-secret-keys`, move files to the safe dir (`dotfiles rm --cached <live>`, `dotfiles add <safe>`). If the bad commit is unpushed HEAD: `dotfiles commit --amend --no-gpg-sign`. Verify shape without signing by replaying the same rebase with an exec asserting file existence + `sha256sum -c`; the real fingerprint prompt on push remains untested until then. Same latent hazard applies to `~/.config/git/config` and `~/.config/git/hooks/*` tracked at live paths.

Machine layout: tracked `~/.local/share/gpg-fingerprint/{gpg-agent.conf,common.conf,sshcontrol,pinentry-fprintd}` + `~/.local/bin/install-gpg-fingerprint`; live `~/.gnupg/gpg-agent.conf` root-owned (chown before user edits).

_Migrated from: dotfiles-bare-repo-rebase-deletes-live-config_

## Fan-out scout survey mechanics

For 100+ `.config` entries: fan out scout subagents per cluster (per AI tool + misc), each returning one-line verdicts `DEF ADD` / `MAYBE` / `SHOULDN'T ADD`, grepping `token|secret|password|api[_-]?key|auth|credential|bearer|ghp_|glpat-|ctx7sk|figd_...`. Before staging any `DEF ADD` path, re-check against tracked state (`dotfiles ls-tree -r --name-only HEAD`) — scouts verdict already-tracked paths. On re-survey, diff tracked vs on-disk per cluster yourself first, then give each scout its narrowed 5–20 path list.

Commit sequencing: the bare repo has a single shared index — NEVER run `add`+`commit` concurrently; sequence strictly one path at a time or one commit grabs both files. `git add` through a symlink fails (`pathspec ... is beyond a symbolic link`) — AI-tool `skills/<name>` dirs are usually symlinks into `~/.agents/skills` or `/usr/share/omarchy/...`; default MAYBE/skip.

_Migrated from: dotfiles-bare-repo-gitleaks-hook_

## Verdict map (this machine, Arch/Omarchy)

Full sweeps 2026-08-28 through 2026-10-30. DEF ADD: `.config/hypr/**` (12 real files, not omarchy-store symlinks; plus `apps/tern.lua`), `.config/omarchy/plugins/wils.*`, `hooks/theme-set.d/{omarchy,20-zen,30-cider,10-owe}-sync.sh`, listed autostart/desktop files, `gh/hosts.yml` (no token), gtk-3.0/bookmarks, fcitx5 xcb.conf, tensaku/pulsemeeter/pupgui/aether configs, emulator conf, picker config, `.bash_logout`, `.gemini/projects.json`, 2026-10 hand-authored nvim/wireplumber/mimeapps/portals/strata/tern/cursor/uad files + listed `~/.local/bin` scripts + stencil `.desktop`s, 2026-10-30 `.gnupg/gpg-agent.conf` + Equicord `quickCss.css`.

MAYBE (skip by default): all vendor skill dirs (41 confirmed symlinks 2026-10-30), `.codex/.system/*`, claude synced/marketplaces/trash, grok docs/README, backups (`*.bak*`, `*.omarchy-upgrade-to-quattro.*`, hypr backups), stubs/regenerable (lazygit/lazydocker/gtk-4.0 zeros, lazy-lock.json, codexctl version-ids, copilot configs, orca/pi/opencode/udiskie/kilo/qwen herdr stubs, calibre/FigCraft/vectorcraft/photocraft/pdfcraft/Pinta/tern/strata/QtProject/tool_state, obs rtmp-services, fcitx5 except xcb, cava — third-party email in header, 117 omarchy lock-design QMLs), `.npmrc`/`.zshrc` one-liners, Equicord except quickCss (`settings.json` account-linked), demoted 2026-10-30 (qwen marker/settings, opencode cli/gitignore/package, omarchy shims, evince print-settings naming home printer, tern carly, dictation defaults, codex pets/AGENTS.md.disabled), `vykey` + desktop (hand-written 993-line tool, ask user), third-party checkouts with own `.git` (omafilee/qs-bitwarden/robzolkos plugins, Utils/omazen), 89 generated `.desktop`s + bin binaries/stubs/symlinks, generated omarchy themes (pink/spectrum-os/aether/ame-quattro).

NO (never commit): Context7 `ctx7sk-…` across omp/codex/gemini/opencode configs, `.omp` mcp/auth-broker/collab-hosts tokens, claude credentials/backups/daemon, glab config, manicode/aether/wallhaven/bash_history/pi/hermes/convex/docker/cloudflared/opencode-service/obs-websocket/photocraft/passless/pulse/tern-host keys, copilot auth.db, Equicord settings, ssh, `private-keys-v1.d`, mitmproxy pems; browser/Electron profiles; sessions/history (`claude/{projects,history.jsonl,jobs,daemon}`, copilot session-state/store/db, grok sessions/memtrace/logs, cline, pi-acp, manicode, tern triples, t3); sqlite+wal/shm; tmp/build/dconf/logs/locks/sockets/pids.

_Migrated from: dotfiles-survey-verdict-map_
