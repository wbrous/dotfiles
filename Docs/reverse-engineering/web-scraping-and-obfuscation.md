# Scraping and reverse-engineering notes

Hard-won findings from scraping coupon aggregators, decompiling Quizlet's Match highscore obfuscation, and general client-JS reverse-engineering technique.

## Hawk coupon widget: codes are not extractable

**Symptom:** Coupon aggregator pages (TechRadar `/coupons/<brand>`, Tom's Hardware `/coupons/<domain>`, Discoup, other Future plc-network pages) show masked codes (`**********************NUP`) with a "Get Code" button; headless attempts to reveal the code fail.

**Cause:** The real code is never in page HTML/DOM (no `data-code` attribute, no in-page reveal). Clicking triggers an instant same-tab navigation to the retailer (e.g. dell.com) with affiliate params (`cjevent`, `dgc=CJ`, `publisherid`) — the code is fetched via an internal API synchronously with the click and used only for clipboard-copy + redirect, never rendered as text. Pre-attached `page.on('response')`/`page.on('request')` listeners still race the navigation (frame navigates before listeners fire reliably). Retrying causes stale-tab errors (`Cannot read properties of undefined (reading 'click')`) since the tab already navigated.

**Fix:** Don't force-reveal via DOM/network tricks — treat the masked-code list as the ceiling of what's extractable without a real browser session. Report offer *terms* (discount %, category, expiration) from readable page text (always plaintext, reliable). For the code itself, have the user click "Get Code" (auto-copies + redirects) — by design for affiliate tracking. Skip RetailMeNot (Cloudflare "Just a moment..." under headless — use TechRadar/Tom's Hardware/Discoup instead) and couponfollow.com (empty body after full load). Expect `Access Denied` from dell.com product/shop pages under headless Chromium (bot detection) even though aggregator pages load fine — note the block and rely on aggregator + web_search instead of retrying headers.

_Migrated from: coupon-aggregator-hawk-widget-code-reveal_

## Quizlet Match highscore obfuscation (decompiled)

**Symptom:** `POST /{setId}/scatter/highscores` body `{"data": "<dash-joined decimal byte array>"}` looks like a checksum/envelope; byte-diffing alone can't explain variable length or server 500s on edited bytes.

**Cause:** Trivial reversible obfuscation of a plain JSON object, extracted verbatim from Quizlet's own shipped webpack chunk (`chunks/57499-*.js`). NOT a checksum or session-bound envelope:

```js
const payload = {
  score,            // Math.ceil((endTime - startTime + penaltyTime) / 100) — DECISECONDS, lower=better, NOT points
  previous_record,  // account's prior best for this set, or 0
  too_small: 0,
  time_started,     // Date.now()-shaped millisecond timestamp
  selectedOnly,     // whether only starred/selected terms were studied
};
const json = JSON.stringify(payload);
const data = json.split("").map((ch, i) => ch.charCodeAt(0) + (77 % (i + 1))).join("-");
// POST {"data": data}
```
Inverts trivially: `bytes.map((b,i) => String.fromCharCode(b - 77%(i+1))).join('')` then `JSON.parse`. Verified byte-perfect against 5 independent real captured samples (2 accounts, 2 study sets). This explains earlier observations: the "score-digit cipher" (`byte[9]=digit+55`) was coincidental — `JSON.stringify` always starts with `{"score":` (9 chars), so score digits land at index 9+ where `77 % (9+1)=7`, `77 % (10+1)=0`, `77 % (11+1)=5`; "variable payload length" was `previous_record`'s digit count; editing score bytes 500s because it corrupts the JSON length-to-digit relationship, not a checksum. The blob carries NO session/account binding — a payload captured under one account replays under a different logged-in account and records its score; only the request's `qtkn`/cookie identity determines attribution.

**Fix (payload construction / verification):** build with the actual algorithm for any desired completion time (targets a throwaway test set to avoid disturbing real leaderboards); see project artifacts `INFO.md` (§4.4 algorithm, §9 method, §8 verification) and `submit-match-score.ts`.

_Migrated from: quizlet-match-highscore-obfuscation_

## General technique: read the site's own client JS

When traffic-diffing alone isn't enough (checksums, variable structure, "looks obfuscated"), read source instead of guessing:
1. Load the target page in a real cookie-authenticated browser; enumerate `document.querySelectorAll('script[src]')` (webpack/Next.js splits into many content-hashed chunks, no stable names).
2. Fetch every chunk in parallel from *inside the tab* (`fetch(url).then(r=>r.text())` via the browser tool's evaluate — reuses the page's own `cf_clearance`/session) and grep for endpoint keywords (e.g. `"scatter"` + `"highscores"`); usually one or two chunks match out of dozens.
3. Locate the literal action/endpoint string (e.g. `"saveScore"`, a Redux `createAsyncThunk` name) and read outward — minified code keeps control flow, literal constants, and field names intact, often directly readable without deobfuscation.
4. Verify the recovered algorithm against every real captured sample.

Diffing captures *behavior*; reading source gives the *actual mechanism* — and is often faster than inferring a cipher from samples.

_Migrated from: quizlet-match-highscore-obfuscation_

## Quizlet live-session gotchas

- Automated headless signup is reliably blocked: `POST /webapi/3.8/direct-signup` → `400 {"error":{"message":"Invalid reCAPTCHA token"}}` — reCAPTCHA Enterprise (invisible) scores headless Chromium as non-human regardless of human-paced typing. Don't try stealth/fingerprint patches. If a retry returns `401 direct_signup_email_in_use`, pivot to the "Log in" link the form surfaces — headless *login* is not blocked the same way.
- Match gameplay is click-to-select-then-click-to-match, NOT drag-and-drop (drags just trigger text selection). Tile positions: walk DOM leaf elements (`children.length===0`) matching known term/definition text, read `getBoundingClientRect()` — no stable selectors exist.
- Rapid uniform clicking trips a PerimeterX "Press & Hold" challenge (nested `about:blank` iframe — recursively walk `page.mainFrame().childFrames()` matching `document.body.innerText` to find the real challenge frame among decoys). A single scripted press-and-hold (`elementHandle.click({delay: 2500})`) was rejected ("Please try again"). Don't defeat it — spawn a visible non-headless browser window so a real human plays; real input passes with no special handling. To capture the resulting request across separate tool calls without racing the human: attach `page.on('response', ...)` pushing into `globalThis.__someKey` (not a closure local — those don't survive separate `run` invocations on the same tab), then poll it back after giving the human time.

_Migrated from: quizlet-match-highscore-obfuscation_
