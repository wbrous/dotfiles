---
name: discord-selfbot-bridge-bun
description: "Use when working on the google-voice-ws Discord selfbot bridge (examples/discord-bridge): user-token login with discord.js-selfbot-youtsuho-v13, phone↔DM bridging, the outbound 400-wrong-threadId trap, the getUploadURL file_size fork bug + CJS monkey-patch, and why fully-headless WAA/reCAPTCHA token capture is impossible (manual capture-tokens only)."
---

# Discord selfbot bridge (bun)

Bridges one Google Voice phone number with one Discord DM by logging in as YOUR OWN Discord user account (a "selfbot"). Project: `/home/wils/Documents/Development/google-voice-ws/examples/discord-bridge` (own package.json; deps: `discord.js-selfbot-youtsuho-v13` (active fork of archived selfbot-v13) + `google-voice-client` via `link:`).

## ⚠️ ToS / ban risk
Discord explicitly bans selfbots (user-token login) — accounts get deactivated. Use a throwaway account; never assume a warning. This is the account owner's own call, but flag it loudly in code/docs.

## Key env
- `GV_*` — Voice session (see main repo).
- `DISCORD_TOKEN` — YOUR USER token (not a bot token).
- `BRIDGE_DM_USER_ID`, `BRIDGE_PHONE` (E.164 or national — matching is lenient).
- `BRIDGE_CONTACT_IMAGE` — optional Google Contact avatar URL; shown as a Discord embed author icon on forwarded messages so a wrong source is obvious.
- `GV_SEND_ATTESTATION_TOKEN` / `GV_SEND_RECAPTCHA_TOKEN` — required for outbound (Discord→phone); minted live by Google, session-recent (minutes-hours).
- `DEBUG=1` — verbose logs of every event + filter decision.

## Wire/behavior facts (verified live)
- **Phone matching is suffix-tolerant** (`numbersMatch`): `4697590653` matches `+14697590653` (country code optional). Inbound `otherPartyNumber` is E.164 with `+1`.
- **Outbound 400 INVALID_ARGUMENT is a WRONG THREADID, not stale tokens** (the classic red herring). Do NOT derive `t.+<digits>` from `BRIDGE_PHONE` without the country code — the real thread is `t.+14697590653`, not `t.+4697590653`. Fix: `resolveThreadId()` queries `listThreads()` and finds the thread whose `otherPartyNumber` matches (cached). Verified: sending to the resolved thread succeeds and returns a real message id.
- **`getUploadURL` file_size bug in the selfbot fork**: `Util.getUploadURL` computes Discord `file_size` from `file.byteLength`, but receives MessagePayload wrappers whose bytes live at `file.file` → sends `file_size: 0` → Discord rejects `files[0].file_size >= 1`. Fix: rebind via CJS `require` (ESM `import * as` namespace is frozen) and stamp `byteLength` from `.file` before delegating. Deep import path is `src/util/Util` (package ships no types for it).
- **MMS both ways**: Voice→Discord downloads attachment via `voice.downloadAttachment` and sends as file; Discord→phone downloads first `message.attachments` via plain fetch and passes `attachment` to `sendMessage` (client already supports `[2, base64]` mediaField). Attachment-only DMs must not be skipped when a photo is present.

## Token refresh — the honest wall
- Manual path that WORKS: `bun run capture-tokens` — opens a visible browser; user sends one real text; helper intercepts `sendsms` (body index 10 `[attestation,null,null,recaptcha]`) and writes `.env`.
- **Fully-headless automated capture DOES NOT work**: even with the phone saved as a contact and correctly selected ("Wilson Brous" resolves; composer opens), `sendsms` never fires headless (0 network hits). Typing a raw number yields "No contacts found" (Voice mints only for saved contacts); typing the name resolves the contact but a scripted send is still not minted. Google gates the anti-abuse token mint to genuine interactive sends. Do NOT ship a flaky auto-loop; do not attempt to defeat bot detection. Every ~few hours: run `capture-tokens` (or when outbound 400s).

## Gotchas
- `file:../..` copies without `dist/` (gitignored) → use `bun link` in the parent repo, then `"google-voice-client": "link:google-voice-client"` in the bridge.
- Parent `bun run build` required after library changes before the bridge sees them.
- Playwright for capture helpers: `--disable-blink-features=AutomationControlled` + no-HeadlessChrome UA + hide `navigator.webdriver` (same mitigations as login).
- Selfbot fork emits a banner on import (harmless).
