---
name: google-voice-tapback-to-discord-reaction
description: "Use when working on the google-voice-ws Discord bridge (examples/discord-bridge/) and forwarding Google Voice's iMessage-style tapback notification texts (Liked/Loved/Disliked \"…\" or Reacted emoji to \"…\") — map them to a Discord message reaction on the originally-forwarded message instead of posting them as new DM text. Covers caching BOTH directions of forwarded messages, not just Voice→Discord."
---

## What this is

Google Voice (relaying iMessage tapbacks over SMS) sends plain-text notification messages instead of real reaction events:

- `Liked "…"` / `Loved "…"` / `Disliked "…"`
- `Reacted <emoji> to "…"`

The quoted part can span multiple lines. In `examples/discord-bridge/index.ts` these should be turned into a real Discord reaction on the message being referenced, not posted as their own DM text.

## Implementation

- `parseReactionMessage(text)` — regex-matches the four forms above (quote char class `[""]`/`[""]`, `[\s\S]*` for multi-line body) and returns `{ emoji, quoted }`. Label→emoji map: `Liked → 👍`, `Loved → 💖`, `Disliked → 👎`; `Reacted <emoji> to "…"` uses the captured emoji literally.
- `recentForwarded`: a bounded (50-entry) array of `{ text, message: Message }`, with `rememberForwarded`/`findForwardedMessage` (exact-trim match, most-recent-first) doing the lookup.
- In the `voice.on("messageCreate")` handler (Voice → Discord), when the incoming text has no attachment, try `parseReactionMessage` first; on a hit, look up `findForwardedMessage(reaction.quoted)` and call `target.react(emoji)` instead of `dm.send`. Fall back to a normal send if no match is found.

## Critical bug already hit here: cache BOTH directions

The tapback target message is not always something *received* from the phone — it's just as often a message *you sent* from Discord to the phone (Discord → Voice), which the phone user then tapped-back on via iMessage. If `rememberForwarded` is only called in the Voice→Discord handler, reactions to your own outbound messages silently no-op (falls through to the "not found" branch, which for a `Loved "…"` message on your own thread produces no visible effect since it's not re-sent as new text either way — easy to miss in testing).

Fix: also call `rememberForwarded(text, message)` in the `discord.on("messageCreate")` (Discord → Voice) handler, right after a successful `voice.sendMessage(...)`, caching the original Discord `Message` object (only when `text` is non-empty). Both directions must feed the same cache for tapback matching to work symmetrically.

## Verification

- `bunx tsc --noEmit -p examples/discord-bridge` after any change (project has no separate build target here worth invoking through `bun build`, which pulls in unrelated broken deps like `chromium-bidi`/`ffmpeg-static` from transitive playwright/prism-media packages — those failures are pre-existing and unrelated to this feature).
- Standalone eval of `parseReactionMessage` against the five example message shapes (all three label forms, the emoji-react form, and a multi-line liked message) plus one non-matching plain message, to confirm regex correctness without needing a live Discord/Voice session.
