---
name: quizlet-match-highscore-obfuscation
description: "Use when analyzing, reimplementing, or documenting Quizlet's Match/Scatter game highscore submission API (POST /{setId}/scatter/highscores), or when attempting to create a Quizlet account programmatically for testing — covers the auth model (qltj JWT + qtkn CSRF double-submit + Cloudflare cookies), the opaque {\"data\":\"byte-array-as-dash-joined-decimal\"} payload format, the reverse-engineered per-position additive cipher that encodes the 3-digit score inside that payload, the reusable INFO.md + submit-match-score.ts POC pattern for writing this up and proving it against a live session, and the confirmed reCAPTCHA Enterprise wall blocking headless-browser signup."
---

## Score submission cipher (Quizlet Match/Scatter)

See prior version of this skill / INFO.md in quizlet-match-speed repo for the full writeup. Key recovered fact: in the 99-byte envelope sent as `{"data":"<dash-joined-decimal>"}` to `POST /{setId}/scatter/highscores`, the 3-digit score is encoded at byte offsets 9/10/11 via fixed per-position additive offsets:

- `byte[9]  = hundredsDigit + 55`
- `byte[10] = tensDigit + 48`
- `byte[11] = onesDigit + 53`

Confirmed exactly against 3 real captured submissions (328, 278, 172). All other bytes are constant across submissions in the same session except a 6-byte region at offsets 71-76 that varies with score but was never decoded (likely a time/checksum field) — reforging an arbitrary score requires cracking that region too, unverified.

## Headless browser signup is blocked by reCAPTCHA Enterprise — do not try to bypass

Quizlet's `/sign-up` flow embeds an **invisible Google reCAPTCHA Enterprise** widget (iframe url pattern: `google.com/recaptcha/enterprise/anchor?...size=invisible...`). Submitting the signup form (`POST /webapi/3.8/direct-signup`) from a headless Chromium browser (via the `browser` xd tool without `app.relay`) reliably returns:

```
400 {"error":{"message":"Invalid reCAPTCHA token","code":400,"identifier":"client_developer_error"}}
```

This reproduces **every time**, regardless of human-like pacing (staggered field fills, delays before submit, delay after page load before interacting). It is not a timing/race issue — it's the invisible reCAPTCHA scoring the browser *environment itself* (headless `navigator.webdriver=true`, no real GPU/plugin fingerprint, etc.), not the interaction pattern.

**Do not attempt to defeat this with stealth/fingerprint-spoofing patches** (e.g. puppeteer-extra-stealth-style overrides) — this is a deliberate anti-abuse control, not a UI quirk, and circumventing it is out of scope for a coding-agent task even when the user asks to "just make an account."

### The only viable paths forward
1. **Browser relay** (`app.relay: true` on the `browser` xd tool) driving the user's own real, already-authenticated Chrome — requires the OMP Browser Relay extension to actually be installed/connected in that browser. If the relay `open` call times out (~30s) with no error detail, the extension is very likely not installed/connected — check for it before assuming relay will work, and tell the user directly rather than retrying blindly.
2. **Manual signup handoff**: ask the user to sign up themselves in any real browser (solves the captcha inherently), then paste back the resulting `Cookie:` header + `qtkn` cookie value so a script (e.g. `submit-match-score.ts`, see companion repo) can drive the account's session directly — no captcha involved for authenticated API calls after that point, since the highscore endpoint itself has no captcha, only signup does.

When a user asks to "make an account and figure it out" for a site with invisible reCAPTCHA on signup, proactively check for relay extension availability first (cheap timeout check), then default to recommending the manual-handoff path since it's the fastest guaranteed route.
