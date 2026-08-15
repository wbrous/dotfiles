---
name: git-scoped-coauthor-trailer
description: "Use when the user wants every commit under specific project folders (e.g. all repos under ~/Projects/zep/* or ~/Projects/phermata/*) to automatically get a Co-authored-by trailer (or similar always-on commit message addition), and wants it distinguished between AI-agent-driven commits vs the user's own manual commits, without cluttering ~/ with new dotfiles. Also covers git worktrees (e.g. orca-managed worktrees) checked out outside the scoped path, adding multiple scopes each with a different co-author, and layering an independent sudo-gated Signed-off-by trailer that applies to every commit regardless of who/what made it."
---

## Goal
Auto-append a `Co-authored-by: NAME <email>` trailer to commits in certain project folders only — and only when made by an agent/harness (e.g. oh-my-pi), never when the user commits by hand in the same folder. Multiple scopes (e.g. `~/Projects/zep/**` and `~/Projects/phermata/**`) can each have their own distinct co-author, sharing one hook script. A second, independent `Signed-off-by` trailer applies globally (every repo on the machine, not just scoped folders) whenever the commit will actually be GPG-signed — no sudo involved; the real per-commit human-presence check happens at GPG-signing time via a fingerprint-gated pinentry, not in the git hook.

## Key mechanism
`prepare-commit-msg` git hook, scoped via `includeIf "gitdir:PATTERN"` for the co-author trailer; `core.hooksPath` set unconditionally at the top of the real config for the signoff trailer (applies everywhere). Hooks work even for `git commit -m "..."` (unlike `commit.template`, which `-m` bypasses).

## Multi-scope co-author design: one shared hook, trailer text lives in git config
Don't hardcode the AI co-author trailer text in the hook script — read it from a git config var (`coauthor-hook.trailer`) instead, set per-scope via each `includeIf`'d config file (which now ONLY sets `coauthor-hook.trailer`, not `hooksPath` — that's global, see below, so duplicating it per-scope is redundant). This lets one hook script under `~/.config/git/hooks/` serve any number of scoped folders, each with a different co-author, without duplicating the script.

Hook checks: `COAUTHOR_TRAILER="$(git config --get coauthor-hook.trailer)"`; only appends when non-empty AND `OMPCODE=1` — so repos with no scope config just no-op, and manual commits within a scoped repo skip this trailer.

Adding a new co-author scope later = one new `~/.config/git/<name>-config` file (just `[coauthor-hook]\n\ttrailer = ...`) + one `includeIf` block appended to the real config. No hook script edits needed.

## Signed-off-by trailer: global (every repo), gated on GPG-key presence, NOT sudo
Superseded an earlier sudo-gated design (`sudo -v` inside the hook) — dropped in favor of gating on whether the commit will actually be GPG-signed, since the real authentication now happens at GPG-signing time (see fingerprint section below), not in the commit-message hook:
```sh
GPG_SIGN_ENABLED="$(git config --get commit.gpgsign)"
SIGNKEY="$(git config --get user.signingkey)"
if [ "$GPG_SIGN_ENABLED" = "true" ] && [ -n "$SIGNKEY" ] \
   && gpg --list-secret-keys --with-colons "$SIGNKEY" 2>/dev/null | grep -q '^sec'; then
  SIGNOFF_TRAILER="Signed-off-by: NAME <email>"
  grep -qF "$SIGNOFF_TRAILER" "$MSG_FILE" || printf '\n%s\n' "$SIGNOFF_TRAILER" >> "$MSG_FILE"
fi
```
No `exit 1` on failure here — this block never blocks a commit; it just conditionally appends text. If a specific repo has `commit.gpgsign=false` locally, or the signing key's secret half isn't present, the trailer is silently skipped (correct: don't claim "signed off" on a commit that won't actually be GPG-signed).

To make this apply to **every repo on the machine** (not just scoped folders): put `core.hooksPath = ~/.config/git/hooks` unconditionally at the top of the user's real `~/.config/git/config` (not inside any `includeIf` block), and make sure `commit.gpgsign = true` + `user.signingkey` are also set globally (usually already the case if the user signs commits). The co-author `includeIf` blocks stay as-is — they only gate the co-author trailer's *text availability*, not `hooksPath`, since that's now global.

## Fingerprint-gated GPG key unlock (the real "just a tap" mechanism)
GPG has no native biometric feature — there's no `gpg --add-fingerprint`. Two real approaches; discuss the tradeoff with the user explicitly before implementing either, don't just silently pick one:
1. **Hardware token** (e.g. YubiKey Bio) — private key never leaves the token, biometric unlocks it in hardware. Requires buying hardware; most robust; out of scope for a pure software fix.
2. **Software gate via custom `pinentry-program`** — the existing GPG secret key stays as-is; a wrapper script intercepts gpg-agent's passphrase prompt (the `pinentry` protocol) and requires `fprintd-verify` (the user's already-OS-enrolled fingerprint — check via `fprintd-list "$USER"`) before releasing the real passphrase.

