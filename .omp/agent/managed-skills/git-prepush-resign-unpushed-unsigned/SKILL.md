---
name: git-prepush-resign-unpushed-unsigned
description: "Use when setting up or debugging the global pre-push hook that GPG-resigns unpushed unsigned commits before push, or the one-command git push/dotfiles push flow — covers the fundamental pre-push limitation (a hook alone cannot complete a push in one command; stale-SHA \"remote rejected\" error even though the re-invoked push lands), the GIT_PRE_PUSH_RESIGNED re-entry guard, the shell-level git() function routing every git push through ~/.local/bin/git-push-resign (generic, any repo) and dotfiles() routing through the same script via GIT_DIR/GIT_WORK_TREE, gpg-agent default-cache-ttl 300 for single-fingerprint batches, the dev-time unsigned vs push-time signed split (commit.gpgsign=false on ~/.dotfiles), the new-branch/no-upstream footgun where resigning is silently skipped, headless testing with a throwaway no-passphrase GPG key, which pieces of this setup are dotfiles-synced vs machine-local when cloning onto a new machine, and the resign rebase's cascading-touch requirement (a cancelled/timed-out fingerprint scan on one commit halts the whole rebase — 'operation cancelled' just means retry, not corruption; each subsequent commit resign needs its own touch, it is NOT one batched scan despite the log line saying \"one fingerprint scan\"; a same-file merge conflict can also appear mid-rebase if two auto-committed edits to the same managed-skill file were picked up in different original commits — resolve via conflict:// blocks, git add, then keep running git rebase --continue, touching the sensor each time, until it reports done)."
---

## Resign-rebase mid-flight failure modes (learned from live incident)

The `dotfiles push` / `git-push-resign` flow rebases unpushed commits, re-signing each via `exec git commit --amend --no-edit -S`. Two failure modes observed in one session, both non-fatal and recoverable:

### 1. "cannot rebase: You have unstaged changes"

If the working tree has uncommitted modifications (e.g. an app wrote to a tracked dotfile like `.config/Omacom/omawrite.conf` or `.omp/agent/last-changelog-version` between commits), the resign rebase aborts immediately with this error before touching gpg at all. Fix: `dotfiles commit -a -m "update"` (or similar) to clear the tree, then `dotfiles push` again.

### 2. "gpg: signing failed: Operation cancelled" mid-rebase

The log line `git-push: re-signing N unpushed unsigned commit(s) (one fingerprint scan)...` is misleading — it does NOT mean one touch covers the whole batch during an interactive rebase. Each `exec git commit --amend --no-edit -S` step is a **separate** gpg-agent signing operation; if the user doesn't touch the sensor in time (or the touch doesn't register), gpg reports `Operation cancelled` and the rebase halts cleanly at that step (nothing corrupted — this is by design, same as any failed rebase exec step).

Recovery: the user must run `git rebase --continue` (via their dotfiles alias, or `git --git-dir=$HOME/.dotfiles --work-tree=$HOME rebase --continue`) themselves, in their own terminal, touching the fingerprint sensor each time a new pinentry prompt appears — repeat once per remaining commit. An agent cannot do this on their behalf (no physical sensor access); the correct move is to explain the state clearly and hand control back, not to attempt automation.

To check exactly how many steps remain and confirm nothing is corrupted, read `git status` (interactive rebase state shows "Last commands done" / "Next commands to do" with an exact remaining count) — this is safe for an agent to inspect read-only at any point without disturbing the paused rebase.

### 3. Same-file merge conflict from two prior auto-committed edits

If a managed-skill's SKILL.md (or any tracked file) was auto-committed twice in the unpushed history — e.g. once by an earlier agent turn, once by a later one, both touching overlapping lines — the rebase's `pick` step for the later commit can produce a real content conflict against the (now-resigned, replayed) earlier commit, independent of the signing issue. This is a normal git conflict, not a resign-flow bug: resolve it like any other (`conflict://<N>` blocks if the harness's write tool exposes them, else manual `<<<<<<<` markers), `git add` the resolved file, then continue with `git rebase --continue` — which will likely immediately hit the next commit's resign-touch prompt, so warn the user to expect that next.

An agent CAN and should resolve pure content conflicts directly (no physical dependency), but MUST hand back control for every subsequent `exec` (resign) step.
