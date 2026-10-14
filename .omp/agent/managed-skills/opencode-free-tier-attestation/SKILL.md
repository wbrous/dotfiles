---
name: opencode-free-tier-attestation
description: "When OpenCode rejects omp with FreeTierError, or the judge role (jev-1.13-free via opencode-zen proxy) fails with BrotliDecompressionError / 404 on /v1/v1/systemone, diagnose the local attestation proxy."
---

# OpenCode free-tier attestation for omp

OpenCode's Zen/Go free tier gates on request **shape** (looks-like-official-client), not the key. `403 FreeTierError: "can only be used from within OpenCode"` means shape mismatch, not bad credentials. Upstream tightens the checks periodically, so re-verify before assuming breakage.

## Known fingerprint (re-verified 2026-10-13 by one-signal-at-a-time replay of a real omp body)

Required simultaneously:

- `User-Agent` whose LEADING token is `opencode/<semver>`, version >= 1.18.0 (lower -> 426 `UpgradeRequired`). Trailing tokens are accepted: `opencode/1.19.0 omp/18.10.3` -> 200.
- `x-opencode-session: ses_<12 lowercase hex><14 base62>`. Format validated, value not. UPPERCASE hex -> 403. omp's native `<uuid>` -> 403.
- body `stream: true` (omp already sends this)
- body `tools` includes lowercase `bash`, `glob`, `grep`, `read` (omp already sends these; threshold has shifted before - recheck)
- muse-spark models use `/responses`, not `/chat/completions`

NOT required (verified): `x-opencode-client`, `x-opencode-request`, key value (`Bearer public` works), body size, system prompt.

Fixing only UA or only session still 403s - both are needed.

## This machine's fix

- `~/.omp/agent/opencode-attest.js` + systemd user service `opencode-attest` (127.0.0.1:8791): rewrites UA/session, maps each incoming session to one stable `ses_` id, streams bodies untouched. `models.yml` config headers **cannot** override omp's transport-stamped `x-opencode-session` (`setHeader` in `packages/ai/src/providers/inference-headers.ts`), hence the proxy.
- `~/.omp/agent/models.yml`: zen/go `baseUrl` -> proxy paths, backup headers.
- `~/.omp/agent/opencode-id.py`: mints `ses_`/`msg_` ids.

## System One / judge role through the proxy (fixed 2026-10-14)

Symptom: `omp find` / `judge()` with `modelRoles.judge: opencode-zen/jev-1.13-free` fails every request with `BrotliDecompressionError fetching ".../zen/v1/v1/systemone"`, then (after fix 1) `API error (404): <!DOCTYPE html>`.

Two proxy bugs, both fixed in `opencode-attest.js`:

1. **Forwarded `content-encoding`**: `fetch()` already decodes br/gzip, but the proxy re-sent the `content-encoding` header, so clients decoded twice. Fix: add `content-encoding` to the stripped response headers. Repro: `curl --compressed http://127.0.0.1:8791/zen/v1/models` failed with "Failed reading the chunked-encoded stream".
2. **Doubled `/v1/v1/`**: omp's `typesafe` System One transport appends `/v1/systemone` to a baseUrl already ending `/v1`. Fix: `req.url.replace(/\/v1\/v1\//, "/v1/")` before routing.

Upstream facts: `jev-1.13-free` is listed in the zen `/models` as kind chat but is served at `POST /zen/v1/systemone` (free key works); paid `jev-1.13` returns 401 without a real `OPENCODE_API_KEY`. Hand-made curl bodies gave misleading 400/422 ("Invalid request", "Endpoint is unavailable") - verify with omp itself instead: `omp find "<query>" <dir> -k <kw>`. Healthy run: judged all files, scores spread (0.98 down to 0.28), $0.0000.

Debug recipe: `ss -ltnp | grep 8791`; `systemctl --user restart opencode-attest` after any edit; `node --check opencode-attest.js`; compare `curl --compressed` through proxy vs direct to `https://opencode.ai/zen/v1/...` with `user-agent: opencode/1.19.0`. A python sniffer on :8899 with a models.yml baseUrl swap does NOT capture judge traffic (judge reads the role/provider, not that override) - skip it.

## Upstream tracking

Repo is `can1357/oh-my-pi`. Issues: #12306, #12418 (older), **#15609** (consolidated, filed 2026-10-13, with proposed fix: `opencode/<floor> omp/<ver>` UA + deterministic `ses_` id from conversation id). Unmerged PR #12325 (bundles OAuth device flow). Check these before re-filing.

## Re-diagnosing when upstream changes the gate

1. Capture a REAL omp body: temp edit `models.yml` zen `baseUrl` to a local logging server (python http.server on 127.0.0.1:8899; log headers + parsed summary of stream/tools - omp puts `stream`/`tools` at the END of big bodies), run `omp -p --model opencode-zen/big-pickle "ok"`, then RESTORE models.yml. Save raw body.
2. Replay with `curl --data-binary @body` against `https://opencode.ai/zen/v1/chat/completions` (or `/responses` for muse-spark), varying ONE header at a time. Vary the real body too - tool-less/non-stream probes give false 403s. Beware typos in hand-made ids (a bad id looks like a gate change).
3. Error classes: 403 FreeTierError = shape, 426 = UA version low, 429 FreeUsageLimitError = per-IP quota, 403 `[user_blocked]` = account ban. Reported lane drift: `/inference/openai/v1/responses`; `zen/go/v1/responses` returned 400 "Model is unavailable" for muse-spark-free.
4. Verify end-to-end: `omp -p --model opencode-zen/big-pickle "reply with just the word ok"` and the go muse-spark model.
