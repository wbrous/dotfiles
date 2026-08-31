---
name: google-voice-web-api-reverse-engineering
description: "Use when reverse-engineering Google Voice's internal (undocumented) web API from a HAR capture of voice.google.com — e.g. building a client to send/receive SMS, or investigating other clients6.google.com/voice/v1/voiceclient/* endpoints. Covers the SAPISIDHASH auth scheme, the api2thread/list and api2thread/sendsms endpoints, why message body text is absent from list responses, the opaque unreverse-engineered send-payload token, why wss:// traffic in a Voice HAR is unrelated (SIP calling, not texting), and how to detect Firefox's HAR-export cookie/auth redaction."
---

## Context
Reverse-engineered Google Voice's web client traffic from a Firefox-captured HAR (`voice.google.com_network_log.har`) to build a Bun/TS client that sends/receives SMS.

## Key endpoints (host: `https://clients6.google.com/voice/v1/voiceclient`)
- `POST api2thread/sendsms?alt=protojson&key={API_KEY}` — sends a message.
- `POST api2thread/list?alt=protojson&key={API_KEY}` — polls thread/event metadata (this is how "receiving" a message works; Voice's SMS transport is plain HTTP polling, **not** a live websocket).
- The `key` query param is a public web-client API key (`AIzaSy...`), not secret — safe to hardcode/commit.

## wss:// traffic is a red herring
A Voice HAR does contain `wss://web.voice.telephony.goog/websocket` entries, but that's for SIP/calling (voice calls), completely unrelated to SMS send/receive. Don't chase it when building a texting client.

## SAPISIDHASH auth (Google's cookie-based request signing)
`Authorization: SAPISIDHASH {ts}_{hash} SAPISID1PHASH {ts}_{hash} SAPISID3PHASH {ts}_{hash}`
where `hash = SHA1("{ts} {origin} {SAPISID}")`, `ts` = unix seconds, `origin = "https://voice.google.com"` (the page origin, not the request target `clients6.google.com`). Compute this fresh per-request from the `SAPISID` (or `__Secure-3PAPISID`) cookie — don't hardcode a captured header, it expires in minutes.

## api2thread/list response shape (event row, 0-indexed, ~30 elements)
`[id, timestampMs, accountNumber, participants, typeCode, directionFlag, _, _, _, label, _, _, _, _, _, otherPartyNumber, _, tmpId, ...tail, threadId]`
- `row[9]` = `"SEND MESSAGE"` | `"RECEIVE MESSAGE"` (the direction label).
- `row[17]` = client-generated tmpId, present only for events this client itself sent (echoes the id from the sendsms request body).
- **Message body text is NOT present anywhere in this response** — only metadata (who/when/thread/direction). Confirmed by exhaustively enumerating all 30 fields on both a SEND and RECEIVE row from a real capture; every non-metadata slot was `None`.
- Top-level response body: `[threads, "1", "v"]` where `threads = [[threadId, 0, events[]], ...]`.

## api2thread/sendsms request body shape
`[null,null,null,null,"SEND MESSAGE",threadId,null,null,[tmpId],null,[opaquePayload]]`
- `opaquePayload` is a single ~3.7KB non-standard-base64 string (e.g. `"!SUqlSi7NAA..."`) that presumably encodes the outgoing text client-side via undetermined logic — not JSON, not plain base64. **Could not reverse-engineer from a single capture.** To actually decode it: capture two sends with known, distinct plaintext bodies and diff the resulting payloads. Don't fake a plaintext→payload converter; expose it as a required opaque parameter instead and document the gap.

## Firefox HAR-export cookie/auth redaction — detect before trusting captured credentials
Firefox's "Save All As HAR" anonymizes `Cookie`/`Authorization` header values by default unless "Include sensitive data" was checked before capture. Detection trick: verify SAPISIDHASH math — take the `ts` embedded in a captured `Authorization` header and the `SAPISID` cookie value from the *same request*, recompute `SHA1("{ts} {origin} {SAPISID}")`, and check it matches the captured hash for both `origin = page` and `origin = request-target` candidates. If neither matches, the values are redaction placeholders, not real credentials (further confirmed if `APISID` and `SAPISID` cookies differ — in a real session they're normally identical). Don't ship a `.env` built from a HAR without running this check first; if it fails, tell the user explicitly rather than presenting captured cookies as working.
