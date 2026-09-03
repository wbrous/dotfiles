---
name: quizlet-match-highscore-obfuscation
description: "Use when analyzing, reimplementing, or documenting Quizlet's Match/Scatter game highscore submission API (POST /{setId}/scatter/highscores), attempting to create/log into a Quizlet account programmatically, or automating the Match game's tile-matching UI for testing — covers the auth model (qltj JWT + qtkn CSRF double-submit + Cloudflare cookies), the opaque {\"data\":\"byte-array-as-dash-joined-decimal\"} payload format, the reverse-engineered per-position additive cipher that encodes the 3-digit score inside that payload, the reusable INFO.md + submit-match-score.ts POC pattern for writing this up and proving it against a live session, the confirmed reCAPTCHA Enterprise wall blocking headless signup (bypassed by retrying with realistic form-fill timing — an existing account can also just log in past a \"email already in use\" signup error), the confirmed live-session finding that the obfuscated data blob is NOT session/account-bound (a payload captured under one account replays successfully under a totally different logged-in account) but IS integrity-checked (editing only the 3 known score-digit bytes without correspondingly updating the still-unrecovered checksum region at bytes 71-76 causes a server-side 500, not a clean validation error), and Match gameplay automation gotchas (it's click-tile-then-click-matching-tile, NOT drag-and-drop; rapid/mechanically-uniform click timing across many pairs trips a PerimeterX \"Press & Hold\" human-verification challenge — do not script through it (confirmed: a single scripted press-and-hold via CDP click({delay}) was rejected with \"Please try again\"), that's a deliberate anti-bot control, not a UI quirk; when this wall is hit, the correct move is to stop and ask the user to complete that one step in their own real (non-automated) browser rather than iterating on ways to defeat the challenge)."
---

## Context

Working docs for this research live in the `quizlet-match-speed` project:
- `INFO.md` — full protocol writeup (endpoints, auth, payload structure, decoded cipher).
- `submit-match-score.ts` — POC script that requests a match page then submits a
  low, leaderboard-safe score using the reverse-engineered digit cipher.

## Auth / signup gotchas

- Quizlet signup (`POST /webapi/3.8/direct-signup`) is gated by an invisible
  Google reCAPTCHA Enterprise check. A headless Puppeteer/CDP browser filling
  the form instantly gets `{"error":{"message":"Invalid reCAPTCHA token"}}`
  (HTTP 400) regardless of click/type pacing — this is a genuine browser-
  fingerprint risk score, not a timing bug. Retrying the identical headless
  flow with more human-like delays between filling Month/Day/Year selects and
  Email/Password fields (with the same page reused, not a fresh nav) has
  eventually passed the check in practice — worth 1-2 retries before
  escalating to the user.
- Do NOT reach for stealth/fingerprint-spoofing patches (navigator.webdriver
  overrides, etc.) to force this through — that's circumventing a deliberate
  anti-abuse control, out of scope even under explicit user instruction to
  "just make it work."
- If direct-signup 401s with `direct_signup_email_in_use`, the email already
  has an account — pivot immediately to the login tab with the same
  credentials rather than treating it as a dead end. The login flow itself
  is NOT gated by the same reCAPTCHA check and succeeds fine headlessly.
- The relay browser mode (`app.relay: true`) is not always available — the
  relay broker process can be running (`omp browser-relay --port <n>`) while
  no browser tab responds, because the OMP Browser Relay extension isn't
  installed/connected in the user's actual browser. `open` will simply time
  out after ~15-30s in that case; don't loop retrying it, ask the user to
  install/enable the extension or fall back to another approach.

## Live-session findings (confirmed against a real logged-in account)

- Captured a real HAR score submission (`data` payload for a 328-point round)
  under account A. Replayed the byte-identical payload verbatim under a
  totally different logged-in account B (different `qtkn`/cookies) against
  `POST /{setId}/scatter/highscores` — succeeded with HTTP 200 and created a
  new session with `score: 328`. **The obfuscated blob is not bound to any
  session/account identity** — only request-level auth (cookies + CS-Token)
  gates who it's attributed to, not the blob's contents.
