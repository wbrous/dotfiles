---
name: discord-selfbot-bridge-bun
description: "Use when working on the google-voice-ws Discord selfbot bridge (examples/discord-bridge/) — the youtsuho-v13 fork's getUploadURL file_size bug, stale 400-vs-401 send-token diagnosis, phone-number matching, threadId resolution, the WAA/reCAPTCHA capture-tokens workflow, and the SIGINT/destroy() crash fix."
---

## Uncaught exception on Ctrl+C (SIGINT)

`discord.js-selfbot-youtsuho-v13`'s `WebSocketShard#destroy()` dereferences
`this.connection` unconditionally. If the gateway connection was never
established, or already dropped (e.g. right after a Voice-side 503
disconnect), calling `discord.destroy()` throws a synchronous `TypeError:
null is not an object (evaluating 'this.connection.readyState')` that
becomes an uncaught exception crash on shutdown.

Fix in the `process.on("SIGINT", ...)` handler — swallow the error instead
of `void discord.destroy()`:

```ts
process.on("SIGINT", () => {
  voice.stop();
  try {
    void Promise.resolve(discord.destroy()).catch(() => {});
  } catch {
    // ignore — see WebSocketShard#destroy() this.connection null-deref bug
  }
  process.exit(0);
});
```

Note: the lib's `.destroy()` return type is typed as `void` in this fork,
so `discord.destroy().catch(...)` fails to typecheck (`TS2339`) — wrap in
`Promise.resolve()` first, and still guard with a synchronous `try/catch`
since the throw can happen before any promise is even returned.

## Edit-tool stale-hash gotcha

If a file was read a while ago and edited again later in the same session,
the edit tool may report "Recovered from a stale file hash using a previous
read snapshot" and silently base the edit on the STALE snapshot — dropping
any lines added to the file since that read (even by your own earlier edits
in the same session, if a later edit round-tripped through an old read).
After any edit that triggers this warning, `git diff` the file immediately
and diff-review it before moving on — don't assume the edit only touched
what you intended.
