---
name: google-voice-web-api-reverse-engineering
description: "Use when reverse-engineering Google Voice's internal web API (sendsms, api2thread/list, attachments, WAA/BotGuard attestation, SAPISIDHASH auth) or debugging cookie expiry/401s / multi-browser session reading (Firefox, Zen, Chrome, Brave, Vivaldi, Opera, Edge, Safari via cookies.sqlite or @mherod/get-cookie) in a client that replays a browser session."
---

# Google Voice web API reverse-engineering

Reverse-engineered from Firefox/Zen HAR captures of voice.google.com (2026-08-31), then validated live. Project: `/home/wils/Documents/Development/google-voice-ws` (bun library).

## Endpoints (all `POST https://clients6.google.com/voice/v1/voiceclient/...?alt=protojson&key=AIzaSy<voiceApiKey>` — the `key` param is a public browser-shipped constant; grab the exact value from any live capture's query string, don't paste one here)

- `api2thread/sendsms` — send. Body (positional array): `[null,null,null,null,text,threadId,null,null,[tmpIdNumeric],mediaField,botguardField]`
  - `text`: plaintext SMS body VERBATIM (no encoding). `mediaField`: `[2, base64ImageBytes]` for photo MMS, else null. `botguardField`: `[wsaToken, null, null, recaptchaToken]` — see WAA below.
  - **Attachment size limit**: ~11MB request body → real `400 INVALID_ARGUMENT` (`base64_format: "CAU="`); ~400KB succeeds. Exact cutoff unknown; library defaults to 1MB cap with sharp-based JPEG recompression fallback.
- `api2thread/list` — read. Body: `[2,100,50]` (empty `[]` → 400). Response: `[threads, ...]`, each thread `[threadId, _, events]`.
  - Event row (0-indexed): `0`=id, `1`=timestampMs, `2`=accountNumber, `5`=directionFlag (0=RECEIVED, 1=SENT), `9`=SMS text OR MMS type label (`"MMS Sent"`/`"MMS Received"` — NOT content), `14`=MMS content `[caption, _, attachments, ...]` or null, `15`=otherPartyNumber, `17`=tmpId (echoed from send), `last`=threadId.
  - Attachment entry: `[mimeType, idWithDashSuffix, _, sizes, ...]`. **Images** have `sizes=[[sizeCode,width,height],...]`; **videos** (`video/3gpp`) have `sizes=null` — decode as empty variants, don't crash.
  - **Gotcha**: for MMS events `row[9]` is a fixed label; the real content is `row[14]`. Reading index 9 for text yields `"MMS Sent"` garbage.
- Attachment download: `GET https://voice.google.com/u/{authUser}/a/i/{attachmentId}?s={sizeCode}` — plain cookie auth, NO SAPISIDHASH needed. Works for received images (no network request exists for received images in HARs — bytes come from this URL only).
- WAA/BotGuard: `POST https://waa-pa.clients6.google.com/$rpc/google.internal.waa.v1.Waa/Create` with body `["<sitekey>"]`, `X-Goog-Api-Key: AIzaSy<waaApiKey>` (again public; read from a live capture), `X-User-Agent: grpc-web-javascript/0.1`. This is Google's generic anti-abuse attestation (same system as YouTube's poToken), NOT message encoding. The sendsms botguardField tokens are NOT bound to message text (replaying captured tokens with different text succeeded) — they're bound to session recency.

## SAPISIDHASH auth (verified formula)

```
Authorization: SAPISIDHASH {ts}_{sha1hex("{ts} {sapisid} https://voice.google.com")} SAPISID1PHASH {same} SAPISID3PHASH {same}
```
Field order is `ts SPACE sapisid SPACE origin` (getting this wrong = 401). ts = unix seconds, fresh per request.

## Session cookie renewal (the 401 problem)