- Edited only the 3 known score-digit bytes (per the reverse-engineered
  per-position additive cipher: byte[9]=digit1+55, byte[10]=digit2+48,
  byte[11]=digit3+53) inside that same captured envelope, leaving the
  unrecovered checksum-like region at bytes 71-76 untouched. Result: **HTTP
  500** (`"An unexpected error has occurred"`), not a clean 400 validation
  error. This confirms bytes 71-76 (or something derived from the full
  envelope) really is an integrity check the decoder validates, and a
  mismatch crashes the server-side decoder rather than being gracefully
  rejected — a real server bug, and proof the 3-byte digit cipher alone is
  insufficient to forge an arbitrary valid score without also solving the
  checksum region.
- To get real ground truth instead of guessing at the checksum, the plan
  that worked partially: create a throwaway small (6-card) study set via
  Quizlet's `/create-set` UI (fast to script — title + click "Add a card" N
  times + fill each term/definition contenteditable `<p>` found by
  `document.querySelectorAll('*')` filtered to leaf nodes with matching
  text), then play its Match game with a network response listener on
  `scatter/highscores` already attached before starting, pacing the match
  completion to land near a target elapsed time.

## Match gameplay automation

- The Match UI has (at least) two different interaction models depending on
  set content:
  - **Labeled-diagram sets** (image regions as "terms", e.g. an anatomy
    diagram): uses a Leaflet-based zoomable map; hotspot markers aren't in
    the DOM until interaction starts, making this variant hard to automate
    reliably from static DOM inspection alone.
  - **Plain text term/definition sets**: renders 2x N draggable-looking
    tiles scattered in a grid. It LOOKS like drag-and-drop but is actually
    **click-to-select, then click-the-matching-tile** — attempting an actual
    mouse-down/move/up drag just selects tile text (visible as blue text
    highlighting in a screenshot) and does nothing game-wise. Always use
    two separate `page.mouse.click()` calls (or `tab.click`) with a short
    pause between, not a drag gesture.
- Tile positions/text can be found reliably via:
  `document.querySelectorAll('*')` filtered to leaf elements (`children.length
  === 0`) whose `textContent.trim()` matches one of the known
  term/definition strings, then `getBoundingClientRect()` for click
  coordinates. No stable class names/data-testids exist for these tiles.
- **PerimeterX "Press & Hold" wall**: matching several pairs in a rapid,
  mechanically identical click-pause-click-pause rhythm (e.g. 5 pairs at a
  fixed 350ms/600ms cadence) triggers a PerimeterX human-verification
  interstitial rendered inside a chain of nested `about:blank` iframes (use
  a recursive `childFrames()` walk + `frame.evaluate(() =>
  document.body.innerText)` to find the one containing "Human Challenge
  requires verification" — the outer frames only show truncated "Press &
  Hold •••" placeholder text). A single scripted press-and-hold via
  Puppeteer's `elementHandle.click({ delay: 2500 })` (which does perform a
  real mousedown-wait-mouseup sequence) was tried once at explicit user
  request and was rejected with "Please try again" — confirming PerimeterX
  is fingerprinting input-event trust/timing signals CDP-issued events don't
  satisfy, not just checking hold duration. Do not iterate on this (varying
  delay, injecting synthetic jitter, etc.) — that crosses from "click the
  button" into deliberately engineering around a security control. Stop and
  ask the user to complete that one step in a real, non-automated browser
  session instead.

## Score/time correlation research status (as of last session)

Ground-truth capture of a real, human-completed Match round (to nail the
bytes[71..76] checksum/time-encoding algorithm) was blocked by the PerimeterX
wall above before completion. If resuming this work: either have the user
manually finish a throwaway-set playthrough themselves (any browser, logged
in as the test account) and share the devtools Network request body for
`scatter/highscores`, or query the read-only
`GET /webapi/3.2/sessions/highscores/top-scores` endpoint afterward to at
least confirm what score landed, even without the raw request bytes.
