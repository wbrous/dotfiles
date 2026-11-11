# Installing apps on Linux (native) and fully removing Orca

Native Linux install paths — manual vendor bundles, single binaries — plus the icon-cache spaces gotcha and the full Orca uninstall checklist. (For Windows apps under Wine, see `electron-apps.md` / `prefix-and-msi.md`.)

## Manual vendor bundle with hardcoded Exec path (needs sudo)

**Symptom:** downloaded tarball like `rev-hardware-client-1.4.2/` containing `bin/<binary>`, `lib/app/`, `lib/runtime/`, `share/applications/<reverse-dns>.desktop`, `share/icons/hicolor/<size>/apps/<icon>.png` — no `install.sh`. (E.g. REV Hardware Client, FTC/FRC robotics GTK tooling.)

**Cause:** n/a — install task. Key insight: the bundled `.desktop`'s `Exec=` already hardcodes where the binary MUST live (e.g. `/usr/lib/rev-robotics/rev-hardware-client/bin/rev-hardware-client`) — read it first instead of inventing paths.

**Fix:**
1. Read `share/applications/*.desktop` for `Exec=` (target path) and `Icon=` (icon name).
2. `sudo mkdir -p` the parent dir implied by Exec, then `sudo cp -r` the whole extracted bundle there so bin/lib/share stay together exactly as shipped.
3. `sudo ln -sf <installed>/bin/<binary> /usr/local/bin/<binary>`.
4. `sudo cp` the `.desktop` to `/usr/share/applications/`; `sudo cp -r share/icons/hicolor /usr/share/icons/` (whole tree at once — sizes 16 through 1024 — no per-size loop).
5. `sudo update-desktop-database /usr/share/applications` and `sudo gtk-update-icon-cache -f /usr/share/icons/hicolor` (may silently no-op on some distros; harmless).
6. Verify: `ls -la` the installed dir, `cat` the installed `.desktop` to confirm Exec resolves.

Batch sudo commands into one shell invocation (`&&`/newlines) — separate calls each trigger a fresh fingerprint prompt; back-to-back commands in one script usually prompt once.

_Migrated from: linux-manual-app-bundle-install_

## Single standalone binary, user-local install (no sudo)

**Symptom:** lone ELF binary from `~/Downloads` (e.g. `Tern-0.8.2-linux-x86_64/tern/tern`, ~160MB stripped), no bundle, no `.desktop`, user wants a launcher shortcut. (If the archive ships a `.desktop`, use the bundle section above instead.)

