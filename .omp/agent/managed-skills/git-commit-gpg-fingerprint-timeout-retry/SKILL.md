---
name: git-commit-gpg-fingerprint-timeout-retry
description: "Use when a git commit invoked from an agent bash tool hangs indefinitely or times out on a system with fingerprint-gated GPG commit signing (commit.gpgsign=true + fprintd/pinentry) — the commit blocks silently (no visible prompt in captured output) waiting for a physical fingerprint touch, then after ~2 minutes fails with gpg: signing failed: Timeout / exit 128 / \"failed to write commit object\". Also covers why a background bash tool call can't surface this and why polling via hub in a real PTY, with explicit user prompts to touch the sensor, is required."
---

## Symptom

`git commit` (with `commit.gpgsign=true` and a fingerprint-gated pinentry configured — see `fingerprint-gated-gpg-unlock`/`gpg-fingerprint-pinentry-gating` skills) invoked via a plain bash tool call:

- Runs the pre-commit hook (gitleaks etc.) successfully, prints its output.
- Then hangs with no further output — the fingerprint prompt is a GUI/desktop dialog, not terminal text, so nothing in captured stdout/stderr indicates a prompt is waiting.
- After the gpg-agent's internal timeout (~2 minutes), fails with:
  ```
  error: gpg failed to sign the data:
  gpg: signing failed: Timeout
  fatal: failed to write commit object
  ```
  and the bash tool reports a plain 30/120s command timeout or exit 128, depending on which timeout hits first.

A plain backgrounded bash job (`bg_N`) will also just sit in "Still Running" — waiting on it via `hub wait` never resolves because the user was never told a touch is needed.

## Root cause

The commit is not actually stuck — it's correctly waiting for a real fingerprint scan the user hasn't performed yet, because the agent's tool output gave no indication one was needed. The gpg-agent pinentry cache (`default-cache-ttl`) had expired since the last signed commit.

## Fix

1. Start the commit via `hub start` with a real PTY (`application: "bash", args: ["-c", "git commit -m '...'"]`) instead of a plain backgrounded bash call — a PTY is what lets a fingerprint-prompting pinentry actually surface/behave correctly, matching the `sudo-interactive-tty-via-hub` pattern for other fingerprint/polkit-gated commands.
2. **Explicitly tell the user in the same turn** that a fingerprint touch is needed now — this is the step a plain bash call skips, since no visible prompt exists to alert them.
3. `hub wait` on the job with a real timeout (60-90s is reasonable — don't undershoot the ~2 minute gpg-agent timeout, but don't wait the full 2 minutes blindly either).
4. If it exits 128 with `gpg: signing failed: Timeout` in the logs, the touch didn't happen in time — restart the same commit (new `hub start` with a fresh job name) and prompt the user again. Two timeouts in a row is a signal to stop and ask the user how they want to proceed (retry again / commit unsigned for this one commit / let them commit manually) rather than retrying indefinitely.
5. On success the job exits 0 quickly (the actual `git commit` step is near-instant once signing succeeds) — `git log --oneline -1` confirms the new commit landed.

## Do NOT

- Don't assume a hung `git commit` bash call means something is broken in the repo/hooks — check `git config --get commit.gpgsign` and `user.signingkey` first; if signing is on, this is almost certainly the fingerprint wait, not a real hang.
- Don't silently fall back to `commit.gpgsign=false` or `--no-gpg-sign` without asking — that changes the security posture of the commit and the user may care.
- Don't retry more than ~2-3 times without checking in with the user; repeated silent timeouts likely mean the user is away from the machine, not that one more retry will help.