Within option 2, there's a further tradeoff to explicitly ask the user about (don't assume):
- **Empty passphrase, fingerprint-only, no fallback**: simplest, truly zero-friction, but if the wrapper is ever removed/misconfigured, the private key sits on disk with **zero protection** — worse blast radius than a locked hook file, since anyone with filesystem read access to `~/.gnupg` could sign as the user with no auth at all.
- **Real passphrase kept, fingerprint-gated with typed fallback after N failed scans** (what was actually built here, N=3): the real, non-empty passphrase is seeded once into the OS-protected secret store (`gnome-keyring` via `secret-tool`), and a custom pinentry script tries `fprintd-verify` up to N times; on success it retrieves and hands back the real passphrase from the keyring (never displayed/typed); after N consecutive failures it falls back to reading a typed passphrase directly from `/dev/tty`. This keeps genuine passphrase protection intact (nothing is ever *actually* passphrase-less) while making the common case a single tap, and avoids the failure mode of the empty-passphrase design — if the wrapper is bypassed, the key still requires the real passphrase, gpg just won't auto-fill it from fingerprint anymore.

**Critical: never have the user paste their real GPG passphrase into an agent chat/session.** Seeding the secret store must be done by the user themselves in their own terminal:
```sh
secret-tool store --label="GPG fingerprint-gated passphrase" service gpg-fingerprint-unlock account "$USER"
```
This prompts securely (no echo, not logged anywhere the agent can see) — verify it landed via `secret-tool lookup service gpg-fingerprint-unlock account "$USER" >/dev/null 2>&1` (exit 0 = present), never by trying to read the value itself.

### Custom pinentry script (minimal Assuan protocol handler)
gpg-agent's `pinentry-program` protocol is a simple line-based handshake: the pinentry sends `OK Pleased to meet you` immediately on startup, then for each line gpg-agent sends (`SETDESC`, `SETPROMPT`, `OPTION`, etc.) it just needs `OK\n` back — except `GETPIN`, which must respond with a `D <percent-encoded-secret>\nOK\n` pair, and `BYE`, which should reply `OK closing connection` then exit. No off-the-shelf tool does "fprintd-first, real-passphrase-fallback" — hand-roll it:
```sh
#!/bin/bash
set -u
SECRET_SERVICE="gpg-fingerprint-unlock"
SECRET_ACCOUNT="${USER:-$(id -un)}"
MAX_ATTEMPTS=3

printf 'OK Pleased to meet you\n'

while IFS= read -r line; do
  cmd="${line%% *}"
  case "$cmd" in
    GETPIN)
      ok=0
      attempt=1
      while [ "$attempt" -le "$MAX_ATTEMPTS" ]; do
        fprintd-verify >/dev/null 2>&1 && { ok=1; break; }
        attempt=$((attempt + 1))
      done
      [ "$ok" = 1 ] && pin="$(secret-tool lookup service "$SECRET_SERVICE" account "$SECRET_ACCOUNT" 2>/dev/null || true)"
      if [ -z "${pin:-}" ]; then
        # N failed scans (or nothing stored yet) -> typed fallback via controlling tty, NOT via re-delegating
        # mid-protocol to a real pinentry binary (that would require replaying the handshake it expects
        # from scratch — much simpler to just prompt inline).
        printf 'Fingerprint failed %s times — enter GPG passphrase: ' "$MAX_ATTEMPTS" > /dev/tty 2>/dev/null
        stty -echo < /dev/tty 2>/dev/null
        IFS= read -r pin < /dev/tty
        stty echo < /dev/tty 2>/dev/null
        printf '\n' > /dev/tty 2>/dev/null
      fi
      if [ -n "${pin:-}" ]; then
        esc=$(printf '%s' "$pin" | sed 's/%/%25/g; s/\r/%0D/g')  # Assuan D-line percent-encoding
        printf 'D %s\n' "$esc"
        printf 'OK\n'
      else
        printf 'ERR 83886179 No passphrase available\n'
      fi
      unset pin
      ;;
    BYE) printf 'OK closing connection\n'; exit 0 ;;
    *) printf 'OK\n' ;;
  esac
done
```
Put it at `~/.local/bin/pinentry-fprintd`, `chmod +x`. Wire it up via `~/.gnupg/gpg-agent.conf`:
```
pinentry-program /home/USER/.local/bin/pinentry-fprintd
default-cache-ttl 0
max-cache-ttl 0
```
`default-cache-ttl 0` / `max-cache-ttl 0` are required to get a fresh fingerprint prompt on *every* signing operation — without them gpg-agent caches the unlocked key and skips pinentry entirely for subsequent commits within the cache window, defeating "a tap every commit." After editing, `gpgconf --kill gpg-agent` (it respawns lazily on next use, or `gpg-agent --daemon --pinentry-program <path>` to force-start immediately) — `gpgconf --reload gpg-agent` alone is not sufficient to pick up a changed `pinentry-program` path in all cases; kill-and-respawn is the reliable path.

