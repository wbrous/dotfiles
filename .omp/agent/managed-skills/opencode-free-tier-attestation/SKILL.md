---
name: opencode-free-tier-attestation
description: "When OpenCode rejects omp with FreeTierError, diagnose attestation failure."
---

# OpenCode free-tier attestation for omp

OpenCode's Zen/Go free tier gates on request **shape** (looks-like-official-client), not the key. `403 FreeTierError: "can only be used from within OpenCode"` means shape mismatch, not bad credentials. Upstream tightens the checks periodically, so re-verify before assuming breakage.

## Known fingerprint (re-verified 2026-10-13 by one-signal-at-a-time replay of a real omp body)

Required simultaneously:

- `User-Agent` whose LEADING token is `opencode/<semver>`, version >= 1.18.0 (lower → 426 `UpgradeRequired`). Trailing tokens are accepted: `opencode/1.19.0 omp/18.10.3` → 200.
- `x-opencode-session: ses_<12 lowercase hex><14 base62>`. Format validated, value not. UPPERCASE hex → 403. omp's native `<uuid>` → 403.
- body `stream: true` (omp already sends this)
- body `tools` includes lowercase `bash`, `glob`, `grep`, `read` (omp already sends these; per upstream comments the threshold has shifted — recheck)
- muse-spark models use `/responses`, not `/chat/completions`

NOT required (verified): `x-opencode-client`, `x-opencode-request`, key value (`Bearer public` works), body size, system prompt.

Fixing only UA or only session still 403s — both are needed.

## This machine's fix

- `~/.omp/agent/opencode-attest.js` + systemd user service `opencode-attest` (127.0.0.1:8791): rewrites UA/session, maps each incoming session to one stable `ses_` id, streams bodies untouched. `models.yml` config headers **cannot** override omp's transport-stamped `x-opencode-session` (`setHeader` in `packages/ai/src/providers/inference-headers.ts`), hence the proxy.
- `~/.omp/agent/models.yml`: zen/go `baseUrl` → proxy paths, backup headers.
- `~/.omp/agent/opencode-id.py`: mints `ses_`/`msg_` ids.

## Upstream tracking

Repo is `can1357/oh-my-pi`. Issues: #12306, #12418 (older), **#15609** (consolidated, filed 2026-10-13, with proposed fix: `opencode/<floor> omp/<ver>` UA + deterministic `ses_` id from conversation id). Unmerged PR #12325 (bundles OAuth device flow). Check these before re-filing.

## Re-diagnosing when upstream changes the gate

1. Capture a REAL omp body: temp edit `models.yml` zen `baseUrl` to a local logging server (python http.server on 127.0.0.1:8899; log headers + parsed summary of stream/tools — omp puts `stream`/`tools` at the END of big bodies), run `omp -p --model opencode-zen/big-pickle "ok"`, then RESTORE models.yml. Save raw body.
2. Replay with `curl --data-binary @body` against `https://opencode.ai/zen/v1/chat/completions` (or `/responses` for muse-spark), varying ONE header at a time. Vary the real body too — tool-less/non-stream probes give false 403s. Beware typos in hand-made ids (a bad id looks like a gate change).
3. Error classes: 403 FreeTierError = shape, 426 = UA version low, 429 FreeUsageLimitError = per-IP quota, 403 `[user_blocked]` = account ban. Reported lane drift: `/inference/openai/v1/responses`; `zen/go/v1/responses` returned 400 "Model is unavailable" for muse-spark-free.
4. Verify end-to-end: `omp -p --model opencode-zen/big-pickle "reply with just the word ok"` and the go muse-spark model.