- `SIDCC`/`__Secure-1PSIDCC`/`__Secure-3PSIDCC` expire quickly (minutes-hours); `SID`/`HSID`/`SSID`/`APISID`/`SAPISID` are long-lived (months-years).
- Browsers renew via `POST https://accounts.google.com/RotateCookies` body `[72,"<numericToken>"]` — but the token is minted by page JS; CANNOT be reproduced with plain HTTP.
- **App passwords do NOT work** — legacy protocols only (IMAP/SMTP/CalDAV), no relationship to web session cookies.
- **No OAuth path** for consumer Voice SMS.

### Multi-browser session reading

- **Firefox-family** (Firefox, Zen, LibreWolf, Waterfox): unencrypted `cookies.sqlite` — copy `cookies.sqlite{,-wal,-shm}` to a temp dir first (live browser may hold an exclusive lock), query `host LIKE '%google.com'`. Multi-account lives in the hidden `originAttributes` column (`''` = default, `^userContextId=2` = container tab); anchor on the `SID` value from the existing .env. Zero deps.
- **Chromium-family** (Chrome, Chromium, Edge, Brave, Opera, Opera GX, Vivaldi, Arc) + **Safari**: cookies AES-GCM-encrypted behind an OS-keyring/DPAPI/Keychain key, or Safari binary format — DON'T hand-roll decryption for 3 OSes. Use the optional peer `@mherod/get-cookie` (`ChromiumCookieQueryStrategy(browserType)` / `SafariCookieQueryStrategy().queryCookies("%","google.com")`). It handles Linux Secret Service / macOS Keychain / Windows DPAPI.
- **Caveat (hit on this machine)**: Zen with a temporary/container tab kept today's SIDCC rotations in memory — the on-disk jar was 36 days stale and 401'd. Solution: verify against the live API before trusting the jar; fall back to a persistent Playwright chromium profile. Auto flow does exactly this.
- Library: `readBrowserSession(browser?)` (unified), `detectBrowsers()`, `readFirefoxSession()` (sqlite-only). CLI `bun run refresh-cookies --browser <name>`; auto path = any-browser jar → live verify → playwright fallback.

### Playwright login flow (headless automation)

- **Google blocks automated chromium LOGIN** ("Couldn't sign you in — this browser or app may not be secure"). Mitigations that worked: launch args `--disable-blink-features=AutomationControlled --no-first-run --no-default-browser-check`, init script hiding `navigator.webdriver`, and a real (non-HeadlessChrome) Chrome UA.
- **headless default trap**: Playwright's persistent context auto-turns headless when the profile dir exists. If the first run created `.gv-browser-profile/` but you still want a visible window, pass `--no-headless` and `rm -rf .gv-browser-profile` first.
- Persistent profile is single-account → `X-Goog-AuthUser: 0` (a `1` from a multi-account browser jar 401s in it). CLI persists `GV_AUTH_USER=0` on browser refresh.
- After login success, a headless recurring refresh takes ~5s and produces a live-valid cookie (cron-able).
- Optional peers `playwright` + `@mherod/get-cookie` are BOTH externalized in `bun build` and marked optional in `peerDependenciesMeta`, so consumers not using those paths ship a 0.26 MB bundle.

## HAR capture notes

- Firefox HAR export anonymizes `Cookie`/`Authorization` headers unless "Include sensitive data" is enabled in the export gear menu. Detection: compute SAPISIDHASH from the SAPISID cookie + ts in the same request — mismatch means redacted.
- To find where a value lives on the wire: send a unique greppable test string (e.g. `ZZQTESTMSG7f3a9c1`) and use Firefox Network panel's built-in search (magnifying glass) which searches request AND response bodies, not just URLs.
- Message text appears VERBATIM in both sendsms body index 4 and list response index 9 — earlier confusion came from test messages whose literal text was "SEND MESSAGE"/"RECEIVE MESSAGE", looking like protocol constants.
- `curl --data-raw $'...'` bodies with octal escapes (`\041`) decode via python `json.loads` after shell printf; escape `!` as `\041` for history safety.

## Auth flow for real sends

401 without tokens; 200 with captured `[botguardToken, null, null, recaptchaToken]` replay. Token reuse window is short (session-bound); regenerate via the browser refresh flow or re-capture.