Verify with `git log --show-signature -1` after a real commit — should show `gpg: Good signature from "..."`, not just a trailer claiming signed-off status with no real signature backing it.

## Honest security framing — discuss this with the user before implementing, don't just build it silently
- `Signed-off-by:` is a **plaintext trailer, not a cryptographic signature** on its own — the actual non-repudiation comes from the GPG signature (`commit.gpgsign=true` + the fingerprint-gated key unlock above), not from the trailer text. Keep these two facts distinct when explaining to the user.
- Whatever gate is chosen (sudo, fprintd, hardware token) shares the same underlying trust boundary as "physical access to the unlocked laptop" — none of these mechanisms defend against an attacker who already has that. What they actually defend against is **silent unattended/automated misuse** (e.g. a script or agent process signing something without a live human tap) — say this explicitly, don't oversell it as attacker-proof.
- Bypass that survives regardless of hook/pinentry setup: `git commit --no-verify` skips the message hook entirely (only affects the co-author/signoff *trailers*, not the GPG signature itself, which is a separate git mechanism enforced by `commit.gpgsign` and isn't skippable via `--no-verify`).

## Root-locking the hook file so it's only sudo-editable (optional hardening, independent of the above)
```sh
sudo chown root:root ~/.config/git/hooks/prepare-commit-msg
sudo chmod 755 ~/.config/git/hooks/prepare-commit-msg   # owner(root) rwx, everyone else r-x — still executable by git as the normal user, not writable
```
The regular `bash` tool handles the interactive sudo prompt (password or fingerprint) fine — no PTY workaround required; a prior apparent failure in this flow was just a missed/late fingerprint scan, not a tooling limitation. To update a root-locked hook file later, write the new content to a scratch path first, then `sudo cp` it over the locked file and re-apply `chown root:root` + `chmod 755` (the copy needs re-owning even if the source had normal permissions).

## Where files should live — do NOT scatter into ~
1. Check first: does `~/.config/git/config` already exist (XDG git config)? Many users already use this instead of `~/.gitconfig`. NEVER create `~/.gitconfig` if `~/.config/git/config` already exists — that's a redundant, confusing duplicate config file. If both `~/.gitconfig` and `~/.config/git/config` happen to already exist independently, don't touch/delete either without asking; just add to whichever the user actually uses (check both for existing `[user]` section).
2. Put everything under the existing git config dir:
   - `~/.config/git/hooks/prepare-commit-msg` — the ONE shared hook script (config-driven co-author trailer + global GPG-gated signoff, see above); optionally root-locked
   - `~/.config/git/<scope>-config` — one small file per co-author scope, just `[coauthor-hook]\n\ttrailer = Co-authored-by: NAME <email>` (no `hooksPath` — that's global now)
   - `[core]\n\thooksPath = ~/.config/git/hooks` unconditionally at the top of the real config (applies everywhere, for the signoff trailer)
   - Append (don't clobber) one `[includeIf "gitdir:PATTERN"]` block per co-author scope, `path = ~/.config/git/<scope>-config`, to the user's real config file.
   - `~/.local/bin/pinentry-fprintd` + `~/.gnupg/gpg-agent.conf` for the fingerprint-gated GPG unlock, if that's in scope.
3. Only fall back to creating `~/.gitconfig` if the user truly has no `~/.config/git/config` yet.
4. If you mistakenly create files in `~` (e.g. `~/.gitconfig`, `~/.githooks/`) when `~/.config/git/config` already existed, relocate them into `~/.config/git/` and delete the stray home-root files/dirs — don't leave duplicates.
5. If the scoped project folder doesn't exist yet, just `mkdir -p` it — the includeIf pattern matches by path regardless of whether anything's inside yet.

## Hook script template (current, shared across all scopes)
```sh
#!/bin/sh
MSG_FILE="$1"
COMMIT_SOURCE="$2"

case "$COMMIT_SOURCE" in
  merge) exit 0 ;;
esac

# --- 1. AI co-author trailer (omp-only, per-scope text via git config) ---
COAUTHOR_TRAILER="$(git config --get coauthor-hook.trailer)"
if [ -n "$COAUTHOR_TRAILER" ] && [ "$OMPCODE" = "1" ]; then
  grep -qF "$COAUTHOR_TRAILER" "$MSG_FILE" || printf '\n%s\n' "$COAUTHOR_TRAILER" >> "$MSG_FILE"
fi

# --- 2. Signed-off-by, gated on an actually-usable GPG signing key (every repo, no scoping) ---
GPG_SIGN_ENABLED="$(git config --get commit.gpgsign)"
SIGNKEY="$(git config --get user.signingkey)"
if [ "$GPG_SIGN_ENABLED" = "true" ] && [ -n "$SIGNKEY" ] \
   && gpg --list-secret-keys --with-colons "$SIGNKEY" 2>/dev/null | grep -q '^sec'; then
  SIGNOFF_TRAILER="Signed-off-by: NAME <email>"
  grep -qF "$SIGNOFF_TRAILER" "$MSG_FILE" || printf '\n%s\n' "$SIGNOFF_TRAILER" >> "$MSG_FILE"
fi
```
`chmod +x` it. NEVER hardcode a specific co-author NAME/email in this file — that belongs in each scope's `coauthor-hook.trailer` config value. The signoff identity, if fixed across all repos, is fine to hardcode directly since it doesn't vary.

## Verification
Test the full matrix and clean up test repos after: an entirely-outside-scope repo (should get signoff only, if GPG configured, no co-author, no sudo prompt), an in-scope omp-style commit (both trailers), and an in-scope manual commit (`env -u OMPCODE`, signoff only).
```sh
mkdir -p /tmp/t && cd /tmp/t && git init -q
echo hi > f && git add f
git commit -q -m "outside-scope commit" </dev/null
git log -1 --format=%B    # Signed-off-by only

mkdir -p ~/Projects/<scope>/t && cd ~/Projects/<scope>/t && git init -q
echo hi > f && git add f
git commit -q -m "scoped omp commit" </dev/null
git log -1 --format=%B    # both trailers

echo hi2 >> f && git add f
env -u OMPCODE git commit -q -m "scoped manual commit" </dev/null
git log -1 --format=%B    # Signed-off-by only
cd / && rm -rf /tmp/t ~/Projects/<scope>/t
```
Confirm the signature is real, not just a trailer with nothing backing it: `git log --show-signature -1` should show `gpg: Good signature from "..."`.

Sudo/fingerprint credential caching means back-to-back test commits may not re-prompt — expected behavior of whichever caching layer is in play (sudo `timestamp_timeout`, or `gpg-agent` cache-ttl if left non-zero), not a hook bug. Verify the fingerprint-fallback path too (deliberately fail `fprintd-verify` 3x, or test with `default-cache-ttl 0` set so every commit genuinely reprompts) — don't just verify the happy path.

Worktree test: `git worktree add /tmp/some-wt-outside-scope -b test-branch` from a main repo under a scoped path, then check `git -C /tmp/some-wt-outside-scope config --get core.hooksPath` — should still resolve, proving the co-author scope follows the main repo's `.git`, not the worktree checkout location (moot for the signoff trailer now, since `hooksPath` is global).

`git init` populates `.git/hooks/*.sample` (~13-14 sample files) plus objects/refs/etc — don't mistake this git-internal boilerplate for stray files created by the agent; just remember to `rm -rf` test repos after verifying.
