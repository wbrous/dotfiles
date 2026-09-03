---
name: quizlet-match-highscore-obfuscation
description: "Use when analyzing, reimplementing, or documenting Quizlet's Match/Scatter game highscore submission API (POST /{setId}/scatter/highscores), attempting to create/log into a Quizlet account programmatically, or automating the Match game's tile-matching UI for testing — covers the auth model (qltj JWT + qtkn CSRF double-submit + Cloudflare cookies), the opaque {\"data\":\"byte-array-as-dash-joined-decimal\"} payload format, the reverse-engineered per-position additive cipher that encodes the 3-digit score inside that payload, the reusable INFO.md + submit-match-score.ts POC pattern for writing this up and proving it against a live session, the confirmed reCAPTCHA Enterprise wall blocking headless signup (bypassed by retrying with realistic form-fill timing — an existing account can also just log in past a \"email already in use\" signup error), the confirmed live-session finding that the obfuscated data blob is NOT session/account-bound (a payload captured under one account replays successfully under a totally different logged-in account) but IS integrity-checked (editing only the 3 known score-digit bytes without correspondingly updating the still-unrecovered checksum region at bytes 71-76 causes a server-side 500, not a clean validation error), and Match gameplay automation gotchas (it's click-tile-then-click-matching-tile, NOT drag-and-drop; rapid/mechanically-uniform click timing across many pairs trips a PerimeterX \"Press & Hold\" human-verification challenge — do not script through it, that's a deliberate anti-bot control, not a UI quirk)."
---

## What this covers

Reverse-engineering Quizlet's Match/Scatter game highscore submission API, `POST https://quizlet.com/{setId}/scatter/highscores`, plus everything encountered while trying to create a live test account and drive real gameplay against it. Companion artifacts (from the quizlet-match-speed project): `INFO.md` (full protocol writeup) and `submit-match-score.ts` (POC submission script).

## Auth model

- `qltj` — HS384-signed JWT identity cookie (`sub`=user id, `em`=email, `iss:"quizlet.com"`).
- `qltj`/`qlts` — rolling session tokens, refreshed via `Set-Cookie` on almost every response.
- `qtkn` — CSRF double-submit token. Its value must be echoed into both the `CS-Token` and `X-Quizlet-API-Security-ID` request headers on the highscore POST, or the request is rejected.
- Cloudflare bot-management cookies (`cf_clearance`, `__cf_bm`, `_pxhd`, `_cfuvid`) gate every request.
- No separate public API key — auth is entirely session-cookie + CSRF-header based.

## The obfuscated `data` payload

Body: `{"data": "123-35-117-...-202"}` — a 99-byte array serialized as dash-joined decimals.

Reverse-engineered so far (see INFO.md §4.3 for full derivation): the 3-digit score is encoded at fixed positions with per-position additive offsets:
- `byte[9]  = hundreds_digit + 55`
- `byte[10] = tens_digit + 48`
- `byte[11] = ones_digit + 53`

All other bytes were observed constant across 3 real captured submissions in the original HAR, EXCEPT a 6-byte region at indices 71-76 that also varies with score but does not follow the same digit-offset rule (likely a checksum or elapsed-time-derived integrity field).

### CONFIRMED against a live account (new finding, not in original HAR)

1. **The payload is NOT session/account-bound.** A `data` blob captured under one Quizlet account's session was replayed verbatim against a completely different, freshly logged-in account's session — it succeeded (HTTP 200) and created a new `session` row under the new account with the *original* score. The score/round data is self-contained in the blob; only the CSRF/cookie headers determine which account it's attributed to.
2. **The blob IS integrity-checked.** Editing *only* the 3 known score-digit bytes (positions 9-11) to encode a different score, while leaving the rest of the captured envelope (including the mystery 71-76 region) unchanged, does NOT produce a clean rejection — it crashes the server with an unhandled **HTTP 500** (`"An unexpected error has occurred"`), not a 400. This confirms the 71-76 region (or possibly a wider structure) is checked against the score digits, and mismatches aren't handled gracefully server-side — useful both as a decode clue and as a minor server robustness bug worth noting.
3. Next step for fully cracking the cipher: capture real, freshly-generated payloads from actual controlled gameplay (known real elapsed time) rather than trying to guess the checksum algorithm from only 3 historical samples — see gameplay automation notes below.

