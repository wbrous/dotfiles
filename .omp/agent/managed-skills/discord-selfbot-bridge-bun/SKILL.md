---
name: discord-selfbot-bridge-bun
description: "Use when working on the google-voice-ws Discord selfbot bridge (examples/discord-bridge/) — the youtsuho-v13 fork's getUploadURL file_size bug, stale 400-vs-401 send-token diagnosis, phone-number matching, and the WAA/reCAPTCHA capture-tokens workflow."
---

# Discord selfbot bridge (bun)

Bridges one Google Voice phone number with one Discord DM by logging in as YOUR OWN Discord user account (a selfbot) via `discord.js-selfbot-youtsuho-v13` (maintained fork of the archived `discord.js-selfbot-v13`). Location: `examples/discord-bridge/` in the google-voice-ws repo. ToS-warning: Discord bans selfbots; account-loss risk is the user's call.

## Direction flow

- **Voice → Discord** (works with just the session cookie): `GoogleVoiceClient` event loop (`messageCreate`) → forward to `BRIDGE_DM_USER_ID`'s DM; first attachment downloaded via `voice.downloadAttachment(id)` and sent as a file.
- **Discord → Voice** (needs WAA/reCAPTCHA send tokens): `messageCreate` in the DM from the bridged user → `voice.sendMessage(threadId, text, tmpId, { tokens, attachment? })`; first Discord attachment fetched and sent as MMS. Skip own messages (`author.id === client.user.id`) to avoid echo loops.

## Stale-token diagnosis (400 vs 401) — CRITICAL

`api2thread/sendsms` error semantics:
- **401 Unauthorized** = missing botguardField entirely (no tokens configured), or expired session cookie.
- **400 Bad Request** with `voice_error: {"error_code":"INVALID_ARGUMENT"}` = tokens present but **STALE**. WAA/BotGuard + reCAPTCHA tokens are session-recent, expire in minutes-to-hours (same window as SIDCC). The session cookie may still be valid (inbound forwarding keeps working) while outbound 400s. The bridge's catch block prints a pointed "run bun run capture-tokens" hint on 400/INVALID_ARGUMENT.

Refresh: `bun run capture-tokens` (bin/capture-send-tokens.ts) opens a real Chromium window (persistent profile), hooks network, and the user sends a real text; the helper intercepts the sendsms request's body index 10 (`[attestation, null, null, recaptcha]`) and writes GV_SEND_ATTESTATION_TOKEN / GV_SEND_RECAPTCHA_TOKEN into the bridge .env. Tokens must be re-captured periodically.

## youtsuho-v13 getUploadURL file_size bug (patched in bridge)

Fork's `Util.getUploadURL` computes Discord `file_size: file.byteLength ?? file.size ?? 0` from the MessagePayload wrapper — but the wrapper's actual bytes are at `wrapper.file`, so it always sends `file_size: 0` → Discord rejects with `files[0].file_size: int value should be greater than or equal to 1`. Fix in index.ts: rebind `Util.getUploadURL` via CJS `require` (ESM `import * as` namespace is frozen) to stamp `byteLength` from inner `.file` before delegating. Use `createRequire(import.meta.url)` to require `discord.js-selfbot-youtsuho-v13/src/util/Util`. No ambient decl needed (cast the require result); text-only sends unaffected (getUploadURL returns early on empty files).

## Phone-number matching

Google Voice returns E.164 (`+14697590653`); BRIDGE_PHONE env may be national (`4697590653`) or formatted. Bridge uses `toE164` (strip non-digits, re-add +) and `numbersMatch` (digits-only, suffix-tolerant: one number a suffix of the other) — never strict !==. threadId derived from normalized digits to avoid double-+ (`t.+<digits>`).

## Debugging

`DEBUG=1` env enables per-event debug logging: every Voice messageCreate (direction, otherParty vs wantParty, text preview, attachment presence) and Discord messageCreate (author, self, channelType, content), each filter rejection with reason, forward/send attempts.

## Env

GV_COOKIE/GV_API_KEY/GV_SAPISID/GV_AUTH_USER (session), DISCORD_TOKEN (user token), BRIDGE_DM_USER_ID, BRIDGE_PHONE, GV_SEND_ATTESTATION_TOKEN/GV_SEND_RECAPTCHA_TOKEN (optional, stale-prone), DEBUG.

## Not yet automated

Token capture is manual (requires a real send in a browser window); an automated headless periodic refresh (cron/systemd) was offered but not built.
