---
name: git-prepush-resign-unpushed-unsigned
description: "Use when setting up or debugging the global pre-push hook that GPG-resigns unpushed unsigned commits before push (resign-then-repush), the dev-time unsigned vs push-time signed split (commit.gpgsign=false on ~/.dotfiles), the gpgsig-header detection gotcha (not %G?), the rebase --rebase-merges --exec amend mechanics, the all-zeros/new-branch --root case, and headless testing with a throwaway no-passphrase GPG key."
---

# git-prepush-resign-unpushed-unsigned

Set up or debug the global `pre-push` hook that GPG-resigns **unpushed unsigned** commits right before they leave the machine, using a resign-then-repush flow (the hook aborts the first push after resigning; the user re-runs it).

## Why this pattern exists (the dev/push split)

The dotfiles bare repo (`~/.dotfiles`) has `commit.gpgsign=false` set **locally** (`git --git-dir=~/.dotfiles config --local commit.gpgsign false`), so managed-skill auto-commits and survey commits never trigger the fingerprint-gated pinentry (user may not be at the machine). But at `git push` time the user IS present, so unpushed unsigned commits get GPG-signed then. Already-pushed commits are NEVER rewritten.

Hook lives at `~/.config/git/hooks/pre-push` (global via `core.hooksPath`, applies to every repo) and is tracked in dotfiles as `.config/git/hooks/pre-push`.

## How it works

`pre-push` receives on stdin, one line per pushed ref:
```
<local-ref> <local-oid> <remote-ref> <remote-oid>
```

Per ref:
1. Skip deletions (`local-oid` all-zeros).
2. Determine the unpushed range base:
   - `remote-oid` all-zeros (brand-new branch) → **`--root`** (every local commit is unpushed; sign from the root).
   - Otherwise → `remote-oid..local-oid`; empty range = up to date, skip.
3. Keep only **unsigned** commits.
4. If any: resign with one rebase pass, then **exit 1** to abort the in-flight push.

## Critical detection detail: check `gpgsig` header, NOT `%G?`

```sh
git cat-file -p "$sha" | grep -q '^gpgsig' || echo "$sha"   # unsigned
```

`git log -1 --format='%G?'` returns `N` for no signature but **`E` (can't verify — missing/unknown key) for a signed commit whose key isn't in the current keyring** (e.g. different `GNUPGHOME`). Using `%G?` would wrongly skip those signed commits and leave them unsigned. The header check is key-independent and correct.

## Resign command

```sh
git rebase $base_arg --rebase-merges --exec 'git commit --amend --no-edit -S' --autostash
```

- `--rebase-merges` preserves merge topology (plain rebase flattens merges).
- `-S` signs each replayed commit with `user.signingkey` (default key), triggering the fingerprint pinentry per commit.
- `--autostash` protects dirty worktrees.
- On failure (conflicts): print a clear "resolve conflicts, then re-run git push" message and exit 1.

## Flow: resign then re-push (NOT auto re-exec)

After resigning, exit 1 with:
```
pre-push: re-signed N unpushed unsigned commit(s) on <ref>.
pre-push: fingerprint was required per commit (gpg cache-ttl=0).
pre-push: THIS push was ABORTED so the rewritten refs take effect.
pre-push: re-run the push command to push the now-signed commits.
```

The user re-runs `git push`; the second run finds nothing unsigned and pushes cleanly.

**Why not auto-re-exec inside the hook?** Rewriting mid-transport is unsafe (git already resolved the refs it's about to send). Reconstructing the push from stdin loses original argv (e.g. `--force`) and risks nested errors. The user explicitly chose two-step over one-command auto-re-push.

**Multi-ref pushes:** `break` after the first resign pass — the re-push recomputes ranges fresh and fixes remaining branches over subsequent aborts.

## Caveats / known behaviors

- `gpg-agent.conf` here sets `default-cache-ttl 0` / `max-cache-ttl 0` → **N unsigned commits = N fingerprint taps** at push time. Fine for 1–3 dotfiles commits; batch pushes of many new commits tap per commit. This is the deliberate per-op auth posture; don't "fix" by raising ttl without asking.
- A re-entry guard env var (`GIT_PRE_PUSH_RESIGNED=1`) is belt-and-suspenders; normally unreachable since we abort after resigning.
- The `Signed-off-by` trailer disappears from dotfiles commits once `commit.gpgsign=false` (that trailer is gated on actual GPG signing in `prepare-commit-msg`); `Co-authored-by: wbrous-dev-ai` is unaffected (gated on `OMPCODE=1`).

## Headless verification technique (no fingerprint tap needed)

Fake gpg binaries DO NOT work — git rejects their output ("gpg failed to sign the data"). Use a throwaway **no-passphrase** GPG key in an isolated `GNUPGHOME`:

```sh
rm -rf /tmp/gnupg && mkdir -p /tmp/gnupg && chmod 700 /tmp/gnupg
export GNUPGHOME=/tmp/gnupg
cat > /tmp/keyparams <<'EOF'
%no-protection
Key-Type: eddsa
Key-Curve: ed25519
Key-Usage: sign
Name-Real: Test Signer
Name-Email: test@test.t
Expire-Date: 0
%commit
EOF
gpg --batch --generate-key /tmp/keyparams
FP=$(gpg --list-secret-keys --with-colons | awk -F: '/^fpr/{print $10; exit}')
git config user.signingkey "$FP"
```

Then in a scratch repo (bare remote, 2–3 unsigned commits): `git push origin main` → expect hook to resign + abort; second push → succeeds; verify every commit has a `gpgsig` header and `git log --show-signature` validates. Also test the new-branch case (empty remote → `--root` path).
