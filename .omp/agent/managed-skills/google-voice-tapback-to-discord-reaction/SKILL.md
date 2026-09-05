---
name: google-voice-tapback-to-discord-reaction
description: "Use when working on the google-voice-ws Discord bridge (examples/discord-bridge/) and forwarding Google Voice's iMessage-style tapback notification texts (Liked/Loved/Disliked \"…\" or Reacted emoji to \"…\") — map them to a Discord message reaction on the originally-forwarded message instead of posting them as new DM text. Also covers caching BOTH directions of forwarded messages, formatting Discord replies as SMS block-quotes when forwarding Discord→Voice, phone-typed .reply/.edit commands that control the Discord side of the bridge (with a \"no quotes = latest, direction-aware\" fallback), the Dockerfile layer-ordering fix keeping bunx playwright install cached across source edits, the library-level (src/client.ts) fix for batched-poll-tick message ordering, and the poll-loop initial-empty-snapshot test-fixture gotcha."
---

## Tapback → Discord reaction mapping

In `examples/discord-bridge/index.ts`, Google Voice's iMessage-style tapback texts (`Liked "…"`, `Loved "…"`, `Disliked "…"`, `Reacted <emoji> to "…"`) are parsed and mapped to a Discord `message.react(emoji)` on the *originally forwarded* message instead of being posted as new DM text. The quoted text (which can be multi-line) is matched against a bounded (`MAX_RECENT_FORWARDED = 50`) history array `recentForwarded: Array<{ text: string; message: Message }>` via `findForwardedMessage(text)` (exact-trim match, searched newest-first). If no match is found, it falls back to sending the tapback text as plain content.

**Critical:** `rememberForwarded(text, message)` must be called on *every* successful forward in *both* directions:
- Voice → Discord (`voice.on("messageCreate")`): after `dm.send(body)`.
- Discord → Voice (`discord.on("messageCreate")`): after `voice.sendMessage(...)`, caching the *original Discord `Message` object* the user sent.

Missing the outbound-direction caching means a tapback on a message *you* sent from Discord (not one forwarded from the phone) silently fails to find a target and falls through to plain-text (which is invisible in your own outbound thread) — this was a real reported bug, root-caused as exactly this omission.

## Discord reply → SMS quote formatting (Discord → Voice)

When the bridged user replies to a Discord message, `buildReplyQuote(message)` fetches `message.channel.messages.fetch(message.reference.messageId)` and formats every line of the referenced message's content as `> line` (iMessage/SMS block-quote style), then prepends it to the reply body with a blank line separator:
```
> original line one
> original line two

reply text here
```
The *full* quoted+body text (not just the raw reply) is what gets sent to the phone via `voice.sendMessage` AND cached via `rememberForwarded`, so a tapback reaction on that message later matches on the exact SMS text delivered (which includes the quote block).

## `.reply` / `.edit` phone commands (Voice → Discord)

Typed into the Messages app, these control the Discord side from the phone:
```
.reply "quoted target text"
the reply body (rest of the message, can be multi-line)
```
```
.edit "quoted target text"
the new content
```
Parsed by `parseVoiceCommand(text)`: splits on the first `\n`, matches the first line against `/^\.(reply|edit)(?:\s+"([^"]*)")?\s*$/i`, treats everything after as the body (`.trim()`'d — a blank line between command and body, e.g. `.reply\n\nHello`, is fine). Returns `null` for anything malformed or missing a body line.

**Quoted-target lookup** uses the same `findForwardedMessage` cache as tapbacks (works across both directions).

**No-quote default target is direction-aware, NOT a single "latest message" pointer** — this was a real bug fix:
- `.reply` with no quotes → `latestFromUser()`: most recent cached message *authored by the bridged Discord user*. Ensures replying always targets what the other person said, even if you (the bridge) sent something more recently.
- `.edit` with no quotes → `latestFromSelf()`: most recent cached message *authored by the bridge's own Discord account* (`discord.user?.id`). Required because Discord only allows editing your own messages — defaulting to the absolute-latest message (regardless of author) would frequently pick a message you can't edit, which is exactly the bug reported ("If the discord user sends a message and I do .edit, it doesn't work").
- `.edit` targeting a message NOT authored by the bridge (whether via explicit quote or the old naive "latest overall" default) will throw at the Discord API level — this is an intentional, uncircumventable Discord platform restriction, not a bug to fix. The existing try/catch just logs it.

`.edit` also updates the cache entry's text via `updateRememberedText(message, newText)` (matches by `message.id`) so subsequent commands/reactions referencing the *new* text can find it.

If a command's target isn't found in the cache, it falls through and sends the raw command text as plain content (same fallback pattern as tapback reactions).

## Dockerfile playwright-install cache ordering

`bunx playwright install --with-deps chromium` (~4 min, downloads Chromium) MUST come immediately after `RUN bun install` (bridge deps) and BEFORE `COPY examples/discord-bridge/tsconfig.json/index.ts/bin`. If placed after those `COPY`s, Docker invalidates the playwright layer (and everything below it) on every source-code edit, since Docker layer caching invalidates a layer and all subsequent layers once any earlier layer's input changes. Symptom: every `docker compose build` after an `index.ts` edit re-downloads Chromium (~4-5 min) even though playwright only actually depends on `package.json`.

## Library-level: batched-poll-tick message ordering (src/client.ts)

The poll loop's `tick()` builds a `Map<string, ThreadEvent>` from `listThreads()` response order and previously emitted `messageCreate` immediately per Map entry. Google's `api2thread/list` doesn't guarantee chronological order within one response, so if two SMS land between polls, they could emit (and thus get forwarded to Discord) in reverse order. Fixed by collecting new-event entries into an array, sorting by `timestampMs` ascending, THEN emitting `messageCreate` in that order. `messageUpdate` still emits inline per-id (no batching issue there since it's not a race between distinct new messages).

**Test-fixture gotcha:** the poll loop's `snapshot.size === 0` check is used both to detect "first tick ever" (emit `ready`, no diffing) AND implicitly relies on the *first* tick actually returning non-empty data. If a test's first stubbed `listThreads()` call returns an empty-events thread (`[makeThread([])]`), `this.snapshot` stays size 0 after that tick, so the *second* tick is ALSO treated as "first snapshot" (emits `ready` again, skips all diffing) instead of diffing against the empty baseline — silently producing zero `messageCreate` events and a hanging test (looks like a 5s timeout, not an assertion failure). Fix: make the first stubbed tick return at least one already-seen event so `snapshot.size > 0` before the tick under test.
