---
name: google-voice-tapback-to-discord-reaction
description: "Use when working on the google-voice-ws Discord bridge (examples/discord-bridge/) and forwarding Google Voice's iMessage-style tapback notification texts (Liked/Loved/Disliked \"…\" or Reacted emoji to \"…\") — map them to a Discord message reaction on the originally-forwarded message instead of posting them as new DM text. Also covers caching BOTH directions of forwarded messages, formatting Discord replies as SMS block-quotes when forwarding Discord→Voice, phone-typed .reply/.edit/.delete commands that control the Discord side of the bridge (with a \"no quotes = latest, direction-aware\" fallback), forwarding Discord message edits to the phone as \"edit: old\\n\\nnew\" notices, the Dockerfile layer-ordering fix keeping bunx playwright install cached across source edits, the library-level (src/client.ts) fix for batched-poll-tick message ordering, and the poll-loop initial-empty-snapshot test-fixture gotcha."
---

## Tapback → Discord reaction mapping

Google Voice's Messages app renders iMessage-style tapback notifications as
plain SMS text: `Liked "..."`, `Loved "..."`, `Disliked "..."`, `Reacted 😀 to
"..."`. The bridge's `voice.on("messageCreate")` handler parses these with
`parseReactionMessage(text)` and, on a match, looks up the quoted text in a
bounded `recentForwarded` cache (`findForwardedMessage`) and calls
`target.react(emoji)` instead of posting the tapback as a new Discord
message. Multi-line quoted content works — the regex captures across
newlines up to the closing `"`.

`REACTION_LABEL_EMOJI` maps `Liked`→👍, `Loved`→❤️, `Disliked`→👎. A literal
`Reacted <emoji> to "..."` uses the emoji verbatim from the SMS.

## recentForwarded cache — must record BOTH directions

`rememberForwarded(text, message)` must be called after *every* successful
send in *both* directions:
- Voice→Discord (`dm.send(body)` inside `voice.on("messageCreate")`)
- Discord→Voice (`voice.sendMessage(...)` inside `discord.on("messageCreate")`)

Caching only one direction means a tapback/`.reply`/`.edit`/`.delete` on a
message from the uncached direction silently no-ops (falls through to
sending plain text, or fails). This was a real shipped bug — reacting to a
message the *phone owner* sent (not received) failed until both directions
were cached.

Helper lookups over `recentForwarded`:
- `findForwardedMessage(text)` — exact-match on cached text, either author.
- `latestFromUser()` — most recent entry authored by the bridged Discord
  user (config.dmUserId). Default target for `.reply` — you want to reply
  to *them*, even if you sent a message more recently.
- `latestFromSelf()` — most recent entry authored by the bridge's own
  Discord account (discord.user.id). Default target for `.edit` and
  `.delete` — Discord only allows editing/deleting your own messages, and
  "your own messages" here means the ones the bridge posted representing an
  incoming SMS from the phone contact.
- `updateRememberedText(message, newText)` — rewrite a cache entry's text
  in place (used after `.edit` and after a Discord-side `messageUpdate`).
- `removeRemembered(message)` — splice a cache entry out (used after
  `.delete`, so a stale reference can't be targeted again).

## Phone-typed commands (Voice → Discord control plane)

Typed into the Messages app on the phone, parsed inside
`voice.on("messageCreate")` before the reaction/plain-forward fallback:

```
.reply "quoted target text"
the reply body (rest of the message, can span multiple lines)

.edit "quoted target text"
the new content

.delete
.delete "quoted target text"
```

Quotes are optional on all three — omitting them uses the direction-
appropriate default (`latestFromUser()` for `.reply`, `latestFromSelf()` for
`.edit`/`.delete`). `parseVoiceCommand` requires a first-line command plus at
least one non-empty payload line for `.reply`/`.edit` (no payload → not a
command, falls through to plain forwarding). `parseDeleteCommand` is a
single-line parser since delete has no payload.

If the quoted-target lookup misses, log via `debug(...)` and fall through to
sending the raw command text as a plain message — never throw or drop it
silently.

## Discord edits forwarded to the phone

`discord.on("messageUpdate", (oldMessage, newMessage) => ...)` forwards a
content change as:
```
edit: their old message

their new message
```
Skip when `oldMessage.content === newMessage.content` (embed unfurl fires
`messageUpdate` with unchanged text). Also call
`updateRememberedText(newMessage, newText)` so later commands/reactions
match the edited text, not the stale original.

## Library-level poll ordering fix (src/client.ts)

The poll loop's `tick()` builds a `Map` of events from `listThreads()` and
used to emit `messageCreate` immediately while iterating — but Google's
`api2thread/list` response order within a batch is NOT guaranteed
chronological. Two texts sent back-to-back between polls could get forwarded
to Discord in the wrong order. Fix: collect new events into an array first,
`sort((a, b) => a.timestampMs - b.timestampMs)`, then emit in that order.
`messageUpdate` still emits inline (no batching ambiguity per-id).

**Test-fixture gotcha:** a stub `listThreads` returning an *empty* thread
list on the first tick keeps `this.snapshot.size === 0` after that tick
(since `next` is also empty), so the *second* tick's `if
(this.snapshot.size === 0)` branch fires again — treated as another
"initial" snapshot, silently swallowing all `messageCreate` emission. Always
seed the first tick's fixture with at least one already-seen event so the
snapshot becomes non-empty before asserting on later batched creates.

**Also:** in the test file, prefer awaiting a `Promise.withResolvers()`
resolved by the event listener itself over a fixed `setTimeout` sleep — an
existing sibling test in this file still uses the timer pattern, but new
tests should signal on the actual condition (e.g. "both expected
`messageCreate` events fired") instead of guessing a duration.

## Dockerfile cache-ordering fix

`RUN bunx playwright install --with-deps chromium` (~4 min Chromium
download) only depends on `bun install` (its package.json), not on
`index.ts`/`bin/`. It must be placed *before* `COPY examples/discord-
bridge/tsconfig.json`, `COPY .../index.ts`, `COPY .../bin` — otherwise every
source-code edit busts Docker's layer cache for the Chromium install too,
turning a routine code change into a multi-minute rebuild.
