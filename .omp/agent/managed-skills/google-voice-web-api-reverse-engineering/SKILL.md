---
name: google-voice-web-api-reverse-engineering
description: "Use when reverse-engineering Google Voice's internal web API (sendsms, api2thread/list, attachments, WAA/BotGuard attestation, SAPISIDHASH auth, session cookie renewal) or debugging cookie expiry/401s in a client that replays a browser session."
---

# Google Voice web API reverse-engineering

Reverse-engineered from Firefox HAR captures of voice.google.com (2026-08-31), then validated live. Project: `/home/wils/Documents/Development/google-voice-ws` (bun library).

## Endpoints (all `POST https://clients6.google.com/voice/v1/voiceclient/...?alt=protojson&key=AIzaSy<voiceApiKey>` — the `key` param is a public browser-shipped constant; grab the exact value from any live capture's query string, don't paste one here)

- `api2thread/sendsms` — send. Body (positional array): `[null,null,null,null,text,threadId,null,null,[tmpIdNumeric],mediaField,botguardField]`
  - `text`: plaintext SMS body VERBATIM (no encoding). `mediaField`: `[2, base64ImageBytes]` for photo MMS, else null. `botguardField`: `[wsaToken, null, null, recaptchaToken]` — see WAA below.
  - **Attachment size limit**: ~11MB request body → real `400 INVALID_ARGUMENT` (`base64_format: "CAU="`); ~400KB succeeds. Exact cutoff unknown; library defaults to 1MB cap with sharp-based JPEG recompression fallback.
- `api2thread/list` — read. Body: `[2,100,50]` (empty `[]` → 400). Response: `[threads, ...]`, each thread `[threadId, _, events]`.
  - Event row (0-indexed): `0`=id, `1`=timestampMs, `2`=accountNumber, `5`=directionFlag (0=RECEIVED, 1=SENT), `9`=SMS text OR MMS type label (`"MMS Sent"`/`"MMS Received"` — NOT content), `14`=MMS content `[caption, _, attachments, ...]` or null, `15`=otherPartyNumber, `17`=tmpId (echoed from send), `last`=threadId.
  - Attachment entry: `[mimeType, idWithDashSuffix, _, [[sizeCode,width,height],...], _, _, _, _, downloadPath]`.
  - **Gotcha**: for MMS events `row[9]` is a fixed label; the real content is `row[14]`. Reading index 9 for text yields `"MMS Sent"` garbage.
- Attachment download: `GET https://voice.google.com/u/{authUser}/a/i/{attachmentId}?s={sizeCode}` — plain cookie auth, NO SAPISIDHASH needed. Works for received images (no network request exists for received images in HARs — bytes come from this URL only).
- WAA/BotGuard: `POST https://waa-pa.clients6.google.com/$rpc/google.internal.waa.v1.Waa/Create` with body `["<sitekey>"]`, `X-Goog-Api-Key: AIzaSy<waaApiKey>` (again public; read from a live capture), `X-User-Agent: grpc-web-javascript/0.1`. This is Google's generic anti-abuse attestation (same system as YouTube's poToken), NOT message encoding. The sendsms botguardField tokens are NOT bound to message text (replaying captured tokens with different text succeeded) — they're bound to session recency.

## SAPISIDHASH auth (verified formula)

```
Authorization: SAPISIDHASH {ts}_{sha1hex("{ts} {sapisid} https://voice.google.com")} SAPISID1PHASH {same} SAPISID3PHASH {same}
```
Field order is `ts SPACE sapisid SPACE origin` (getting this wrong = 401). ts = unix seconds, fresh per request.

## Session cookie renewal (the 401 problem)

- `SIDCC`/`__Secure-1PSIDCC`/`__Secure-3PSIDCC` expire quickly (minutes-hours); `SID`/`HSID`/`SSID`/`APISID`/`SAPISID` are long-lived.
- Browsers renew via `POST https://accounts.google.com/RotateCookies` body `[72,"<numericToken>"]` — but the token is minted by page JS; CANNOT be reproduced with plain HTTP.
- **App passwords do NOT work** — legacy protocols only (IMAP/SMTP/CalDAV), no relationship to web session cookies.
- **No OAuth path** for consumer Voice SMS.
- Solution implemented: `refreshCookies()` in src/refresh.ts — persistent Playwright Chromium profile loads voice.google.com (its JS rotates cookies), then reads the jar back. First run interactive login (2FA once), later runs headless + cron-able. `writeEnvCookie()` updates `.env` in place. CLI: `bun run refresh-cookies`.
- Use system `/usr/bin/chromium` via `executablePath` fallback — avoids the ~184MB `bunx playwright install chromium` download entirely (Playwright 1.62 wants build 1234; cached 1228 won't satisfy it, but any system chromium works).

## HAR capture notes

- Firefox HAR export anonymizes `Cookie`/`Authorization` headers unless "Include sensitive data" is enabled in the export gear menu. Detection: compute SAPISIDHASH from the SAPISID cookie + ts in the same request — mismatch means redacted.
- To find where a value lives on the wire: send a unique greppable test string (e.g. `ZZQTESTMSG7f3a9c1`) and use Firefox Network panel's built-in search (magnifying glass) which searches request AND response bodies, not just URLs.
- Message text appears VERBATIM in both sendsms body index 4 and list response index 9 — earlier confusion came from test messages whose literal text was "SEND MESSAGE"/"RECEIVE MESSAGE", looking like protocol constants.
- `curl --data-raw $'...'` bodies with octal escapes (`\041`) decode via python `json.loads` after shell printf; escape `!` as `\041` for history safety.

## Auth flow for real sends

401 without tokens; 200 with captured `[botguardToken, null, null, recaptchaToken]` replay. Token reuse window is short (session-bound); regenerate via the browser refresh flow or re-capture.

## Skill hygiene: gitleaks blocks on public API keys

The global gitleaks pre-commit hook flags `AIzaSy…` strings as `gcp-api-key` and blocks the dotfiles autosync commit for any skill that pastes them. These keys are public (shipped in every browser client), but do NOT bypass with `GIT_ALLOW_SECRETS=1` — instead scrub real key values from the skill body to `AIzaSy<name>` placeholders with a "read from a live capture" note, then recommit manually via `git --git-dir=$HOME/.dotfiles --work-tree=$HOME add -- .omp/agent/managed-skills/<name>/SKILL.md && git ... commit -m "..."`. Applies to any API-documenting skill, not just this one.
