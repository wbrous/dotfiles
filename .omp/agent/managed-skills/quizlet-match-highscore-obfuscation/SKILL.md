---
name: quizlet-match-highscore-obfuscation
description: "Use when analyzing, reimplementing, or documenting Quizlet's Match/Scatter game highscore submission API (POST /{setId}/scatter/highscores) — covers the auth model (qltj JWT + qtkn CSRF double-submit + Cloudflare cookies), the opaque {\"data\":\"byte-array-as-dash-joined-decimal\"} payload format, and the reverse-engineered per-position additive cipher that encodes the 3-digit score inside that payload."
---

## Context
Quizlet's Match game score submission (`POST https://quizlet.com/{setId}/scatter/highscores`)
does not send a plain numeric score. It sends `{"data": "<N dash-joined decimal
bytes>"}` — an obfuscated byte array built client-side in Quizlet's JS bundle.
The server decodes it, persists a `session` row, and echoes back the canonical
`score` in the response (server is authoritative; client can't just POST a
fake score field).

Full findings written up in a prior task's deliverable: see
`quizlet-match-speed/INFO.md` in that project (if still present) for the
complete request/response reference, endpoint table, auth cookie breakdown,
and telemetry-vs-scoring separation (LogRocket via jg7y.quizlet.com,
el.quizlet.com, Braze — all unrelated to scoring).

## Reverse-engineered cipher (score portion)
Diffing 3 real submissions (scores 328, 278, 172) from the same session showed
the payload is byte-identical except at a few positions. The 3-digit score is
encoded at a fixed offset (index 9,10,11 in the observed 99-byte payloads)
using **per-position additive offsets**:

- `byte[9]  = hundreds_digit + 55`
- `byte[10] = tens_digit     + 48`
- `byte[11] = ones_digit     + 53`

Verified exactly against all 3 samples (328→3,2,8; 278→2,7,8; 172→1,7,2).
This is a trivial Caesar-style cipher, not real crypto — just enough to stop
naive tampering.

A separate 6-byte region (~index 71-76 in the samples) also varies with score
but does NOT follow the same rule — likely an elapsed-time-derived checksum
the server cross-validates against the score. NOT decoded; no ground-truth
time value was available in the captured HAR to correlate against.

All other ~90 of 99 bytes were constant across every submission in the same
browser session — likely game-mode/set/client-version framing or a
session-stable key, not randomized per-request.

## Caveats / what's still unknown
- Digit-offset rule only confirmed for 3-digit scores; untested for 1, 2, or
  4+ digit scores (offset-per-position pattern may not generalize the same way).
- The 6-byte "checksum" region is unsolved — would need more samples with a
  known correlated time value to crack.
- Full reimplementation requires the actual Quizlet frontend JS (not present
  in network traffic) to know the general byte-layout algorithm beyond what
  was diffed.

## Method used to find this
1. Grep HAR for repeated POSTs to `scatter/highscores`, pull the `data` field
   and the response's decoded `score` from 3+ separate submissions.
2. Diff the byte arrays pairwise (Python) to find which indices change.
3. Correlate changed-byte values against known digits of the score to find
   the arithmetic relationship (simple `value - digit` per position, check
   for a constant offset).
