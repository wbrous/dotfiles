---
name: discord-selfbot-bridge-bun
description: "Use when working on the google-voice-ws Discord selfbot bridge example (examples/discord-bridge): the youtsuho-v13 library choice and string event names, the self-loop guard, ToS/ban risk, live-capture of WAA/reCAPTCHA send tokens via capture-tokens, and the bun link/env gotchas."
---

# Discord selfbot bridge (Bun)

Project: `/home/wils/Documents/Development/google-voice-ws/examples/discord-bridge` — bridges one Google Voice phone number with one Discord DM by logging into Discord as a **user account** (selfbot). Two directions: phone→Discord (via the GV client's event loop) and Discord→phone (via `sendMessage`).

## Library choice (critical)

Stock `discord.js` v14 **refuses user tokens**. Use the active fork of the archived selfbot lib:

- `discord.js-selfbot-youtsuho-v13@3.7.7` — maintained continuation of the archived `discord.js-selfbot-v13` (discord.js v13 base, API v9). CJS main (`./src/index.js`) but works under Bun.
- **No `Events` enum export** — use string event names: `client.on("ready", ...)`, `client.on("messageCreate", ...)`.
- `client.user` is a `ClientUser`; `client.login(token)` takes the user token.
- Prints its own banner on import — harmless.

## Self-loop guard (critical)

The selfbot's OWN messages (including its voice-forwards) fire `messageCreate`. Always filter `if (message.author.id === discord.user?.id) return;` before forwarding, else every forward echoes back to the phone forever.

## ToS / ban risk (must flag honestly)

Selfbots violate Discord ToS; Discord deactivates accounts detected doing this. Not a gray area. README + code flag it; run on a throwaway account if at all possible.

## Outbound sends need live-captured anti-abuse tokens

`sendMessage` 401s without WAA/BotGuard + reCAPTCHA tokens that Google mints by running obfuscated JS in a real page. The GV SDK cannot fabricate them; they're short-lived. Mechanism in this repo:

```bash
bun run capture-tokens   # bin/capture-send-tokens.ts in the bridge dir
```

- Launches persistent Chromium profile at voice.google.com/messages, hooks the network layer, and extracts `body[10]` (the `[attestationToken, null, null, recaptchaToken]` array) from the next `api2thread/sendsms` request.
- **Requires a real send**: you must actually send a text in the browser window for the tokens to be minted/intercepted.
- Writes `GV_SEND_ATTESTATION_TOKEN` / `GV_SEND_RECAPTCHA_TOKEN` into the bridge `.env`.
- Fails fast if `DISCORD_TOKEN` isn't set.

## Env + linking gotchas

- `start` runs `bun --env-file=.env run index.ts`; `capture-tokens` uses its own `.env` too.
- `google-voice-client` is a local dep via `link:google-voice-client` — register once with `bun link` at the repo root before `bun install` in the bridge.
- Bridge `.env` is gitignored by the root `.env` pattern; it carries `DISCORD_TOKEN`, `BRIDGE_DM_USER_ID`, `BRIDGE_PHONE` (E.164), GV session vars, and the `GV_SEND_*` tokens.
- Discord user id: Developer Mode → copy user id.
