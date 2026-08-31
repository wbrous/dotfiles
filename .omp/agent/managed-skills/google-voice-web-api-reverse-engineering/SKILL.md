---
name: google-voice-web-api-reverse-engineering
description: "Use when reverse-engineering Google Voice's internal (undocumented) web API from a HAR capture or curl request of voice.google.com — e.g. building a client to send/receive SMS, or investigating other clients6.google.com/voice/v1/voiceclient/* endpoints. Covers the verified SAPISIDHASH auth formula, the api2thread/list and api2thread/sendsms endpoints and their real field mapping (message text is plaintext, not encoded), the WAA/BotGuard attestation endpoint (unrelated to message content), why Firefox HAR exports can silently redact Cookie/Authorization values, and how to validate captured credentials before trusting them — including the SIDCC-family cookie rotation that makes a captured session go stale within roughly an hour."
---

## Endpoints (host: clients6.google.com/voice/v1/voiceclient)

- `POST api2thread/list?alt=protojson&key=<API_KEY>` — body `[2,100,50]` (an
  empty `[]` body 400s). Response: `[[[threadId, _, events], ...], "1", "v"]`.
  Works with only cookie-based SAPISIDHASH auth — no WAA/BotGuard token needed.
- `POST api2thread/sendsms?alt=protojson&key=<API_KEY>` — body:
  `[null,null,null,null, text, threadId, null,null, [Number(tmpId)], null, [attestationToken]]`.
  `text` is the plaintext SMS body verbatim — NOT encoded/encrypted. `tmpId`
  is a client-chosen numeric string echoed back in the corresponding list
  event's `tmpId` field. Returns 401 if the session cookie is stale — same
  failure mode as an actually-missing WAA token, so always cross-check with
  `api2thread/list` (see "Debugging 401s" below) before concluding WAA is
  required.

### Thread event row shape (from api2thread/list)

0-indexed array, ~30 elements per event row:
`[id, timestampMs, accountNumber, participants, typeCode, directionFlag,
  _, _, _, text, _, _, _, _, _, otherPartyNumber, _, tmpId, ...tail, threadId]`

- `row[5]` (directionFlag): `0` = received, `1` = sent. `row[4]` (typeCode)
  correlates (10=received sms, 11=sent sms) but directionFlag is simpler.
- `row[9]` = the SMS body, **plaintext, unencoded**. If test messages are
  literally sent with content like "SEND MESSAGE"/"RECEIVE MESSAGE", that
  string will appear verbatim here — it is not a protocol constant. Don't
  assume a literal string found in a capture is an API keyword without first
  checking whether it's just the tester's own message content.
- `row[17]` = tmpId (present only for events this client sent via sendsms).
- last element = threadId, e.g. `"t.+14697590653"`.

## SAPISIDHASH auth (verified against a live, non-redacted request)

```
Authorization: SAPISIDHASH {ts}_{hash} SAPISID1PHASH {ts}_{hash} SAPISID3PHASH {ts}_{hash}
hash = SHA1(f"{ts} {SAPISID_cookie} {origin}")   # NOT "{ts} {origin} {sapisid}" — field order is ts, sapisid, origin
origin = "https://voice.google.com"  (the page origin, not the request target clients6.google.com)
ts = unix seconds
```
Many public write-ups state the order as `ts origin sapisid` — that did NOT
match a live-verified request; `ts sapisid origin` did. Always verify empirically
against one real Authorization + Cookie pair from the same request before trusting
either ordering, by brute-forcing cookie-name × order-permutation combos with
`hashlib.sha1` and comparing to the header's embedded digest.

## WAA / BotGuard attestation (waa-pa.clients6.google.com)

`POST https://waa-pa.clients6.google.com/$rpc/google.internal.waa.v1.Waa/Create`
(gRPC-web-javascript, separate API key from voiceclient) is Google's generic
BotGuard/Web Application Attestation service — the same anti-abuse system
YouTube uses for its "poToken". It issues a signed proof-of-genuine-browser
token. It is **unrelated to message content** — don't confuse a large opaque
non-base64 token (`!SUqlSi7NAA...`, ~3.7KB) appended to a sendsms request
with an encoded message body. That opaque field is the BotGuard attestation;
the actual message text is elsewhere in the same request, in plain text (see
above). Whether sendsms actually enforces this token server-side is still
unconfirmed — a 401 on sendsms could equally be caused by a stale cookie
(see below), so don't conclude WAA is mandatory without first ruling that out.

## Firefox HAR redaction

Firefox's "Save All As HAR" anonymizes `Cookie`/`Authorization` header values
by default. Symptom: `SAPISIDHASH` computed from the HAR's own `SAPISID`
cookie + timestamp does NOT reproduce the HAR's own `Authorization` header
value from the same request entry — that mismatch is the fingerprint of
redaction, not a formula bug. Also: `APISID` and `SAPISID` cookie values in a
real session may legitimately differ from each other; don't use "they don't
match" alone as a redaction signal.

Fix: re-export with the HAR-export panel's "Include sensitive data" option
enabled, or copy fresh values directly from DevTools Network tab / a raw curl
(right-click a request → Copy → Copy as cURL / Copy Value) instead of an HAR
export.

## Debugging 401s: stale session vs. missing WAA token

`SIDCC` / `__Secure-1PSIDCC` / `__Secure-3PSIDCC` cookies rotate frequently —
observed a captured session go fully unauthenticated (401 on *every* endpoint,
including `api2thread/list` which needs no WAA token) within roughly an hour
of capture. Before attributing a `sendsms` 401 to a missing/invalid WAA
attestation token, first retry `api2thread/list` with the same cookie — if
that also 401s, the cookie itself is stale and must be recaptured; it says
nothing about whether WAA is required on sendsms.

## Validating credentials before trusting them

Given one real (non-redacted) `Authorization` header + `Cookie` header from
the same request:
1. Extract `ts` and `hash` from `Authorization`, parse all cookies from `Cookie`.
2. Brute-force every cookie name × a few origin candidates × a few field
   orderings through `SHA1`, looking for an exact hex match to `hash`.
3. Only trust the formula once you get an exact match — don't assume a
   remembered/documented formula is correct without this check, since public
   references disagree on field order.
