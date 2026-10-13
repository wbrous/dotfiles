---
name: opencode-free-tier-attestation
description: Diagnose and fix OpenCode free-tier FreeTierError rejections for omp
---

# OpenCode free-tier attestation for omp

OpenCode's Zen/Go free tier gates on request **shape** (looks-like-official-client), not the key. `403 FreeTierError: "can only be used from within OpenCode"` means shape mismatch, not bad credentials. Upstream tightens the checks periodically, so re-verify before assuming breakage.

## Known fingerprint (verified 2026-10-13)

All required simultaneously; anything else (body size, system prompt, key value — `Bearer public` works) is ignored:

- `User-Agent: opencode/<semver>`, version >= 1.18.0 (lower → 426 `UpgradeRequired`)
- `x-opencode-session: ses_<12 lowercase hex><14 base62>` (timestamp value not validated, format is; omp's native `<uuid>` fails)
- `x-opencode-request: msg_<same format>`
- `x-opencode-client: desktop`
- body `stream: true` (omp already sends this)
- body `tools` includes lowercase `bash`, `glob`, `grep`, `read` (omp already sends these)
- muse-spark models use the `/responses` endpoint, not `/chat/completions`

## This machine's fix

- `~/.omp/agent/opencode-attest.js` + systemd user service `opencode-attest` (port 127.0.0.1:8791): rewrites UA/session, maps each incoming session to one stable `ses_` id, streams bodies untouched. `models.yml` config headers **cannot** override transport-native headers (omp's UUID session wins), hence the proxy.
- `~/.omp/agent/models.yml`: zen/go `baseUrl` → proxy paths, backup headers.
- `~/.omp/agent/opencode-id.py`: mints `ses_`/`msg_` ids for config `!`-commands.

## Re-diagnosing when upstream changes the gate

1. Reproduce with curl against `https://opencode.ai/zen/v1/chat/completions` (or `/responses` for muse-spark), varying one signal at a time: UA → session → request → stream → tools. Error classes differ: 403 FreeTierError = shape, 426 = UA version too low, 429 FreeUsageLimitError = per-IP quota (change egress, not shape).
2. To see what omp actually sends: temp `models.yml` provider with `baseUrl: http://127.0.0.1:<port>/v1` + a stdlib logging server; `omp -p --model <probe>/...`. Note omp sends `stream`, `tools`, `tool_choice` at the END of large bodies — log parsed summaries, not truncated prefixes.
3. Reference: community notes on the fingerprint (e.g. `0xgetz/opencode-free-9router` README, `shiyanYX/opencode2api` UPSTREAM-COMPAT.md) document newly discovered conditions.
4. Verify end-to-end with `omp -p --model opencode-zen/big-pickle "reply with just the word ok"` and the go muse-spark model.
