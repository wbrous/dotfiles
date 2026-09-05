---
name: google-voice-tapback-to-discord-reaction
description: "Use when working on the google-voice-ws Discord bridge (examples/discord-bridge/) and forwarding Google Voice's iMessage-style tapback notification texts (Liked/Loved/Disliked \"…\" or Reacted emoji to \"…\") — map them to a Discord message reaction on the originally-forwarded message instead of posting them as new DM text. Also covers caching BOTH directions of forwarded messages, formatting Discord replies as SMS block-quotes when forwarding Discord→Voice, phone-typed .reply/.edit commands that control the Discord side of the bridge (with a \"no quotes = target latest message\" fallback), and the Dockerfile layer-ordering fix keeping bunx playwright install cached across source edits."
---

## Bidirectional forwarded-message cache

`recentForwarded: Array<{ text: string; message: Message }>` (bounded, `MAX_RECENT_FORWARDED = 50`) in `examples/discord-bridge/index.ts` caches messages from **both** directions:
- Voice → Discord: `rememberForwarded(body, sentDmMessage)` after `dm.send(body)`.
- Discord → Voice: `rememberForwarded(text, message)` after a successful `voice.sendMessage(...)` — `text` here is the *full* sent content (including any reply-quote prefix, see below), because that's what a later Voice tapback will quote back.

`findForwardedMessage(text)` searches newest-first by exact trimmed text match. `latestForwarded()` returns the single most recent entry across both directions — used as the fallback target when a phone command omits its quoted argument.

`updateRememberedText(message, newText)` mutates a cache entry's `.text` in place by `message.id` — needed after `.edit` changes a message's displayed content, so a *later* command/reaction targets the new text, not the stale one.

## Tapback → Discord reaction mapping

Google Voice sends tapback acknowledgements as plain SMS/MMS text in this exact shape:
```
Liked "quoted text"
Loved "quoted text"
Disliked "quoted text"
Reacted 😂 to "quoted text"
```
The quoted portion may be multi-line (real newlines inside the quotes, not escaped `\n`). `parseReactionMessage(text)` matches this and returns `{ emoji, quoted }`; `REACTION_LABEL_EMOJI` maps `Liked`→👍, `Loved`→❤️ (or similar), `Disliked`→👎, and `Reacted <emoji> to "..."` uses the literal emoji already in the text.

In `voice.on("messageCreate")`, before falling through to normal-message forwarding: if there's no attachment, try `parseReactionMessage(body)` → `findForwardedMessage(reaction.quoted)` → `target.react(reaction.emoji)`. No match → falls through to sending as plain text (visible to the user as a literal `Liked "..."` DM, which is the correct degraded behavior, not a bug).

## Discord reply → SMS block-quote (Discord→Voice direction)

`buildReplyQuote(message)`: if `message.reference?.messageId` is set, fetches the referenced message via `message.channel.messages.fetch(...)` and returns its content with every line prefixed `> ` (SMS/iMessage quoting convention). Prepended to the outbound text as `` `${quote}\n\n${rawText}` ``. A reply with no additional text still sends (quote-only), since `!rawText && !discordAttachment && !replyQuote` is the actual skip condition — not `!rawText` alone.

## Phone-typed `.reply`/`.edit` commands (Voice→Discord direction)

Typing into the Messages app on the phone can control the Discord side:
```
.reply "quoted target text"
the reply body (rest of the message, can be multi-line)
```
```
.edit "quoted target text"
the new content
```
Quotes are **optional** — omitting them (`.reply\nbody text`) targets `latestForwarded()` instead of searching. `parseVoiceCommand(text)`: command must occupy the *entire first line* (`/^\.(reply|edit)(?:\s+"([^"]*)")?\s*$/i`); everything after the first `\n`, trimmed, is the payload — a command with no following payload line returns `null` (falls through to normal reaction/forward handling, so a stray literal `.reply` typo just gets sent as plain text).

- `.reply` → `target.reply(command.body)`, then `rememberForwarded(command.body, sentMessage)` so later commands/reactions can reference the new reply.
- `.edit` → `target.edit(command.body)`, then `updateRememberedText(target, command.body)`. Only succeeds if the bridge's own selfbot sent `target` (Discord only allows editing your own messages) — editing a message the *other* Discord user sent throws, caught by the existing try/catch and logged, not a special case to add.
- Target-not-found (bad/stale quoted text) falls through to sending the raw command text as a normal message, mirroring the reaction-fallback pattern already used for `Liked "..."`.

Command detection runs **before** `parseReactionMessage` in the `!attachment` branch, since both operate on `body` and are mutually exclusive by format.

## Dockerfile playwright cache-busting (examples/discord-bridge/Dockerfile)

`RUN bunx playwright install --with-deps chromium` (a ~4 minute layer) must sit **immediately after** `RUN bun install` for the bridge package and **before** `COPY examples/discord-bridge/tsconfig.json/index.ts/bin`. If it's placed after the source `COPY`s, every source edit invalidates the Docker layer cache for everything below it — including the expensive Chromium download — even though the install only actually depends on `package.json`/lockfile, not source files. Verify a fix by touching `index.ts` and rebuilding: the `bunx playwright install` step should show `CACHED`.
