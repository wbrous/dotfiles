---
name: google-voice-tapback-to-discord-reaction
description: "Use when working on the google-voice-ws Discord bridge (examples/discord-bridge/) and forwarding Google Voice's iMessage-style tapback notification texts (Liked/Loved/Disliked \"…\" or Reacted emoji to \"…\") — map them to a Discord message reaction on the originally-forwarded message instead of posting them as new DM text. Also covers caching BOTH directions of forwarded messages, formatting Discord replies as SMS block-quotes when forwarding Discord→Voice, phone-typed .reply/.edit commands that control the Discord side of the bridge (with a \"no quotes = latest, direction-aware\" fallback), forwarding Discord message edits to the phone as \"edit: old\\n\\nnew\" notices, the Dockerfile layer-ordering fix keeping bunx playwright install cached across source edits, the library-level (src/client.ts) fix for batched-poll-tick message ordering, and the poll-loop initial-empty-snapshot test-fixture gotcha."
---

## Message cache (`recentForwarded` in `index.ts`)

Bounded array of `{ text, message }`, appended by `rememberForwarded()` on **every** successful forward, both directions:
- Voice → Discord: after `dm.send(body)`.
- Discord → Voice: after `voice.sendMessage(...)` succeeds (was originally missing — a Voice tapback on a message *you* sent from Discord wouldn't resolve until this was added).

`findForwardedMessage(text)` does an exact-trim match scanning newest-first. `updateRememberedText(message, newText)` mutates a cache entry's `text` in place, keyed by `message.id` — used both when `.edit`-ing a message and when the Discord user edits their own message (keeps the cache in sync with the current displayed content).

## Tapback → reaction mapping

`parseReactionMessage(text)` matches `Liked "…"` / `Loved "…"` / `Disliked "…"` / `Reacted X to "…"` (multi-line quoted content included). On a match, `findForwardedMessage(reaction.quoted)` resolves the target; `target.react(emoji)` applies it. No match or no cached target → falls through and sends the tapback text as a plain message (never silently drops it).

## Discord reply quoting (Discord → Voice)

`buildReplyQuote(message)`: if `message.reference?.messageId` is set, fetches the referenced message and returns its content with every line prefixed `> `. The final SMS text sent to the phone is `` `${quote}\n\n${rawText}` `` when a quote exists. A reply with **no** additional text (e.g. replying to just add an attachment) is still allowed through — the emptiness check is `!rawText && !discordAttachment && !replyQuote`, not `!text`.

## `.reply` / `.edit` phone commands (Voice → Discord)

Typed into the Messages app on the phone, parsed by `parseVoiceCommand(text)`:
```
.reply "quoted target text"
the reply body (rest of the message, after the first newline)
```
`.edit` has the same shape but calls `target.edit(body)` instead of `target.reply(body)`. Regex: `/^\.(reply|edit)(?:\s+"([^"]*)")?\s*$/i` on the first line only; `body` is everything after the first `\n`, trimmed (a blank line between command and body is fine — `.trim()` absorbs it).

**Direction-aware default target when quotes are omitted** — this is the part that's easy to get wrong:
- `.reply` with no quotes → `latestFromUser()`: the most recent `recentForwarded` entry authored by the bridged Discord user (`config.dmUserId`). Reasoning: a bare `.reply` should always target what the *other person* said, even if the bridge itself sent a message more recently (e.g. an earlier `.reply`/forward).
- `.edit` with no quotes → `latestFromSelf()`: the most recent entry authored by the bridge's own account (`discord.user.id`). Reasoning: Discord only allows editing your own messages, so defaulting to the user's message would always fail.
- Do **not** collapse these into one `latestForwarded()` — that was the original (buggy) implementation and picks the wrong author depending on which direction last fired.
- `.edit` targeting a message the Discord user sent will still fail at the Discord API level (can't edit someone else's message) — this is a genuine platform restriction, not a bug to work around; the existing try/catch just logs it.

## Discord message edits → phone

`discord.on("messageUpdate", async (oldMessage, newMessage) => ...)` forwards a Discord-side edit to the phone as:
```
edit: their old message

their new message
```
Same author/self/channel-type filtering as the `messageCreate` handler. Skip if `oldMessage.content === newMessage.content` (an embed unfurling fires `messageUpdate` with unchanged text). After a successful send, call `updateRememberedText(newMessage, newText)` so subsequent `.reply`/`.edit`/reactions targeting that message match the *current* text, not the stale pre-edit text.

## Dockerfile playwright/cache ordering

`RUN bunx playwright install --with-deps chromium` (~4 min) must come **before** `COPY examples/discord-bridge/index.ts` / `COPY examples/discord-bridge/bin`, right after `RUN bun install` for the bridge's deps. It only depends on `package.json`/lockfile, not source — if placed after the source `COPY`s, every source edit busts Docker's cache for the expensive layer too, since Docker invalidates a layer and everything below it once an earlier layer changes.

## Library-level poll ordering fix (`src/client.ts`)

`GoogleVoiceClient`'s poll `tick()` originally emitted `messageCreate` immediately while iterating the `next` Map, which is built in raw `listThreads()` response order — not guaranteed chronological. Two SMS sent back-to-back between polls could be emitted (and thus DM'd to Discord) in the wrong order.

Fix: collect new events into an array, `sort((a, b) => a.timestampMs - b.timestampMs)`, then emit `messageCreate` for each in order. `messageUpdate` still emits inline during the same scan (order doesn't matter there since it's per-id, not a race between distinct new messages).

**Test-fixture gotcha**: the poll loop's "first snapshot" branch checks `this.snapshot.size === 0` (the *old* snapshot, before this tick's data is applied) to decide whether to emit `ready` instead of diffing. If your first stubbed `listThreads()` tick returns a thread with an **empty** events array, `next` stays size 0, so `this.snapshot` stays empty after that tick too — and the *next* tick will ALSO take the "first snapshot" branch (re-emitting `ready`, never diffing/emitting `messageCreate`), because `this.snapshot.size === 0` is still true. Regression tests for batched-message-ordering must seed tick 1 with a **non-empty** thread (e.g. one already-seen event) so tick 2 actually reaches the diff/sort path.

## Docker rebuild reminder

The Discord bridge example depends on the library via `bun link` inside the Docker image; when running example against local dev host (not Docker), always `bun run build` in the repo root after any `src/*.ts` change before testing the bridge, since it consumes `dist/`.
