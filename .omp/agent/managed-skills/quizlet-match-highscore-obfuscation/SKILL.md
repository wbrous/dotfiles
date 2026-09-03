---
name: quizlet-match-highscore-obfuscation
description: "Use when analyzing, reimplementing, or documenting Quizlet's Match/Scatter game highscore submission API (POST /{setId}/scatter/highscores) — covers the auth model (qltj JWT + qtkn CSRF double-submit + Cloudflare cookies), the opaque {\"data\":\"byte-array-as-dash-joined-decimal\"} payload format, the reverse-engineered per-position additive cipher that encodes the 3-digit score inside that payload, and the reusable INFO.md + submit-match-score.ts POC pattern for writing this up and proving it against a live session."
---

## Source material

Full reverse-engineering writeup lives in `INFO.md` in the
`quizlet-match-speed` project (built from a HAR capture,
`quizlet.com_highscore.har`, of three real Match playthroughs). A working
TypeScript POC that exercises the documented flow lives alongside it as
`submit-match-score.ts`. Read both before re-deriving anything — this skill
is a pointer/summary, not a replacement for them.

## Auth model

- `qltj` — HS384 JWT identity cookie (user id, email, issuer). Rolling
  expiry, refreshed via `Set-Cookie` on almost every response.
- `qlts` — long-lived (~400 day) session/tracking token cookie.
- `qtkn` — CSRF/session security token. Its value must be echoed verbatim
  into both the `CS-Token` and `X-Quizlet-API-Security-ID` request headers
  on the highscore POST (double-submit-cookie CSRF pattern).
- `cf_clearance`, `__cf_bm`, `_pxhd`, `_cfuvid` — Cloudflare bot-management
  cookies; requests without valid ones get a challenge page instead of a
  response.
- No separate public API key exists — submitting a highscore requires a
  full logged-in browser session cookie jar.

## Endpoint

`POST https://quizlet.com/{setId}/scatter/highscores`
Body: `{"data": "<99 decimal bytes, dash-joined>"}` (e.g.
`"123-35-117-100-...-202"`). Endpoint name is legacy ("scatter" = old name
for Match). Response echoes the server's own decoded/canonical `score` in
a `session` model — the server is authoritative, not the client.

## The cipher (partially recovered)

Diffing three real submissions (scores 328, 278, 172) byte-for-byte showed:

- **Bytes 9–11 (0-indexed) encode the 3-digit score**, one digit per byte,
  each position with its own fixed additive offset:
  - `byte[9]  = hundreds_digit + 55`
  - `byte[10] = tens_digit + 48`
  - `byte[11] = ones_digit + 53`
  Confirmed exactly against all three samples (328→3,2,8; 278→2,7,8;
  172→1,7,2).
- **Bytes 71–76 vary in lock-step with score but do NOT follow the same
  offset rule** — almost certainly an elapsed-time or checksum field the
  server cross-validates against the score digits. This region was
  **never fully decoded** — no ground-truth time value existed in the HAR
  to correlate against it.
- All other 90 of the 99 bytes are byte-for-byte constant across every
  submission in the same session (game-mode/set/client-version framing,
  possibly a session-stable nonce).

## Reusable POC pattern (submit-match-score.ts)

1. GET the Match page's Next.js SSR `match.json` route first (mirrors
   "loading the game" before playing).
2. Take a captured 99-byte envelope as a template, override only bytes
   9/10/11 via the digit cipher above for the desired (deliberately low,
   leaderboard-safe) score, leave bytes 71–76 as captured.
3. POST with `CS-Token` / `X-Quizlet-API-Security-ID` headers = the
   session's `qtkn` cookie value.
4. Report whatever score the server actually persists — since bytes 71–76
   are unresolved, the returned score may not match the requested one;
   that mismatch (or lack thereof) is itself the useful signal.

**Cannot verify without live cookies.** The HAR's session cookies expire /
rotate (`cf_clearance` especially); running the POC for real requires the
user's own fresh `QUIZLET_COOKIE` + `QUIZLET_QTKN` from a live logged-in
browser session — state this limitation explicitly rather than fabricating
a live run.

## Style note

This repo enforces a `ts-no-tiny-functions` rule: don't wrap a single
`return <expr>` in a named function unless it has 3+ call sites or documents
a non-obvious formula. Inline one-liners (e.g. build headers as a `const`
object spread with `...BASE_HEADERS`, not a `baseHeaders()` function; inline
`bytes.join("-")` at its one call site instead of a named
`encodeDataField` wrapper).
