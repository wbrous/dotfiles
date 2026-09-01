---
name: git-commit-gpg-fingerprint-timeout-retry
description: "Use when a git commit invoked from an agent bash tool hangs indefinitely or times out on a system with fingerprint-gated GPG commit signing (commit.gpgsign=true + fprintd/pinentry) — the commit blocks silently (no visible prompt in captured output) waiting for a physical fingerprint touch, then after ~2 minutes fails with gpg: signing failed: Timeout / exit 128 / \"failed to write commit object\". Also covers why a background bash tool call can't surface this and why polling via hub in a real PTY, with explicit user prompts to touch the sensor, is required."
---

# Git commit + fingerprint-gated GPG signing

## Symptom

`git commit` from an agent bash tool hangs silently for ~2 minutes, then dies with:

```
gpg: signing failed: Timeout
fatal: failed to write commit object
```

`commit.gpgsign=true` + fingerprint-gated pinentry (fprintd) means git is waiting for a physical fingerprint touch that the backgrounded bash tool can never surface. A background bash call will hang until the ~2 min GPG timeout; nothing useful appears in captured output.

## Correct procedure

1. Do NOT run `git commit` in a plain/bash background tool when signing is needed. It will look hung; it is waiting for a human.
2. Run the commit through **hub start in a real PTY** so the flow is observable, then explicitly tell the user to **touch the fingerprint sensor**:
   ```
   hub start name=commit ... bash -c "cd /repo && WATERMARKS_REMOVER_DISABLE=1 git commit ..."
   hub wait name=commit (timeout 60-90s)
   ```
   The user touches the sensor; gpg-agent signs; commit lands. If the touch never comes, gpg fails after ~2 min (exit 128) — retry, don't assume corruption.
3. After a successful login, subsequent commits may still time out: gpg-agent caches the key for only `default-cache-ttl` (often 300s), so each new commit can need a fresh fingerprint touch.
4. **Pitfall — commit message quoting through the hub `bash -c` wrapper**: a `-m "..."` message containing parens/newlines (e.g. `sendMessage(threadId, text)`) breaks the shell wrapper: pathspec errors (`error: pathspec 'pin' did not match`) or `syntax error near unexpected token ('`. Use `git commit -F /tmp/commit_msg.txt` (write the message to a temp file first) instead of `-m`. This is mandatory for multi-line/bullet messages with parens.

## Why PTY and not a background tool

- A backgrounded bash tool has no controlling TTY; the pinentry GUI prompt (notify-send/zenity) still appears on the user's desktop, but the bash tool's captured output shows nothing — looks like a hang.
- `hub start` gives a real PTY, so if a fallback terminal pinentry is configured it can render; more importantly it lets the agent poll `hub logs`/`hub wait` and confirm where in the flow the commit is.
- Polling via hub with explicit user prompts ("touch the sensor now") is the only reliable way to get the commit through without a desktop GUI prompt going unanswered.

## Local vs global state

- `commit.gpgsign=true` is usually global (every repo); a repo may opt out locally (`git config commit.gpgsign false`) but that defeats the security intent — prefer the PTY + touch flow.
- The watermarks-remover pre-commit hook (see dotfiles-bare-repo-gitleaks-hook) also wraps commits; if it hangs or blocks on flagged files it can be skipped once via `WATERMARKS_REMOVER_DISABLE=1`, but that bypass is separate from the GPG/fingerprint issue.
