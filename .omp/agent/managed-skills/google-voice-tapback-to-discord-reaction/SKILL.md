---
name: google-voice-tapback-to-discord-reaction
description: "Use when working on the google-voice-ws Discord bridge (examples/discord-bridge/) and forwarding Google Voice's iMessage-style tapback notification texts (Liked/Loved/Disliked \"…\" or Reacted emoji to \"…\") — map them to a Discord message reaction on the originally-forwarded message instead of posting them as new DM text. Also covers caching BOTH directions of forwarded messages, formatting Discord replies as SMS block-quotes when forwarding Discord→Voice, phone-typed .reply/.edit commands that control the Discord side of the bridge (with a \"no quotes = target latest message\" fallback), the Dockerfile layer-ordering fix keeping bunx playwright install cached across source edits, and the library-level (src/client.ts) fix for batched-poll-tick message ordering."
---

## Tapback reaction mapping (Voice → Discord)

Google Voice sends iMessage-style tapback notifications as plain SMS text:
`Liked "..."`, `Loved "..."`, `Disliked "..."`, `Reacted <emoji> to "..."`.
The quoted part is the *exact* original message text (multi-line messages
keep their literal newlines inside the quotes, no escaping).

- `REACTION_LABEL_EMOJI` maps `Liked`→👍, `Loved`→❤️, `Disliked`→👎.
- `parseReactionMessage(text)` regex-matches all four forms (curly and
  straight quotes) and returns `{ emoji, quoted }` or `null` for a normal
  message.
- `recentForwarded: Array<{ text: string; message: Message }>` is a
  bounded (50-entry) history keyed by exact forwarded text, checked most-
  recent-first by `findForwardedMessage(text)`.
- **Cache BOTH directions.** Voice→Discord forwards (`dm.send`) and
  Discord→Voice sends (`voice.sendMessage`) must both call
  `rememberForwarded(text, message)` after success — a tapback can target
  either an inbound or outbound message. Missing the outbound side means
  reacting to your own sent SMS silently no-ops (falls through to sending
  the tapback text as a new message, easy to miss since it looks like a
  DM you'd expect to just not react).
- In the `messageCreate` handler (Voice→Discord): before forwarding a
  text-only Voice message normally, check `parseReactionMessage`; on a
  match, look up the target and call `target.react(reaction.emoji)`. Any
  attachment present skips reaction parsing entirely (MMS never carries
  tapback text). No match found among cached messages → fall back to
  forwarding as plain text (matches call for `.reply`/`.edit` below).

## Reply quoting (Discord → Voice)

When the bridged user replies to a Discord message, prefix the SMS body
with an SMS/iMessage-style block quote:

```
> original line one
> original line two

actual reply text
```

`buildReplyQuote(message)` fetches `message.reference.messageId` via
`message.channel.messages.fetch`, splits the referenced content on `\n`,
prefixes each line with `> `, joins back. Returns `undefined` for a
non-reply or an unfetchable reference (deleted message — caught and
logged via `debug`, not thrown). The **full quoted text** (quote block +
blank line + reply) is what actually gets sent to the phone and cached in
`rememberForwarded` — not just the raw reply — so a later tapback quoting
the phone's SMS content matches correctly.

## Phone-side `.reply` / `.edit` commands (Voice → Discord)

Typed into the Messages app to control the Discord side without touching
Discord directly:

```
.reply "quoted target text"
the reply body (rest of the message, can be multi-line)
```
```
.edit "quoted target text"
the new content
```

- `parseVoiceCommand(text)`: command must occupy the *entire first line*
  (`text.indexOf("\n")`); everything after the first newline is the
  payload, trimmed. Regex: `/^\.(reply|edit)(?:\s+"([^"]*)")?\s*$/i`.
  Returns `null` if the line doesn't match, or if there's no payload
  (single-line message, e.g. just `.reply "x"` — command is silently
  ignored, NOT sent to Discord as literal text with no body).
- **Quotes optional** — omitting them (`.reply\nbody`) targets
  `latestForwarded()`, the most recently cached message in the
  `recentForwarded` array (either direction). Don't add a separate
  "latest" keyword; just treat a missing quoted group as "use latest."
- `.reply`: `target.reply(body)`, then `rememberForwarded(body, sent)` so
  the new Discord message is itself reactable/replyable from the phone.
- `.edit`: `target.edit(body)`, then update the cache entry's cached text
  in place (`updateRememberedText(message, newText)` — find by
  `message.id`, mutate `.text`) so a stale old-text lookup can't match it
  anymore. `.edit` only succeeds if the bridge itself sent that Discord
  message (Discord API restriction) — editing the other person's message
  throws and is caught by the handler's existing try/catch, logged as a
  normal `[voice→discord] failed:` error, no special-casing needed.
- Target not found in cache (either command) → falls through to sending
  the raw command text as a plain Discord message, same fallback pattern
  as the tapback-reaction miss case. Put the command check *before* the
  reaction check in the `messageCreate` handler, both gated behind
  `if (!attachment)`.

## Message-ordering bug (poll batching) — library-level, src/client.ts

**Symptom:** sending two SMS from the phone before Voice's next poll tick
causes them to appear in Discord in *reverse* order.

**Root cause:** `GoogleVoiceClient`'s poll `tick()` built a `Map<id, event>`
from `listThreads()` in raw server-response order and emitted
`messageCreate` synchronously per Map entry during iteration. Google's
`api2thread/list` does NOT guarantee chronological order across multiple
new events landing in the same poll window.

**Fix:** collect all new (no prior snapshot entry) events into an array
first, `.sort((a, b) => a.timestampMs - b.timestampMs)`, THEN emit
`messageCreate` for each in that order. `messageUpdate` can stay emitted
inline during the same loop pass — it's per-id, not a race between
distinct new messages, so order doesn't matter there.

**Regression test gotcha:** a poll-loop test's first tick must return a
**non-empty** thread. If the first `listThreads()` stub returns
`[makeThread([])]`, `next` is size 0, so `this.snapshot.size === 0` stays
true on the *next* tick too (nothing was ever recorded), re-triggering the
"first snapshot" branch (`ready` again) instead of diffing — the intended
`messageCreate` assertions never fire and the test hangs until timeout.
Always seed tick 1 with at least one already-known event, then add new
ones (out of chronological order, to prove the sort) on tick 2.

Also: after any `src/client.ts` change, run `bun run build` before
testing `examples/discord-bridge/` — it depends on the library via
`bun link`, so `dist/` must be rebuilt (per repo AGENTS.md).

## Docker layer-ordering (Dockerfile)

`RUN bunx playwright install --with-deps chromium` (~4 min) must come
**right after** `RUN bun install` for the bridge, **before** the source
`COPY`s (`tsconfig.json`, `index.ts`, `bin`). Docker invalidates a layer
and everything below it once an earlier layer changes; if the Playwright
install sits after the source `COPY`s, every ordinary code edit re-runs
the entire Chromium download. Ordering must be: deps → heavy/network
installs → source copies, not deps → source copies → heavy installs.

## Misc

- `discord.js-selfbot-youtsuho-v13`'s `Message` class supports both
  `.reply(content)` and `.edit(content)` (confirmed via grep on
  `node_modules/.../structures/Message.js`) — no need to fall back to
  `channel.send({ reply: { messageReference } })` manually.
- `Message` type must be imported as `type Message` from the same
  package the `Client` comes from, for the cache array's element type.
