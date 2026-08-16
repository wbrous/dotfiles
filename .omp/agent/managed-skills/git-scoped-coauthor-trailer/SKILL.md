---
name: git-scoped-coauthor-trailer
description: "Use when the user wants every commit under specific project folders OR repos owned by a specific remote account (GitHub/GitLab user) to automatically get a Co-authored-by trailer (or similar always-on commit message addition), distinguished between AI-agent-driven commits vs the user's own manual commits, without cluttering ~/ with new dotfiles. Covers git worktrees checked out outside the scoped path, multiple scopes each with a different co-author, scoping by remote URL owner (hasconfig:remote.*.url), and a global Signed-off-by trailer gated on GPG-key presence."
---

## Goal
Auto-append a `Co-authored-by: NAME <email>` trailer to commits in certain project folders OR repos owned by a specific remote account — and only when made by an agent/harness (e.g. oh-my-pi), never when the user commits by hand. Multiple scopes can each have their own distinct co-author, sharing one hook script. A second, independent `Signed-off-by` trailer applies globally (every repo) whenever the commit will actually be GPG-signed — no sudo; the real per-commit human-presence check happens at GPG-signing time via a fingerprint-gated pinentry.

## Key mechanism
`prepare-commit-msg` git hook, scoped via `includeIf` for the co-author trailer; `core.hooksPath` set unconditionally at the top of the real config for the signoff trailer (applies everywhere). Hooks work even for `git commit -m "..."` (unlike `commit.template`, which `-m` bypasses).

## Two scoping signals for the co-author trailer
1. **By local folder path** — `includeIf "gitdir:PATTERN"`. Use for "all repos under `~/Projects/foo/**`".
2. **By remote URL owner** — `includeIf "hasconfig:remote.*.url:PATTERN"`. Use for "repos owned by GitHub/GitLab user `foo`". Requires git 2.36+. Example:
```
[includeIf "hasconfig:remote.*.url:**/wbrous/**"]
	path = ~/.config/git/wbrous-config
```
`**/foo/**` matches any remote URL with a `/foo/` path segment — `https://github.com/foo/repo.git`, `git@github.com:foo/repo.git`, `gitlab.com/foo/repo.git`. Caveat: this also matches forks/any repo with a `foo` path component under a different owner; if the user wants strict owner-only matching, anchor on the full host+owner pattern instead. Both signals can coexist — same hook, same `coauthor-hook.trailer` var, no hook edits needed when adding a scope.