**Fix:**
1. Inspect: `file <bin>`, `ldd <bin> | grep 'not found'`, `<bin> --help | head -60`, `<bin> --version`.
2. Check `--help` for a self-registration subcommand (`register`, `install`, `desktop-integration`) before hand-writing anything — Tern has `tern register`, which writes `.desktop` files, MIME associations, and hicolor icons itself.
3. Install to a stable path BEFORE registering (generated `Exec=` hardcodes the running binary's path — never register from `~/Downloads`):
```bash
mkdir -p ~/.local/opt/<app> ~/.local/bin
cp <bin> ~/.local/opt/<app>/<app> && chmod +x ~/.local/opt/<app>/<app>
ln -sf ~/.local/opt/<app>/<app> ~/.local/bin/<app>
```
4. Run `<app> register`. Verify: `desktop-file-validate ~/.local/share/applications/<id>.desktop`, `find ~/.local/share/icons -name '<id>*'`.
5. No register command: hand-write `~/.local/share/applications/<name>.desktop` (copy style from existing ones like `Alacritty.desktop`: Exec/Icon/StartupWMClass/Categories), then `update-desktop-database ~/.local/share/applications`.
6. Literal desktop icon is opt-in: `cp the.desktop ~/Desktop/ && chmod +x` (Hyprland/Omarchy — skip unless asked).

Tell the user: `register` may claim file-type/MIME handlers (mention the `unregister` undo); warn if help mentions account sign-in/closed beta; `~/Downloads` can be deleted after copying.

_Migrated from: linux-single-binary-app-user-install_

## gtk-update-icon-cache "generated cache was invalid" (spaces in filenames)

**Symptom:** installers warn `gtk-update-icon-cache: The generated cache was invalid.` for `~/.local/share/icons/hicolor`; only the user icon cache is stale, the app works.

**Cause:** icon files with **spaces in their names** under `~/.local/share/icons/hicolor/<size>/apps/` (e.g. `Disk Usage.png`, `Google Maps.png` from Omarchy webapp installers). Missing `index.theme` in the user hicolor dir was ruled out (adding it didn't help).

**Fix — diagnose without touching the real dir:**
```sh
T=$(mktemp -d); cp -r ~/.local/share/icons/hicolor $T/h; cd $T/h; rm -f .icon-theme.cache
gtk-update-icon-cache -f .                 # fails
find . -name '* *' -delete; gtk-update-icon-cache -f .   # succeeds => spaces are the cause
```
List offenders: `find ~/.local/share/icons/hicolor -name '* *'`. Then rename to dash names AND update `Icon=` in the matching `.desktop` files, rebuild:
```sh
cd ~/.local/share/icons/hicolor/48x48/apps
for f in *\ *.png; do mv "$f" "${f// /-}"; done
gtk-update-icon-cache -f ~/.local/share/icons/hicolor
```
Caveat: the Omarchy webapp installer may recreate spaced names on next run — ask before renaming.

_Migrated from: gtk-update-icon-cache-invalid-space-filenames, linux-single-binary-app-user-install_

## Fully uninstalling the Orca desktop app

**Symptom:** "remove orca completely" — naive `rm -rf ~/.orca` leaves dozens of dangling references, because Orca injects hooks/skills into nearly every AI coding tool on the machine.

**Fix — footprint checklist (verified on one machine; re-check for drift):**
1. App files: `~/Applications/Orca.AppImage`, `install-orca.sh`, `orca-ide-extracted`, `~/.local/bin/orca-ide`, `~/.local/share/applications/orca-ide.desktop`, `~/.local/share/icons/orca-ide.png`.
2. Orca state: `~/.orca` (per-tool hook scripts), `~/.config/orca` (profiles, browser partition, auth, stats, shell wrappers, terminal history).
3. `orca-cli` skill copies/symlinks in nearly every tool's skills dir: `~/.claude/skills`, `~/.pi/agent/skills`, `~/.agents/skills`, `~/.hermes/skills`, `~/.factory/skills`, `~/.commandcode/skills`, `~/.grok/skills`, `~/.config/devin/skills`. Enumerate: `find ~ -maxdepth 4 -iname orca-cli`.
4. omp/pi extensions: `orca-titlebar-spinner.ts`, `orca-prefill.ts`, `orca-agent-status.ts` under `~/.omp/agent/extensions` AND `~/.pi/agent/extensions`, plus `~/.config/amp/plugins/orca-agent-status.ts`; check `~/.omp/agent/managed-skills` for orca-authored skills (e.g. `orca-mise-config-stomp`).
5. Hook wiring in other tools' JSON — Orca inserts `if [ -f '/home/USER/.orca/agent-hooks/<tool>-hook.sh' ] ...` into every lifecycle event. Found in: `~/.codex/hooks.json`, `~/.gemini/config/hooks.json`, `~/.cursor/hooks.json`, `~/.factory/settings.json`, `~/.commandcode/settings.json`. factory/commandcode/cursor files may be entirely Orca's (safe to reset `"hooks"` to `{}`); codex/gemini mix Orca with unrelated integrations (e.g. `herdr`) — strip only entries containing `orca` via Python `json` load/filter, never sed.
6. Orca-only standalone hook files (just delete): `~/.grok/hooks/orca-status.json(.bak)`, `~/.copilot/hooks/orca.json`.
7. Stale backups: `~/.claude/settings.json.bak` may be a pre-Orca backup — safe to delete once the live config is clean.
8. `~/orca/workspaces/` is real project data (git worktrees), NOT app state — **never delete without asking**; `git status --short` each for uncommitted work, prefer moving to a backup location.
9. Dotfiles bare repo (`~/.dotfiles`): `git --git-dir=~/.dotfiles --work-tree=~ ls-files | grep -i orca`; stage deletions with `git add -A` over a pre-verified `ls-files | grep` list via `xargs` (one bad pathspec fails the whole invocation). Commit surgically-edited hook configs separately from pure deletions (`M` vs `D`).
10. Straggler sweep: `~/.cache/*/*orca*`, `~/.omp/agent/sessions/-orca-workspaces-*`.
11. Re-appearing footprint (second removal, Oct 2026): the app was already gone but leftovers returned because Orca's skill stubs live in `~/.agents/skills/` and are symlinked into claude/pi/grok/commandcode/devin. **`computer-use` and `orchestration` are Orca-only stubs too** (they just run `orca skills get ...`) — remove them together with `orca-cli`. `~/.config/devin/config.json` also carries Orca hooks mixed with `herdr` ones: filter entries whose command contains `orca`, drop events left empty. Search with `grep -rIlw -i orca` (word match; plain `orca` substring-matches "decorate" etc. and floods results).
12. `~/orca/workspaces/*` may have been moved to a backup dir (here `~/Documents/Development/orca-workspace-backup`). Those are git worktrees whose parent repo still lists them as `prunable`; `git worktree prune` in the parent repo (phermata, zep) clears the dead entries but detaches the moved copies from git.

Approach: enumerate first (`find ~ -maxdepth 4 -iname "*orca*"`, `grep -rl "orca"` hook dirs) before deleting; ask before touching workspaces; edit mixed JSON programmatically; commit the removal if dotfiles-tracked so it doesn't resurrect.

_Migrated from: orca-app-full-uninstall_
