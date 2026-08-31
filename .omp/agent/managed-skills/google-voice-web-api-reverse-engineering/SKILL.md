---
name: google-voice-web-api-reverse-engineering
description: "Use when reverse-engineering Google Voice's internal (undocumented) web API from a HAR capture or curl request of voice.google.com — e.g. building a client to send/receive SMS, or investigating other clients6.google.com/voice/v1/voiceclient/* endpoints. Covers the verified SAPISIDHASH auth formula, the api2thread/list and api2thread/sendsms endpoints and their real field mapping (message text is plaintext, not encoded), the sendsms anti-abuse token requirement (WAA/BotGuard + reCAPTCHA-style token pair, tokens not bound to exact message text), the WAA/BotGuard attestation endpoint, why Firefox HAR exports can silently redact Cookie/Authorization values, how to validate captured credentials before trusting them, the SIDCC-family cookie rotation that makes a captured session go stale within roughly an hour, and how to extract exact request bodies from a curl --data-raw ANSI-C ($'...') string containing octal escapes."
---

## Endpoints (all POST, `alt=protojson&key=<apiKey>` query params)

- `https://clients6.google.com/voice/v1/voiceclient/api2thread/list` — list every thread + event metadata **and message text**. Body: `[2,100,50]` (empty `"[]"` body is rejected with 400).
- `https://clients6.google.com/voice/v1/voiceclient/api2thread/sendsms` — send an SMS. Requires anti-abuse tokens (see below) or the server returns 401.
- `https://waa-pa.clients6.google.com/$rpc/google.internal.waa.v1.Waa/Create` — Google's generic BotGuard/Web-Application-Attestation service (same system YouTube uses for "poToken"). Uses a *different* API key than the voiceclient endpoints. Unrelated to message content — it's a proof-of-genuine-browser challenge/response system.

## Auth: SAPISIDHASH (verified against live, non-redacted requests)

```
Authorization: SAPISIDHASH {ts}_{hash} SAPISID1PHASH {ts}_{hash} SAPISID3PHASH {ts}_{hash}
hash = SHA1(`${ts} ${SAPISID_cookie} ${origin}`)   // note: sapisid BEFORE origin
```
`origin` = `"https://voice.google.com"` (the page origin, not the request target host `clients6.google.com`). This is the field order that reproduces real captured Authorization headers exactly — the commonly-cited "ts origin sapisid" order is WRONG for this API; verify empirically against a real capture, don't trust memory/docs.

`SAPISID` (or `__Secure-1PAPISID`/`__Secure-3PAPISID`, same value) comes from the `Cookie` header of an authenticated google.com session.

## sendsms request body shape (11-element JSON array)

```
[null,null,null,null, TEXT, threadId, null,null, [tmpId], null, tokensArray]
```
- `TEXT` (index 4): **plaintext message body, verbatim, no encoding**. Don't assume it's encrypted/opaque just because it looks unfamiliar — a message whose body is literally "hello" appears as the literal string `"hello"`.
- `threadId` (index 5): e.g. `"t.+14697590653"`.
- `tmpId` (index 8, wrapped in an array): client-chosen unique numeric id, echoed back in the corresponding list-response event row so you can correlate.
- `tokensArray` (index 10): **4-element array** `[attestationToken, null, null, recaptchaToken]`, NOT a 1-element wrapper.
  - `attestationToken`: starts with `!`, ~1500 chars, from the WAA/BotGuard flow.
  - `recaptchaToken`: starts with `0cAFcWeA` (or similar), ~2000+ chars, reCAPTCHA-style.
  - Omitting this array (`null`) → server returns **401 Unauthorized**. This is the actual gate, not a coincidental auth issue.
  - **Tokens are not bound to the exact message text.** A token pair captured for one message ("hello") successfully sent a completely different message ("Hello from AI") minutes later — they appear to validate session/browser recency, not per-message content. So a single manual capture of `{attestationToken, recaptchaToken}` can be reused across several sends within some (unmeasured, likely short — an hour or less given SIDCC rotation) time window.
  - Full automated generation requires running Google's obfuscated BotGuard JS challenge (headless browser or a reverse-engineered VM interpreter, à la yt-dlp's po_token providers) — out of scope for a HAR-capture-only client; treat tokens as caller-supplied.

## api2thread/list response row shape (30+ element array per event)

```
[id, timestampMs, accountNumber, participantsArray, typeCode, directionFlag,
 _,_,_, TEXT, _,_,_,_,_, otherPartyNumber, _, tmpId, ...tail, threadId]
```
- `TEXT` (index 9): plaintext message body, verbatim — same field philosophy as the send request. **This is the field that actually carries content; don't assume metadata-only responses hide the text elsewhere or that it's encrypted.**
- `directionFlag` (index 5): `0` = received, `1` = sent (redundant with `typeCode` at index 4: `10`=received sms, `11`=sent sms).
- `tmpId` (index 17): present (matches the tmpId sent in the corresponding sendsms request) for events this account sent; `null` for received events.
- `threadId`: last element of the row.

Top-level response shape: `[[[threadId, _, eventsArray], ...], "1", "v"]`.

## Firefox HAR export redaction (critical gotcha)

Firefox's "Save All As HAR" **silently anonymizes** `Cookie`/`Authorization` header values unless "Include sensitive data" is checked before capture. Symptom: the exported Authorization header's embedded SHA1 hash doesn't reproduce when computed from the exported Cookie's SAPISID value using the correct formula — that mismatch is the fingerprint of redaction, not a formula bug. Real, usable credentials require either re-exporting with sensitive data included, or copy-pasting a raw curl / individual header values directly from DevTools (Copy as cURL / Copy Value), which are NOT redacted.

`SIDCC`/`__Secure-1PSIDCC`/`__Secure-3PSIDCC` rotate frequently (well under a day, observed expiring within roughly an hour or two during active use) — a `.env`-pinned cookie snapshot will start returning 401 on previously-working requests; when that happens, ask for a fresh curl capture rather than assuming a code regression.

## Extracting a curl `--data-raw $'...'` body with octal escapes

curl commands copy-pasted from Firefox often use ANSI-C quoting (`$'...'`) with octal escapes like `\041` for `!` inside the JSON string. Don't hand-unescape these — write the full `BODY=$'...'` assignment verbatim into a bash script file and let bash's own ANSI-C-quote parsing do it:
```bash
cat > /tmp/extract.sh <<'OUTER'
BODY=$'...(paste exact $'...' string here)...'
printf '%s' "$BODY" > /tmp/body_decoded.json
OUTER
bash /tmp/extract.sh
python3 -c "import json; print(json.load(open('/tmp/body_decoded.json')))"
```
This reliably decodes `\041`→`!` and any other octal/hex escapes without manual regex, and lets you `json.load` the result directly.

## Validating a captured credential before trusting it

Never assume a captured cookie/auth pair works. Recompute the SAPISIDHASH from the captured SAPISID + timestamp + origin and compare byte-for-byte against the captured Authorization header. If they don't match, the capture is redacted/stale — don't build on it. If they do match, still do one read-only live call (e.g. `api2thread/list`) before attempting a side-effecting one (e.g. `sendsms`), and never blindly retry a failed send multiple times with different payloads — each attempt may have a real-world side effect (an actual SMS to a real phone number).
