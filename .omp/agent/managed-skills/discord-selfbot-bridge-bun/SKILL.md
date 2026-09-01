---
name: discord-selfbot-bridge-bun
description: "Use when working on the google-voice-ws Discord selfbot bridge (examples/discord-bridge): the youtsuho-v13 library choice and string event names, the self-loop guard, ToS/ban risk, WAA/reCAPTCHA capture, lenient E.164 phone matching, and both-direction attachment forwarding."
---

# Discord selfbot bridge (examples/discord-bridge)

Bridges one Google Voice phone number with one Discord DM using a **selfbot** (user-token login, ToS risk — Discord bans selfbots; keep on a throwaway account). Runs under Bun.

## Library & API

- **Library**: `discord.js-selfbot-youtsuho-v13` (v3.7.7) — the maintained fork of the archived `discord.js-selfbot-v13`. Node 20.18+ required. Stock discord.js v14 refuses user tokens.
- **No `Events` enum**: use string event names — `client.on("ready")`, `client.on("messageCreate")`. `client.user` is the selfbot's own user.
- **Install gotcha**: `bun add` may hang/stall resolving the big discord.js transitive tree; the lockfile can silently omit the dep even when node_modules has it. Fix: delete bun.lock and reinstall, or pin the exact version.
- **Local lib link**: bridge depends on `google-voice-client` via `link:google-voice-client` (register with `bun link` in the repo root first). `file:../..` copies but omits the gitignored `dist/`, so `link:` is required for the built package. Rebuild the parent (`bun run build`) after library changes.

## Self-loop guard (critical)

The selfbot's OWN messages fire `messageCreate` (including its own voice-forwards). MUST ignore `message.author.id === discord.user?.id` before any forwarding, or the bridge echoes every forward back to the phone forever.

## Phone matching (E.164 trap — cost a debug cycle)

Google Voice returns numbers in E.164 (`+14697590653`, with country code), while `BRIDGE_PHONE` in .env may be national form (`4697590653`, no `+`, no `1`). A strict `!==` comparison silently drops EVERY message — symptom: "sent through Voice but not relayed to Discord."

Fix (in bridge): normalize to digits and match on suffix:
- `toE164(raw)` = `"+" + raw.replace(/\D/g, "")`
- `numbersMatch(have, want)` = compare digits-only, match if `a === b || a.endsWith(b) || b.endsWith(a)`
- `threadId = "t.+" + digits` (strip the `+` from the normalized number first, else `t.++...`)

Debug with `DEBUG=1` in the bridge .env — logs every event with `otherParty` vs `wantParty`, direction, attachment presence, and each filter rejection reason.

## Outbound sends: WAA/reCAPTCHA tokens

Discord→phone sends need the anti-abuse tokens Google mints (WAA/BotGuard attestation + reCAPTCHA), session-recent and short-lived; the SDK cannot fabricate them. Capture a fresh pair with `bun run capture-tokens` (opens a real Chromium window; send ANY text to any number; the helper intercepts the `sendsms` request and writes `GV_SEND_ATTESTATION_TOKEN`/`GV_SEND_RECAPTCHA_TOKEN` to .env). Without them, inbound still works but outbound is skipped.

## Attachments (both directions now)

- **Voice → Discord**: `voice.on("messageCreate")` → `voice.downloadAttachment(id)` → `dm.send({ files: [{ attachment: Buffer.from(data), name }] })`.
- **Discord → Voice**: first `message.attachments` item (Collection) → `fetchDiscordAttachment(url, contentType)` (plain fetch of the CDN url) → pass as `sendMessage(threadId, text, tmpId, { attachment: { data, mimeType }, tokens })`. Attachment-only DMs (no text) must NOT be skipped when a photo is present.

## Env (bridge .env)

`GV_*` session vars (from repo root .env), `DISCORD_TOKEN` (user token), `BRIDGE_DM_USER_ID`, `BRIDGE_PHONE` (lenient format ok now), `GV_SEND_ATTESTATION_TOKEN`/`GV_SEND_RECAPTCHA_TOKEN` (optional), `DEBUG=1` (verbose event/filter logging).
