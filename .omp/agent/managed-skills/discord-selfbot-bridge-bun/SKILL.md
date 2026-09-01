---
name: discord-selfbot-bridge-bun
description: "Use when working on the google-voice-ws Discord selfbot bridge (examples/discord-bridge/) — the youtsuho-v13 fork's getUploadURL file_size bug, stale 400-vs-401 send-token diagnosis, phone-number matching, threadId resolution, and the WAA/reCAPTCHA capture-tokens workflow."
---

# Discord selfbot bridge (Bun)

Project: `examples/discord-bridge/` in the google-voice-ws repo. A selfbot (user token, ToS risk — Discord bans selfbots) bridges one Voice phone number with one Discord DM, two-way.

## Stack

- `discord.js-selfbot-youtsuho-v13` (active fork of archived `discord.js-selfbot-v13`; v13-based; string event names `"ready"`/`"messageCreate"`, NO v14 `Events` enum; CommonJS internals; prints a banner on import).
- `google-voice-client` (parent package) via local `link:` — `bun link` in repo root first, then `bun install` in the example dir.
- Playwright (devDep of the example) for the token-capture helper.

## Known fork bug: getUploadURL file_size

Forwarding an attachment to Discord fails with `files[0].file_size: int value should be greater than or equal to 1`.

- Root cause: `Util.getUploadURL` (src/util/Util.js) computes `file_size` from `file.byteLength ?? file.size ?? 0`, but it receives MessagePayload *wrappers* whose actual bytes are at `file.file` — so file_size is always 0 and Discord rejects it.
- Fix (in bridge index.ts): rebind `Util.getUploadURL` via CommonJS `require` (`createRequire`) — an ESM `import * as` namespace is frozen and can't be rebound — to stamp `byteLength` from `f.file?.byteLength ?? f.byteLength ?? 0` before delegating to the original. Deep path: `discord.js-selfbot-youtsuho-v13/src/util/Util` (no bundled .d.ts; cast the require result). Text-only sends unaffected (getUploadURL returns early when files empty).

## Phone-number matching + threadId (the 400 trap)

- Voice returns numbers in E.164 with country code (`+14697590653`); `.env` may hold national form (`4697590653`). NEVER strict-`!==` compare — use digit-only suffix match: `a === b || a.endsWith(b) || b.endsWith(a)`.
- **Wrong threadId → `400 INVALID_ARGUMENT` on sendsms, not 401.** Guessing `t.+${digits}` silently drops the country code (`t.+4697590653` vs real `t.+14697590653`). Resolve the thread from `listThreads()` by matching `otherPartyNumber` with the same suffix-tolerant matcher; cache it. (A 400 ≠ stale tokens; a 401 means no/expired session cookie.)
- Stale WAA/reCAPTCHA send-tokens also yield 400 `INVALID_ARGUMENT` (`voice_error: {"error_code":"INVALID_ARGUMENT"}`) — they're session-recent, expire in minutes-hours, and the SDK cannot mint them.

## Token capture (capture-tokens)

- `bun run capture-tokens` (bin/capture-send-tokens.ts): opens a visible Chromium window on voice.google.com, hooks the network, and extracts the botguard field (body index 10 = `[attestation, null, null, recaptcha]`) from the NEXT `api2thread/sendsms` request — i.e. the USER must send a real message in that window. Writes `GV_SEND_ATTESTATION_TOKEN`/`GV_SEND_RECAPTCHA_TOKEN` to the example `.env`.
- **Headless automation of the mint is NOT viable** (verified): Voice only mints tokens for a real GUI send to a *saved contact*; typing a raw number into "Send new message" → `Enter a name or number` yields "No contacts found" and no `sendsms` ever fires. `waa-pa...Waa/Create` fires, but the per-send mint needs the actual send. Keep the manual visible-browser capture.
- The real composer after picking a contact is a visible `<textarea placeholder="Type a message">` (NOT contenteditable); there's also a hidden reCAPTCHA textarea — never select bare `textarea`.

## Outbound send flow (bridge index.ts)

- Voice → Discord: `voice.on("messageCreate")` filters `direction === "RECEIVED"` + phone match; downloads first attachment via `voice.downloadAttachment(id)` and sends as a file (Buffer + name).
- Discord → Voice: `discord.on("messageCreate")` skips own messages (selfbot loop guard: `author.id === client.user.id`), requires the bridged user, DM/GROUP channel, send-tokens present; strips leading `<@mention>`; attachment-only messages allowed (fetch Discord CDN bytes → `sendMessage` `attachment` option).
- `DEBUG=1` enables verbose logging of every event + filter decision — the first thing to turn on when a relay "isn't working".
- The getUploadURL patch must be applied BEFORE login (it rebinds a module export used at send time).

## Session/cookie side

- `SIDCC`/`__Secure-{1,3}PSIDCC` expire in minutes-hours (the classic 401); long-lived `SID`/`SAPISID` last months. Refresh via parent `bun run refresh-cookies` (browser jar / Playwright login; see google-voice-web-api-reverse-engineering skill).
- The Playwright profile is single-account → `GV_AUTH_USER=0`.
