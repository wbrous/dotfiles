---
name: discord-selfbot-bridge-bun
description: "Use when working on the Discord selfbot bridge in google-voice-client (examples/discord-bridge/) or building any Discord user-account (selfbot) integration in Bun/TypeScript — covers the working library choice, the event-name and self-loop gotchas, the bun link dependency trap, and the ToS/account-ban risk."
---

# Discord selfbot bridge (Bun/TS)

Covers `examples/discord-bridge/` in google-voice-client: bridges one Google
Voice phone number with one Discord DM by logging in as YOUR OWN user account.

## ⚠️ Risk — read first

Selfbots (user-token automation) violate Discord ToS. Discord **deactivates
accounts** detected doing this — not a warning, not a gray area. The library's
own README banner says the same. If the user wants a selfbot, implement it but
flag this risk in code comments + README + commit message, and recommend a
throwaway account. The bridge targets only the account owner's own DM, so it
harms no third party, but account loss is the realistic outcome.

## Library choice

- Stock `discord.js` v14 **refuses user tokens** — it validates and the
  gateway rejects them. Do not try to force it.
- Use `discord.js-selfbot-youtsuho-v13` (npm, v3.7.7) — the actively
  maintained fork of `discord.js-selfbot-v13` (archived Oct 2025). Same
  discord.js v13-style API (`new Client()`, `client.login(token)`).
- CommonJS main (`./src/index.js`) — works under Bun.

## Gotchas that actually bit

1. **No `Events` enum.** The fork is v13-based; `Events` is NOT exported.
   Use string literals: `client.once("ready", ...)`, `client.on("messageCreate", ...)`.
   Importing `{ Events }` fails typecheck with TS2305.
2. **Self-echo loop.** The selfbot's own messages fire `messageCreate` — when
   it forwards a Voice message into the DM, that fires too. MUST filter:
   `if (message.author.id === discord.user?.id) return;` before any bridge
   logic, else every forward echoes back to the phone in a loop.
3. **`file:` deps and gitignored dist.** In this repo the bridge used
   `"google-voice-client": "file:../.."`, but Bun's `file:` protocol copies
   the package WITHOUT gitignored `dist/`, so the linked package had no
   `dist/` → `Cannot find module` type errors and runtime import failures.
   Fix: `bun link` in the parent repo root, then use
   `"google-voice-client": "link:google-voice-client"` in the bridge — the
   symlink keeps `dist/` visible and rebuilds propagate.
4. **Slow/corrupted bun installs.** `bun add` on a package with a large
   transitive tree (discord.js family) can hang at "Resolved, downloaded and
   extracted [0]" and leave the package out of the lockfile even when
   `node_modules` looks complete. Fix: delete `bun.lock`, rerun `bun install`
   (regenerates the lock cleanly and fast), verify with
   `grep -c "<pkg>" bun.lock`.

## Bridge wiring (index.ts)

- Config from env, validated BEFORE any network connect (fail fast):
  `DISCORD_TOKEN` (user token), `BRIDGE_DM_USER_ID`, `BRIDGE_PHONE` (E.164),
  `GV_SEND_ATTESTATION_TOKEN`/`GV_SEND_RECAPTCHA_TOKEN` (optional).
- Voice → Discord: `voice.on("messageCreate")`, filter `direction ===
  "RECEIVED"` && `otherPartyNumber === BRIDGE_PHONE`, then `users.fetch(dmUserId)`
  → `createDM()` → `dm.send(...)` (attachments via `downloadAttachment` +
  `files: [{ attachment: Buffer.from(data), name }]`).
- Discord → Voice: `discord.on("messageCreate")`, filter self + bridged user,
  then `voice.sendMessage(threadId, text, tmpId, { tokens })`. Thread id is
  `t.+${phone}`. Strip a leading `<@mention>` quote from replies.
- Outbound sends 401 without the WAA/reCAPTCHA tokens (SDK can't mint them);
  without them, log that outbound is disabled and keep forwarding inbound.
- Run: `bun --env-file=.env run index.ts`; `SIGINT` stops the voice loop +
  `discord.destroy()`.

## Verification without a live account

- `bun x tsc --noEmit` in the bridge dir (needs its own tsconfig + @types/bun).
- A no-env run must fail fast: `bun run index.ts` → throws
  `Missing required environment variable "GV_COOKIE"` before any connection —
  proves import graph + config validation. Do NOT test against a real user
  token.
