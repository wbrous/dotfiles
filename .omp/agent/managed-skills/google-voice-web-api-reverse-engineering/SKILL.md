---
name: google-voice-web-api-reverse-engineering
description: "Use when reverse-engineering Google Voice's internal (undocumented) web API from a HAR capture or curl request of voice.google.com — e.g. building a client to send/receive SMS, or investigating other clients6.google.com/voice/v1/voiceclient/* endpoints. Covers the verified SAPISIDHASH auth formula, the api2thread/list and api2thread/sendsms endpoints and their real field mapping (message text is plaintext, not encoded), the WAA/BotGuard attestation endpoint (unrelated to message content), why Firefox HAR exports can silently redact Cookie/Authorization values, and how to validate captured credentials before trusting them."
---

## Verified SAPISIDHASH auth formula

Google's internal web clients (gapi, Voice, Gmail, YouTube, ...) sign XHR/fetch requests with:

```
Authorization: SAPISIDHASH {ts}_{hash} SAPISID1PHASH {ts}_{hash} SAPISID3PHASH {ts}_{hash}
hash = SHA1(f"{ts} {sapisid} {origin}")
```

**Field order is `ts sapisid origin`, NOT `ts origin sapisid`** (the order commonly quoted online / assumed by intuition). Verify empirically against any real captured request before trusting an implementation — see "Validating captured credentials" below; a wrong field order fails silently (no exception, just a 401/403 later) unless you check the hash matches a live sample.

`sapisid` = value of the `SAPISID` cookie (or `__Secure-1PAPISID`/`__Secure-3PAPISID`, all equal within one session). `origin` = the page's origin (e.g. `https://voice.google.com`), not the API host's origin (e.g. NOT `https://clients6.google.com` even though that's where the request goes).

## api2thread/list and api2thread/sendsms field mapping

Endpoint: `POST https://clients6.google.com/voice/v1/voiceclient/api2thread/{list,sendsms}?alt=protojson&key={API_KEY}`

`api2thread/list` request body (protects nothing — no WAA token needed): `[2,100,50]` (threadType, pageSize, unknown). An empty `"[]"` body gets rejected with 400.

Response shape: `[[[threadId, 0, [eventRow, ...]], ...], "1", "v"]`. Each `eventRow` (30+ element array):

```
[id, timestampMs, accountNumber, participants, typeCode, directionFlag,
 _, _, _, text, _, _, _, _, _, otherPartyNumber, _, tmpId, ...tail, threadId]
```

- `directionFlag`: `0` = received, `1` = sent.
- **`text` (index 9) is the SMS body, verbatim plaintext.** No encoding, no encryption. If you sent/received a message whose body is literally "hello", this field is `"hello"`.
- `tmpId` (index 17): echoes back the client-chosen id passed on send, for correlating a send with its resulting event row.

`api2thread/sendsms` request body: `[null,null,null,null, text, threadId, null,null, [tmpId], null, [attestationToken]]`. **`text` (index 4) is also plain, unencoded message content** — not a magic constant. (Earlier investigation mistook a test message whose body was literally "SEND MESSAGE"/"RECEIVE MESSAGE" for an API-level type label; it's just what got typed as message content.)

## The opaque token is BotGuard/WAA, not message encoding

The huge (~3.7KB) opaque non-base64 string at the end of a `sendsms` request body is a **Web Application Attestation (WAA)** token — Google's generic anti-abuse/anti-bot proof, the same infra behind YouTube's "poToken". It comes from:

```
POST https://waa-pa.clients6.google.com/$rpc/google.internal.waa.v1.Waa/Create
-H 'X-Goog-Api-Key: <waa-specific key, different from the voiceclient key>'
-H 'X-User-Agent: grpc-web-javascript/0.1'
--data-raw '["<sitekey/context id>"]'
```

This is unrelated to message content — don't try to decode it as text. Generating one for real requires running the obfuscated JS challenge it returns (nontrivial; see OSS projects like `bgutils-js` / youtube-po-token-generator for prior art). Whether `sendsms` actually enforces its presence is unverified — `api2thread/list` works fine without any WAA token, so it may be endpoint-specific (mutating vs read-only).

## Validating captured credentials before trusting them

Firefox's "Save All As HAR" **silently anonymizes `Cookie`/`Authorization` header values** unless "Include sensitive data" was checked before export. Symptom: `SAPISID` cookie value present in a request doesn't reproduce that same request's `Authorization` hash via the verified formula above; also `APISID` and `SAPISID` end up as suspiciously different-looking random strings when they're often expected to correlate within a session.

**Always validate**: take one real `SAPISID` + `Authorization` (with its embedded unix timestamp) from the same captured request, and confirm `SHA1(f"{ts} {sapisid} {origin}")` reproduces the hash before building anything on top of that HAR's cookies. If it doesn't match, the HAR's credentials are redacted placeholders — ask for a fresh curl (browser DevTools → right-click request → Copy as cURL) instead, which does NOT redact.
