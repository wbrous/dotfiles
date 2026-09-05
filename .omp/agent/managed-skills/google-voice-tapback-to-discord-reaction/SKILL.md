---
name: google-voice-tapback-to-discord-reaction
description: "Use when working on the google-voice-ws discord-bridge example and forwarding Google Voice's iMessage-style tapback notification texts (Liked/Loved/Disliked \"…\" or Reacted emoji to \"…\") — map them to a Discord message reaction on the originally-forwarded message instead of posting them as new DM text."
---

## Problem

Google Voice (bridging iMessage tapbacks over SMS) sends reaction notifications as plain SMS text in this exact format:

```
Liked "Thanks"
Loved "U set a range?"
Disliked ":>"
Reacted 🥺 to "🤔🤔🤔"
```

Quotes are curly (`“” `U+201C/201D), and the quoted content can span multiple lines:

```
Liked "HFJH
JDDD
DJDJKFKF
JDDDK
EJDKFF"
```

Naively forwarding these to Discord as plain messages is noisy — the user wants them rendered as a Discord reaction on the original forwarded message instead.

## Solution (implemented in `examples/discord-bridge/index.ts`)

1. **Parse the pattern** with one regex per shape, quote class `[“"]([\s\S]*)[”"]` (dotall via `[\s\S]*` for multi-line):
   - `^(Liked|Loved|Disliked) <quoted>$` → map label to emoji (`Liked`→👍, `Loved`→💖, `Disliked`→👎).
   - `^Reacted (\S+) to <quoted>$` → use the captured emoji literally.
2. **Track forwarded messages**: maintain a small bounded (e.g. 50-entry) history of `{ text, message }` for every plain-text message this bridge forwards Voice→Discord. Only remember text sends, not attachment sends (reactions target text content).
3. On a new Voice message: if it has no attachment and matches the reaction pattern, look up the quoted text (trimmed) in the recent-forwarded history. If found, call `message.react(emoji)` and return early — do NOT send a new Discord message. If no match is found, fall back to sending the raw notification text normally (better than silently dropping it).

## Gotchas

- Must check `!attachment` before attempting reaction-pattern parsing — MMS captions could coincidentally look similar but should never be treated as tapbacks.
- `discord.js-selfbot-youtsuho-v13` exports `Message` as a type — `import { Client, type Message } from "discord.js-selfbot-youtsuho-v13"` for the history array's type.
- Verify parsing logic with a standalone `eval` script (not `tsc`/build) since the package has unrelated pre-existing transitive dependency resolution errors (`ffmpeg-static`, `chromium-bidi`) that block a full bundle build — those are irrelevant to this feature; `tsc --noEmit -p .` is sufficient to confirm type correctness.