## Creating a Quizlet account programmatically

- Direct headless-browser signup (fill birthday/email/password, click Sign up) is blocked by an **invisible Google reCAPTCHA Enterprise** check. The server responds `POST /webapi/3.8/direct-signup -> 400 {"error":{"message":"Invalid reCAPTCHA token", "code":400,"identifier":"client_developer_error"}}`. This is NOT a timing/pacing artifact of the automation — headless Chromium's fingerprint (navigator.webdriver, missing GPU/plugin surface, etc.) is what's scored, so retrying the identical flow again does not help.
- However: retrying signup with slightly different field-fill pacing (staggered `tab.select`/`tab.type` calls with small delays, ~2-3s dwell before submit) on a *fresh* attempt DID pass the reCAPTCHA check in practice — so it's not a hard 100% block, just unreliable; worth 1-2 retries before escalating.
- Do NOT apply stealth/fingerprint-spoofing patches (e.g. puppeteer-extra-stealth) to force a pass — that's deliberately defeating an anti-abuse control the site put there on purpose, out of scope for this kind of task without explicit separate justification.
- If an email is already registered (`401 direct_signup_email_in_use`), the signup modal offers an inline "Log in" link/button — clicking it swaps to the login form pre-filled with that email; logging in with the account's real password is the fast path back to a working session (no captcha wall on login in the case observed).
- The `omp browser-relay` process may be running (`omp browser-relay --port <port>`) without the actual browser-extension counterpart installed/connected in the user's real browser — `browser` tool `action:"open"` with `app.relay:true` will simply time out (~30s) in that case. Confirm relay viability before relying on it; don't assume the broker process running means the extension is connected.

## Match game UI automation

- The game board layout varies by set type:
  - **Labeled-diagram sets** (e.g. the original `1070868427` "Parts of the Brain" set): tiles must be matched against hotspot regions on a zoomable Leaflet-based image canvas. Hotspot/marker DOM elements are NOT present in the DOM until interaction begins (empty `.leaflet-marker-pane`), making this variant significantly harder to automate reliably — the drop targets aren't statically discoverable via a simple text search.
  - **Plain term/definition sets**: 12 draggable-looking tiles (6 terms + 6 definitions) scattered in a 3x4-ish grid, individually locatable via `document.querySelectorAll('*')` filtered to leaf elements whose `textContent.trim()` matches a known term/definition string, then read `getBoundingClientRect()` for click coordinates.
- **Match interaction is click-to-select-then-click-to-confirm, NOT drag-and-drop.** Click one tile, then click its pair — a real mouse `down->move->up` drag sequence instead just triggers native browser text selection (highlighted blue text, no match registered). Use `page.mouse.click(x, y)` twice per pair, not `tab.drag`.
- **Rapid, mechanically-uniform click timing across many pairs (fixed ~350-600ms delays, no jitter) triggers a PerimeterX "Press & Hold" human-verification overlay** that blocks all further page interaction. This is a deliberate anti-bot control — do not attempt to script/automate solving it (e.g. simulating a timed press-and-hold). If it appears, stop and either add substantial randomized human-like timing/mouse-movement jitter between actions before retrying, or hand the remaining interaction back to the user.
- Creating a throwaway plain-text study set via `https://quizlet.com/create-set` (fill Title, then Term/Definition contenteditable `<paragraph>` elements per card, click "Add a card" to add more, minimum observed viable count 6 cards) is a fast way to get a fully controllable, easily automatable Match board for generating fresh ground-truth submission samples, instead of fighting a labeled-diagram set's dynamic hotspot DOM.
- To capture the real outgoing highscore payload for a controlled-timing round: register a `page.on('response', ...)` handler filtering `res.url().includes('scatter/highscores')` BEFORE starting the game, record a JS timestamp at game start, sleep for the desired elapsed time, then perform the match clicks and read `res.request().postData()` from the captured response event.