## Multi-scope co-author design: one shared hook, trailer text lives in git config
Don't hardcode the AI co-author trailer text in the hook script — read it from a git config var (`coauthor-hook.trailer`) instead, set per-scope via each `includeIf`'d config file (which now ONLY sets `coauthor-hook.trailer`, not `hooksPath` — that's global, see below). This lets one hook script under `~/.config/git/hooks/` serve any number of scopes, each with a different co-author, without duplicating the script.

Hook checks: `COAUTHOR_TRAILER="$(git config --get coauthor-hook.trailer)"`; only appends when non-empty AND `OMPCODE=1` — so repos with no scope config just no-op, and manual commits within a scoped repo skip this trailer.

Adding a new scope later = one new `~/.config/git/<name>-config` file (just `[coauthor-hook]\n\ttrailer = ...`) + one `includeIf` block appended to the real config. No hook script edits needed.

## Signed-off-by trailer: global (every repo), gated on GPG-key presence, NOT sudo
Superseded an earlier sudo-gated design (`sudo -v` inside the hook) — dropped in favor of gating on whether the commit will actually be GPG-signed:
```sh
GPG_SIGN_ENABLED="$(git config --get commit.gpgsign)"
SIGNKEY="$(git config --get user.signingkey)"
if [ "$GPG_SIGN_ENABLED" = "true" ] && [ -n "$SIGNKEY" ] \
   && gpg --list-secret-keys --with-colons "$SIGNKEY" 2>/dev/null | grep -q '^sec'; then
  SIGNOFF_TRAILER="Signed-off-by: NAME <email>"
  grep -qF "$SIGNOFF_TRAILER" "$MSG_FILE" || printf '\n%s\n' "$SIGNOFF_TRAILER" >> "$MSG_FILE"
fi
```
No `exit 1` on failure here — this block never blocks a commit; it just conditionally appends text. If a specific repo has `commit.gpgsign=false` locally, or the signing key's secret half isn't present, the trailer is silently skipped.

To make this apply to **every repo on the machine**: put `core.hooksPath = ~/.config/git/hooks` unconditionally at the top of the user's real `~/.config/git/config` (not inside any `includeIf` block), and make sure `commit.gpgsign = true` + `user.signingkey` are also set globally.

## Fingerprint-gated GPG key unlock (the real "just a tap" mechanism)
The current, correct architecture uses **polkit + pkexec + a root-only passphrase file + hyprpolkitagent** (NOT the older secret-tool/fprintd-verify/zenity wrapper). Details:
- Passphrase lives ONLY in `/etc/gpg-fingerprint/passphrase` (root:root 600). No user-readable keyring, no shell history, no transcript.
- A root-only reader `/usr/local/bin/gpg-fingerprint-read` (root:root 755) does `cat /etc/gpg-fingerprint/passphrase`.
- A polkit action `com.gir0fa.gpg-fingerprint-read` (policy at `/usr/share/polkit-1/actions/com.gir0fa.gpg-fingerprint-read.policy`, `auth_admin` defaults) gates that reader.
- The pinentry wrapper `~/.local/bin/pinentry-fprintd` (root:root 755) calls `pkexec /usr/local/bin/gpg-fingerprint-read` on GETPIN, percent-encodes the result (`s/%/%25/g; s/\r/%0D/g`), and replies `D <esc>\nOK\n`. On polkit auth failure it replies `ERR 83886179 cancelled`.
- `~/.gnupg/gpg-agent.conf` points `pinentry-program /home/USER/.local/bin/pinentry-fprintd` with `default-cache-ttl 0` and `max-cache-ttl 0` (fresh prompt every signing op).
- The GUI fingerprint/password prompt is served by `hyprpolkitagent` (systemd user service), which bridges polkit auth to PAM fingerprint (pam_fprintd) with password fallback.

Critical: **never run `gpg-fingerprint-read` (or anything that echoes the passphrase) from an agent session** — it prints the secret into the transcript. Verify only passphrase *length*, never value. Never put the passphrase into any command's argv (`rg -F "$S"`, `grep "$S"`, etc.) — the kernel audit hook logs full command lines to the journal, leaking it again.

### Rotating the passphrase without ever knowing it (loopback pinentry)
Temporarily add `allow-loopback-pinentry` to gpg-agent.conf, then use `gpg --batch --pinentry-mode loopback` to feed old/new passphrases via fd, never argv. For `--quick-generate-key`, `--passphrase "$NEW"` works in batch loopback (verified). For `--change-passphrase`, feed `old\nnew\nnew\n` via `--passphrase-fd 0`. Restore the strict config (drop loopback) afterward and `gpgconf --kill gpg-agent` — on a systemd-supervised agent (`--supervised`), `gpgconf --kill` just respawns it; use `systemctl --user restart gpg-agent.service` to reliably pick up pinentry changes.

### Deleting the passphrase from the journal
The journal is binary — you cannot `sed`/`perl` a string out of it. Remove whole entries/files instead: `sudo journalctl --vacuum-time=1s` deletes all archived journals (the previous boot's leak). Note: the *active* journal (`/var/log/journal/*/system.journal`, `user-1000.journal`) is current-boot only and rotates on the next vacuum. `journalctl --rotate` + `--vacuum-time=1s` flushes and wipes it.

## Honest security framing — discuss with the user before implementing
- `Signed-off-by:` is a **plaintext trailer, not a cryptographic signature** — the real non-repudiation comes from the GPG signature, not the trailer text.
- The gate defends against **silent unattended/automated misuse**, not an attacker with physical access to the unlocked laptop. Say this explicitly.
- Bypass: `git commit --no-verify` skips the message hook (trailers only; the GPG signature itself is separate and not skippable via `--no-verify`).

## Root-locking files (optional hardening)
`sudo chown root:root FILE; sudo chmod 755 FILE` (scripts) or `chmod 644` (configs) for tamper resistance. To update a root-locked file, write new content to a scratch path then `sudo cp` it over and re-apply ownership/mode. The `bash` tool handles the interactive sudo prompt (password/fingerprint) fine.

## Where files live — do NOT scatter into ~
1. Check `~/.config/git/config` exists first (XDG git config). NEVER create `~/.gitconfig` if it already exists.
2. Put everything under `~/.config/git/`:
   - `hooks/prepare-commit-msg` — the ONE shared hook (config-driven co-author + global GPG-gated signoff); optionally root-locked
   - `<scope>-config` — one small file per scope, just `[coauthor-hook]\n\ttrailer = Co-authored-by: NAME <email>`
   - `[core]\n\thooksPath = ~/.config/git/hooks` unconditionally at top of the real config
   - one `includeIf` block per scope (either `gitdir:` or `hasconfig:remote.*.url:`), appended, never clobbering
   - `~/.local/bin/pinentry-fprintd` + `~/.gnupg/gpg-agent.conf` for the fingerprint-gated unlock
3. Only fall back to `~/.gitconfig` if the user truly has no `~/.config/git/config` yet.
4. Relocate any stray `~/.gitconfig`/`~/.githooks/` files into `~/.config/git/` if they were created by mistake.

## Verification
Test the full matrix and clean up after: outside-scope repo (signoff only), in-scope omp-style commit (both trailers), in-scope manual commit (`env -u OMPCODE`, signoff only). For remote-owner scoping, also test the negative case (a repo with a non-matching remote returns no `coauthor-hook.trailer`). Confirm the signature is real via `git log --show-signature -1` (`gpg: Good signature from "..."`).
