# Bare-repo dotfiles workflow

`git init --bare $HOME/.dotfiles` with `status.showUntrackedFiles no`, work tree `$HOME`, remote `origin` = `github.com/wbrous/dotfiles`. Scripted access without the shell function: `git --git-dir=$HOME/.dotfiles --work-tree=$HOME <cmd>` (not `GIT_DIR` env when going through omp's `pi.exec`, see `omp/extensions.md`).

## Commands

`dotfiles` is a bash function in `~/.bashrc` (tracked); it is not a binary, so non-bash shells and scripts must use the long git form.

| Command | Does |
|---|---|
| `dotfiles <git args>` | plain git against the bare repo (`dotfiles status`, `dotfiles add -- <path>`, `dotfiles commit -m ...`) |
| `dotfiles push` | resign-then-push in one command via `git-push-resign` (same flow as shadowed `git push`) |
| `dotfiles autoadd` | stage everything under `~/Docs` (`~/.local/bin/dotfiles-autoadd`); nothing is committed or pushed |

`dotfiles autoadd` contract: precondition `~/.dotfiles` and `~/Docs` exist (else exit 1); postcondition every new, modified, deleted, and renamed file under `Docs/` is staged and nothing outside `Docs/` is touched (paths already staged elsewhere stay staged). It honours the exclude list, so `*.swp`/`*~`/`*.bak` in Docs are skipped. Idempotent: a second run prints "already up to date". Then review `dotfiles diff --cached -- Docs` and commit with a real message. Why Docs only: it is the one tree where "add everything" is correct; the rest of `$HOME` is added one reviewed path at a time.

## What is a dotfile (standards)

A dotfile is **config written on purpose** by the user or their agent. If a theme change, a font change, or merely launching the app would modify the file, it is output and does not belong here.

| Not a dotfile | Examples | Verdict tag |
|---|---|---|
| Theme/font-hook output | `zed/themes/omazed.json`, `~/.omp/agent/themes/omarchy.json`, `btop/themes/current.theme`, omarchy `shell.json`/`shell.toml`, the omazed-managed `theme-set` hook | `NO-GENERATED` |
| App-saved state | pulsemeeter/Omacom/tern/strata/OBS/Pinta settings, `last-changelog-version`, Emulator.conf | `NO-GENERATED` |
| Installer output | native-messaging hosts, omarchy `*.sample`, `herdr-omp-agent-state.ts` ("managed by herdr"), mise config rewritten by `mise use` | `NO-GENERATED` |
| Other coding agents | `.claude`, `.codex`, `.gemini`, `.cursor`, `.copilot`, `.grok`, `.cline`, `.pi`, `.config/opencode`, `.config/devin`, ... (omp is the only agent) | `NO-AGENT` |
| Project source | anything under `~/Projects` | `NO-PROJECT` |
| Secrets/sessions | tokens, auth, history, sqlite, caches | `NO-SECRET` |
| Runtime-critical at a live path | gpg config, pinentry, signing hooks | `NO-LIVE` |

Exception to "other agents": `~/.agents/skills/` is the shared skill dir omp itself reads; real skill dirs there stay tracked, symlinks into `/usr/share/omarchy` do not.

**The exclude list** `~/.config/dotfiles/exclude` (tracked) encodes the table as rooted patterns. Enable once per clone (bare-repo config is not versioned):
```sh
git --git-dir=$HOME/.dotfiles config core.excludesFile $HOME/.config/dotfiles/exclude
```
Effect: `dotfiles add <excluded>` refuses without `-f`, and excluded paths never show as untracked candidates. It does NOT affect already-tracked files; untrack those with `dotfiles rm --cached -- <path>` (file stays on disk) and add a rooted pattern. Check: `dotfiles ls-files -ci --exclude-standard` must print nothing.

## Commit standards

- NEVER `dotfiles commit -a`/`-am` and NEVER a message like `update`. `-a` sweeps in every tracked file some tool rewrote; that is exactly how 33 `update` commits filled the history with theme output.
- Stage explicit paths (`dotfiles add -- <path>`), one logical change per commit, message says what the config does (`Add hypr monitor layout`, `Stop tracking <thing>`). Docs commits: `docs(<area>): <what>`.
- Never push unasked. `dotfiles push` resigns own unpushed commits first.
- Commit via `dotfiles commit` (the global gitleaks hook runs). Agent-made commits: `OMPCODE=1` is already in omp's bash env and adds the co-author trailer.

## Docs structure (for docs created after `autoadd`)

Everything under `~/Docs` is tracked automatically, so structure is the only gate:

- `Docs/<area>/<topic>.md`; area = system topic (`git`, `omarchy`, `hyprland`, `wine`, ...), never a project name (project knowledge is `<repo>/.omp/skills/<name>/SKILL.md`, committed with that repo).
- Every area folder has a `README.md` listing each doc, one line each (`- [topic.md](topic.md) - what it covers`). `Docs/README.md` indexes the area folders the same way. New area folder only when none fits, and add it to the root index in the same change.
- A doc is `## <Problem>` sections with **Symptom**, **Cause**, **Fix** as applicable, exact commands/paths/flags/error strings, preconditions stated. Non-obvious facts only; no secrets, tokens, or session output.
- No binaries or generated files in Docs; keep `*.bak`/`*.swp` out (the exclude list drops them anyway).
- Workflow after writing/editing docs: `dotfiles autoadd` → `dotfiles diff --cached --stat -- Docs` → `dotfiles commit -m "docs(<area>): ..."`.

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

## Survey: `/dotfiles-scan`

`~/.omp/agent/extensions/dotfiles-scan.ts` (tracked) injects the survey procedure into the agent; scopes: `docs`, `config`, `local`, `home`. Order it enforces: (1) `dotfiles autoadd` + one descriptive Docs commit; (2) snapshot the tracked list, drop everything matched by the exclude list; (3) parallel read-only scouts, one line per path `<path> | ADD|MAYBE|NO-GENERATED|NO-AGENT|NO-PROJECT|NO-SECRET|NO-LIVE | reason`; (4) sequential commits of the `ADD`s; (5) report `COMMITTED` / `MAYBE` / `EXCLUDED`.

Mechanics that bite:
- The bare repo has ONE shared index. NEVER run `add`+`commit` concurrently; one path (or one logical group) at a time, or one commit grabs both.
- `git add` through a symlink fails (`pathspec ... is beyond a symbolic link`). Some `~/.agents/skills/<name>` are symlinks into `/usr/share/omarchy/default/agents/skills/`; skip those.
- Scouts must say how a file got there (hand-written vs tool-written); that one fact decides most verdicts.
- Re-check each `ADD` against `dotfiles ls-tree -r --name-only HEAD` before staging; scouts do not know what is already tracked.
- Grep every candidate for `token|secret|password|api[_-]?key|auth[_-]?|credential|bearer|ghp_|glpat-|ctx7sk|figd_|AKIA` and one level into likely secret-bearing JSON (`mcpServers` blocks, `plugin_config`).

Standing judgment calls on this machine (all `MAYBE`/`NO`, learned from earlier sweeps): third-party checkouts with their own `.git` (omafilee, qs-bitwarden, robzolkos plugins, Utils/omazen); Equicord `settings.json` is account-linked (only `settings/quickCss.css` is tracked); `cava` config has a third-party email in its header; evince print-settings names a home printer; `vykey` is a hand-written 993-line tool (ask before adding); 89 generated `.desktop` files and bin stubs; generated omarchy themes (pink, spectrum-os, aether, ame-quattro); lazy-lock.json and lockfiles; browser/Electron profiles; ssh, `private-keys-v1.d`, mitmproxy pems; `.omp` mcp/auth-broker/collab-hosts tokens and Context7 `ctx7sk-…` keys in any agent config.

## Pruned 2026-11-11

Tracked files went 347 → 232 in three forward commits (published history untouched; files stay on disk, only untracked). Removed: 14 other coding agents' trees, theme/font-hook output, app-saved state, installer output, `Projects/archive/omarchy-passkey` (29 files of project source), and the live-path `.gnupg/gpg-agent.conf` (byte-identical copy already in `~/.local/share/gpg-fingerprint/`). The full list is `~/.config/dotfiles/exclude`.

Evidence the cut came from: 33 commits titled `update` were bulk sweeps of tracked files that something else had rewritten, and it was the same files every time: `pulsemeeter/config.json` (18 commits), `omarchy/shell.json`, `Omacom/omawrite.conf`, terminal font-size lines, `zed/themes/omazed.json`, `~/.omp/agent/themes/omarchy.json`, the claude/pi theme files, `last-changelog-version`. If a path keeps showing up in an `update`-style commit, it is output: untrack it and add a rooted pattern to the exclude list.

Left tracked on purpose: hypr, nvim, omarchy `plugins/wils.*` and the `theme-set.d` scripts, terminal/tmux/starship configs, `.local/bin` scripts, `.omp/agent/{config.yml,models.yml,APPEND_SYSTEM.md}` and the `dotfiles-scan`/`omarchy-theme-sync`/`repo-watch` extensions, shared `~/.agents/skills`, `mimeapps.list`, wireplumber/systemd/autostart units. Known soft spots, not pruned: `.config/git/{config,hooks/*}` are tracked at live paths (the live-path rule above says they should move to `~/.local/share/` with an install script), and `omarchy font` writes font sizes into the terminal configs, so those lines can still churn.
