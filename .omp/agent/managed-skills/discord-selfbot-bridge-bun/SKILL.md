---
name: discord-selfbot-bridge-bun
description: "Use when working on the google-voice-ws Discord selfbot bridge (examples/discord-bridge/): the youtsuho-v13 selfbot fork's getUploadURL file_size bug, lenient phone matching, self-loop guard, WAA/reCAPTCHA token capture, and bun link/lockfile gotchas."
---

# discord-selfbot-bridge-bun

Working notes for the Discord selfbot bridge in `examples/discord-bridge/` (this repo's bridge between one Google Voice phone number and one Discord DM, running as the user's own Discord account).

## Architecture

- `index.ts`: selfbot via `discord.js-selfbot-youtsuho-v13` (the active fork of the archived `discord.js-selfbot-v13`). String event names ("ready"/"messageCreate"), NOT the v14 `Events` enum. `google-voice-client` is linked via `bun link` (not `file:` — the `file:` protocol stages gitignored `dist/` and the link breaks).
- Two directions:
  - Voice → Discord: `voice.on("messageCreate")` → filter `RECEIVED` + phone match → `dm.send` (text or `files:[{attachment: Buffer, name}]`).
  - Discord → Voice: `discord.on("messageCreate")` → ignore self (`author.id === discord.user?.id`, otherwise it loops), require `BRIDGE_DM_USER_ID`, DM/GROUP channel only → `voice.sendMessage(threadId, text, tmpId, { tokens, attachment })`.
- `bin/capture-send-tokens.ts`: captures fresh WAA/BotGuard + reCAPTCHA tokens for outbound sends by intercepting a real `api2thread/sendsms` request (body[10] = `[attestation, null, null, recaptcha]`) in a Playwright browser window, then writes `GV_SEND_ATTESTATION_TOKEN`/`GV_SEND_RECAPTCHA_TOKEN` to `.env`.
- `DEBUG=1` env enables verbose logging of every event + filter decision.

## Gotchas (all hit in real sessions)

### 1. Selfbot fork `getUploadURL` file_size bug (attachment forward fails)
Voice→Discord attachment sends fail with `files[0].file_size: int value should be greater than or equal to 1`. Root cause: the fork's `Util.getUploadURL` (src/util/Util.js) computes `file_size: file.byteLength ?? file.size ?? 0` from the **MessagePayload wrapper**, but the actual bytes are at `wrapper.file` — so it always sends `file_size: 0`. Fix: rebind `Util.getUploadURL` via CJS `require` (an ESM `import * as` namespace is frozen and can't be rebound) to stamp `byteLength` from `f.file?.byteLength` before delegating to the original. Import path is `discord.js-selfbot-youtsuho-v13/src/util/Util` (not `lib/`); no `.d.ts` exists there — the bridge declares the module shape inline on the require cast. The bridge's `index.ts` has the exact patch.

### 2. Phone matching: E.164 vs national format
Voice returns `+14697590653` (E.164 with country code), but `BRIDGE_PHONE` in `.env` is often `4697590653` (national, no `+`). Strict `!==` drops every message (visible in DEBUG as `otherParty` vs `wantParty`). Fix: compare on digits with suffix matching (`a.endsWith(b) || b.endsWith(a)`) — tolerates missing `+`, country-code differences, spacing. `threadId` is `t.+<digits>` (strip the `+` before building it or you get `t.++…`).

### 3. Selfbot loop guard
The selfbot's OWN forwarded messages fire `messageCreate` too. Must ignore `author.id === discord.user?.id` before anything else, or the bridge echoes every forward back into the phone.

### 4. Selfbot ToS risk
Using a user token is a Discord ToS violation → account deactivation. The skill/bridge flags this; never present it as risk-free, always recommend a throwaway account.

### 5. Outbound sends need live tokens
`sendsms` 401s without `[attestationToken, null, null, recaptchaToken]`. They're minted by Google's page JS, session-recent, NOT bound to message text. Can't be fabricated; re-capture with `capture-send-tokens` (user must send a real text in the browser window).

### 6. `bun install` lockfile stalls in this example dir
Fresh lockfile regeneration (`rm bun.lock && bun install`) resolved repeated "Resolved, downloaded and extracted [0]" hangs when adding the selfbot fork.

## Verification shortcuts

- Reproduce the fork's wrapper shape: `MessagePayload.resolveFile({attachment: Buffer.from("x"), name})` → `{ file: Buffer, name, ... }` with NO top-level `byteLength`.
- Sanity check numbersMatch with the exact failing pair: `+14697590653` vs `4697590653` must MATCH; a truly different number must not.
- Parent suite must stay 44/44 + typecheck + build after bridge changes.
