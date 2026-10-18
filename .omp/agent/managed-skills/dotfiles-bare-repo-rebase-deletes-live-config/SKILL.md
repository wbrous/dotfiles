---
name: dotfiles-bare-repo-rebase-deletes-live-config
description: "dotfiles push / git-resign-own fails with gpg \"No secret key\", fresh empty pubring.kbx, .bak files, or tracked config vanishing mid-rebase; before tracking any signing-critical or runtime-critical file at its live path in the bare ~/.dotfiles repo."
---

## Hazard

The bare dotfiles repo uses `work-tree=$HOME`. `dotfiles push` -> `git-push-resign` -> `git-resign-own` runs `git rebase --exec` starting at `<oldest-unsigned-commit>~1`. Rebase checks out OLDER trees into `$HOME`, so any file that is tracked at its live path but absent from those older trees is **deleted from disk mid-push**. Git leaves `.bak` copies when it later restores them.

Symptom seen: after adding `~/.gnupg/gpg-agent.conf`, `~/.gnupg/common.conf` (`use-keyboxd`), `~/.local/bin/pinentry-fprintd` in a new commit, `dotfiles push` failed with:
`gpg: keybox '~/.gnupg/pubring.kbx' created` / `No secret key` / `INV_SGNR` / `failed to write commit object`.
Cause: `use-keyboxd` + pinentry config vanished, gpg made a new empty local keyring. Key material in `private-keys-v1.d` was never touched. Only happens when the rebase replays a commit older than the one that added the file.

## Rule

NEVER track runtime-critical files (gpg config, pinentry, git hooks/config used for signing, anything the push itself depends on) at their live path in the bare repo. Track a copy under a non-live dir (e.g. `~/.local/share/<topic>/`) and have an install script copy it to the live path.

## Recovery

1. `dotfiles rebase --abort` (restores working tree; files come back).
2. Remove strays: `~/.gnupg/*.bak`, the empty 32-byte `~/.gnupg/pubring.kbx`.
3. `gpgconf --kill all; gpg --list-secret-keys` to confirm the key is visible again.
4. Copy files to the safe dir, `dotfiles rm --cached <live paths>` (files stay on disk), `dotfiles add <safe dir>`.
5. If the bad commit is unpushed and HEAD: `dotfiles commit --amend --no-gpg-sign` (signing is done at push time; avoids a fingerprint prompt).

## Verify without signing

Replay the same rebase shape with an exec that asserts files exist and hashes are unchanged:
`GIT_DIR=~/.dotfiles GIT_WORK_TREE=~ git rebase --no-gpg-sign --rebase-merges --exec '<check files exist>' <oldest-unsigned>~1`
then `sha256sum -c` against a pre-rebase sum file. Untested remainder: the real fingerprint prompt on `dotfiles push`.

## Fingerprint GPG layout (this machine)

- Tracked: `~/.local/share/gpg-fingerprint/{gpg-agent.conf,common.conf,sshcontrol,pinentry-fprintd}` and `~/.local/bin/install-gpg-fingerprint`.
- Installer deploys them root-owned to `~/.gnupg/*` and `~/.local/bin/pinentry-fprintd`, plus root-only `/usr/local/bin/gpg-fingerprint-read`, the polkit policy `com.gir0fa.gpg-fingerprint-read.policy`, and prompts (hidden) for `/etc/gpg-fingerprint/passphrase` only if missing.
- Live `~/.gnupg/gpg-agent.conf` is root-owned; a user edit needs chown first.
- Same hazard still applies to `~/.config/git/config` and `~/.config/git/hooks/*` (tracked at live paths), latent until a rebase replays a commit older than their addition.
- Amend/edit tools: when edits report "stale file hash", re-validate with `bash -n` and shellcheck.
