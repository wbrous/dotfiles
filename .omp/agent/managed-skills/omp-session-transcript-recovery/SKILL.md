---
name: omp-session-transcript-recovery
description: "Use when a file, command, URL, token, or other artifact from a past agent session was deleted or lost (e.g. a working folder was rm -rf'd along with /tmp logs) — recover it by grepping the archived session transcript JSONL files under ~/.omp/agent/sessions/."
---

# Recovering lost artifacts from omp session transcripts

## When to use
- User deleted a project/working folder (and its `/tmp/*.log` files), then later needs a command, URL, token, or fact that only existed in that session — e.g. "what was the test URL we used?", "where did I put X".
- Any need to re-find exact tool-call commands or outputs from an earlier conversation on this machine.

## Where transcripts live
- `~/.omp/agent/sessions/` contains one directory per session, named `-<sanitized-cwd-path>` (leading hyphen + path with `/` → `-`), e.g.:
  - `-Applications-LockdownBrowser/`
  - `-Applications-Digiexam/`
  - `-tmp/`
- Each dir holds `<session-id>.jsonl` (full transcript: user messages, assistant turns, and ALL tool calls with their args and outputs) plus an optional subdir with attachments.

## How to search
The JSONL embeds tool call commands verbatim. Grep with escaped patterns:

```bash
grep -oE "URL='[^']*'" ~/.omp/agent/sessions/-*/<session>.jsonl | sort -u
grep -oE "ldb1:bt:0:%5B[A-Za-z0-9%]+%5D" ~/.omp/agent/sessions/-*/*.jsonl
```

- Long commands may be split across JSON escape sequences (`\n`, `\"`) — if a full-string grep misses, search for a distinctive *fragment* instead (`grep -oE "ldb1[^\"]*"`), then reconstruct.
- `grep -oiE "<needle>" ... | wc -l` gives mention counts to pick the right session dir when several exist.

## Worked example (real)
User deleted `/home/wils/Applications/Digiexam` (contained wine prefixes, GE-Proton, shims) and the `/tmp/*.log` files that held launcher commands, then asked for the LDB test URL used earlier. The URL was found intact in the archived transcript:
- `~/.omp/agent/sessions/-Applications-Digiexam/<session>.jsonl` → 379 `ldb1` mentions
- `grep -oE "URL='[^']*'"` recovered the full token:
  `ldb1:bt:0:%5BprJCFyylTOjR8JfuRp0HSSreVQwaGAoSU90pMJWTryCZYq6izkER7I513mAnc0BLQFSOkM8KFWVWzBUGcw/4kVfaOyLoZYvSP8W/Upws9fJrAEg5mEeBtRmvJ46dohEU%5D`

## Notes
- `/tmp` logs do NOT survive (deleted with the folder); session transcripts persist independently — always check them before declaring a string unrecoverable.
- The LDB `ldb1:` URLs are server-provided per exam; the client-side copy of the token is recoverable exactly as above.
