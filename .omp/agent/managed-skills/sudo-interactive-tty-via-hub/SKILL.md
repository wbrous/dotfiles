---
name: sudo-interactive-tty-via-hub
description: "Use when sudo commands fail with \"a password is required\" in the bash tool or sudo -n fails, especially with fingerprint (fprintd/polkit) auth on this machine — launch sudo in a real PTY via hub start to surface the interactive prompt."
---

# Running sudo with interactive prompts (fingerprint auth) in this harness

## Symptom
- `sudo -n <cmd>` fails with `sudo: a password is required` even though the user's auth is fingerprint (fprintd/polkit), not a typed password.
- The bash tool has no TTY (`test -t 0` → no), so interactive prompts can't render there.

## Why
- `-n`/`--non-interactive` means "never prompt AT ALL" — if any authentication (including the fingerprint polkit prompt) is pending, it fails immediately. It is NOT "no password".
- `sudo -v`/`--validate` refreshes cached credentials without running a command; it extends the timeout (default 5 min) and CAN trigger the interactive fingerprint prompt.
- Fingerprint scanning IS a "prompt" to sudo, so `-n` refuses it by design.

## Fix: launch sudo in a real PTY via hub
The hub `start` op allocates a true interactive PTY (`pty` defaults true) where polkit/fprintd prompts render.

1. Start the command:
   `hub op=start name=<name> application=sudo args=[...] pty=true`
   (e.g. `args=["true"]` for a trivial auth check)
2. Wait for exit:
   `hub op=wait name=<name> for=exit timeout=<s>`
3. Read the prompt/output:
   `hub op=logs name=<name>`

Expected flow: output shows "Place your right index finger on the fingerprint reader", user scans, process exits 0.

## Notes
- `script -qec "sudo -n true" /dev/null` in bash allocates a PTY but `-n` still fails — the PTY doesn't bypass the non-interactive flag.
- `sudo -v` also works through a PTY (`script -qec "sudo -v" /dev/null`).
- Once credentials are cached (e.g. after a successful `sudo -v`), `sudo -n` succeeds within the timeout window — useful for scripts.
- Environment fact: this machine uses fingerprint (fprintd) + polkit for sudo auth; no password is typed.
