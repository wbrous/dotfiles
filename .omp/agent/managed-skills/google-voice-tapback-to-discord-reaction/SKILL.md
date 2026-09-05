---
name: google-voice-tapback-to-discord-reaction
description: "Use when working on the google-voice-ws Discord bridge (examples/discord-bridge/) and forwarding Google Voice's iMessage-style tapback notification texts (Liked/Loved/Disliked \"…\" or Reacted emoji to \"…\") — map them to a Discord message reaction on the originally-forwarded message instead of posting them as new DM text. Covers caching BOTH directions of forwarded messages, not just Voice→Discord. Also covers formatting Discord replies as SMS block-quotes when forwarding Discord→Voice, and the Dockerfile layer-ordering fix keeping bunx playwright install cached across source edits."
---

## Tapback → Discord reaction (Voice → Discord)

Google Voice sends iMessage-style tapback notifications as plain SMS text:
`Liked "..."`, `Loved "..."`, `Disliked "..."`, `Reacted <emoji> to "..."`.
The quoted content can be multi-line (curly/straight quotes both occur).

- `parseReactionMessage(text)` in `examples/discord-bridge/index.ts` regexes
  these four shapes out and returns `{ emoji, quoted }`.
- `REACTION_LABEL_EMOJI` maps `Liked`→👍, `Loved`→💖, `Disliked`→👎; a literal
  `Reacted <emoji> to "..."` just reuses the emoji verbatim.
- `rememberForwarded(text, message)` keeps a bounded (50-entry) history of
  `{ text, message }` for exact-match lookup by `findForwardedMessage`.
- **Critical:** cache BOTH directions — Voice→Discord forwards AND
  Discord→Voice sends (`discord.on("messageCreate")` after a successful
  `voice.sendMessage`, using the same fully-composed `text` that was sent,
  not just the raw Discord `message.content`). Missing the outbound cache
  means reacting to a message *you* sent from Discord silently falls back to
  plain text with no visible effect (looks like a no-op bug, not a crash).
- When attachment-only reaction lookups fail, code falls back to sending the
  reaction text as a plain message rather than crashing — intentional, not a
  bug to "fix" defensively.

## Reply quoting (Discord → Voice)

When the bridged Discord user replies to a message, `buildReplyQuote(message)`
fetches `message.reference.messageId` via `message.channel.messages.fetch`,
then formats every line of the referenced message's content as an SMS-style
block quote (`> line`), joined with `\n`, and prepends it to the reply text
with a blank line separator:

```
> quoted line one
> quoted line two

actual reply text
```

The full quoted+reply string (not just the raw reply) is what's sent via
`voice.sendMessage` AND cached in `rememberForwarded`, so a later tapback on
that composite message still resolves correctly. An empty reply (e.g.
replying with only an attachment) still sends the quote block alone rather
than being treated as an empty/skippable message.

## Dockerfile layer-cache ordering

`examples/discord-bridge/Dockerfile` builds the parent library then installs
the bridge. `RUN bunx playwright install --with-deps chromium` (~4 min) MUST
be placed immediately after `RUN bun install` (bridge deps) and BEFORE
`COPY examples/discord-bridge/{tsconfig.json,index.ts,bin}` — Docker
invalidates a layer and everything below it once an earlier layer changes,
so if the Chromium install layer sits after the source COPYs, every source
edit forces a full Chromium re-download even though that install only
depends on `package.json`. Symptom: `docker compose build` staying slow
(~5 min) on every rebuild despite `CACHED` showing for unrelated steps.
