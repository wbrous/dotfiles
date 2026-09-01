---
name: google-voice-headless-send-token-refresh
description: "Use when automating capture of Google Voice's WAA/BotGuard + reCAPTCHA outbound send tokens (GV_SEND_ATTESTATION_TOKEN / GV_SEND_RECAPTCHA_TOKEN) via headless Playwright — e.g. for the google-voice-ws discord-bridge example or any client replaying a browser session against voice.google.com's sendsms endpoint — WITHOUT actually delivering a message. Covers why driving the \"Send new message\" contact-picker composer never fires a real send (Voice requires a saved Google Contact there), why direct navigation to a ?itemId=t.+digits thread URL doesn't select the thread either, the working technique (click through existing thread-list rows and match by the URL's itemId digits, not fragile contact-name text, to select a thread that already has message history), and the request-interception trick: hook page.route on the sendsms request and call route.abort() before it reaches Google's servers — the token pair is already in the outgoing request body, so aborting it yields fresh tokens with zero message sent/visible to the recipient."
---

## Problem

Google Voice's `sendsms` endpoint requires a WAA/BotGuard attestation token + reCAPTCHA-style token pair, minted only by the page's own obfuscated JS during a **genuine interactive send attempt**. These tokens cannot be fabricated and expire in minutes-to-hours, so periodic re-capture is needed for any automated outbound sender — but you almost never want the recipient to actually receive a fake "refreshing tokens" text every cycle.

Two headless automation approaches that look plausible **do not work at all** (0 network hits, not just wrong tokens):

1. **Driving the "Send new message" composer** (typing a raw phone number into the "Enter a name or number" field, selecting a suggestion, typing body, pressing Enter/clicking Send). This produces 0 `sendsms` network hits even though every UI step visibly succeeds (recipient selected, body filled). Root cause: Voice's anti-abuse gating only mints tokens for sends to a **saved Google Contact** through this flow; a raw un-contacted number silently never fires the send.
2. **Direct `page.goto("https://voice.google.com/u/0/messages?itemId=t.%2B<digits>")`**, even after the SPA has already loaded once. This does not reliably select the thread — the composer that appears is still the generic new-message one (with a visible "Enter a name or number" input), not the thread's own composer.

## Working technique: select the thread

Click through the **existing thread-list rows** and match by the resulting URL's `itemId` param — do not match by visible contact-name text (fragile, not always present, and requires knowing the display name in advance).

```ts
await page.goto("https://voice.google.com/u/0/messages", { waitUntil: "domcontentloaded" });
await page.waitForTimeout(4000); // let the Angular app hydrate the thread list

const rows = page.locator(".mat-ripple.container"); // each conversation row
const rowCount = await rows.count();
const wantDigits = phone.replace(/\D/g, "");
let found = false;
for (let i = 0; i < rowCount; i++) {
  await rows.nth(i).click({ timeout: 8000 }).catch(() => {});
  await page.waitForTimeout(1000);
  const m = page.url().match(/itemId=t\.([^&]+)/);
  const itemDigits = m ? decodeURIComponent(m[1]).replace(/\D/g, "") : "";
  if (itemDigits && (itemDigits === wantDigits || itemDigits.endsWith(wantDigits) || wantDigits.endsWith(itemDigits))) {
    found = true;
    break;
  }
}
```

Clicking through rows is harmless (just navigation/selection, no side effects) and works whether or not the number is a saved Contact, because it targets a thread that **already has message history** rather than trying to originate one.

Once the right thread is selected, only ONE visible composer remains (`textarea[placeholder="Type a message"]`) — the "Enter a name or number" recipient input disappears, confirming the thread is truly selected.

**Precondition:** at least one message must already have been exchanged with the target number (a thread must pre-exist) — this technique cannot originate a brand-new conversation to an uncontacted number headlessly.

## Capturing tokens WITHOUT sending a message: intercept + abort

Register a `page.route` handler on the `sendsms` request **before** triggering the send. Read the request body for the tokens, then `route.abort()` instead of `route.continue()` — the request never reaches Google's servers, so nothing is delivered, but the token pair (which is already serialized into the outgoing request body) is fully captured:

```ts
let tokens: { attestation: string; recaptcha: string } | null = null;

await page.route("**/api2thread/sendsms*", async (route) => {
  const req = route.request();
  try {
    const body = JSON.parse(req.postData() ?? "null") as unknown[] | null;
    const field = body?.[10] as unknown[] | undefined; // [attestationToken, null, null, recaptchaToken]
    if (Array.isArray(field) && typeof field[0] === "string" && typeof field[3] === "string") {
      tokens = { attestation: field[0], recaptcha: field[3] };
    }
  } catch {
    // leave tokens null on malformed body
  }
  await route.abort("failed");
});

const composer = page.locator('textarea[placeholder="Type a message"]');
await composer.waitFor({ state: "visible", timeout: 15_000 });
await composer.click();
await composer.fill("[AUTOMATED] Refreshing tokens...");
await page.waitForTimeout(500);
await composer.press("Enter"); // triggers sendsms — intercepted and aborted above
await page.waitForTimeout(3000);
```

Why this is safe: `page.route` interception happens client-side in Playwright, upstream of the actual network layer — `route.abort()` prevents the request from ever leaving the browser process. There is no response to check (no `page.on("response")` listener needed or useful here — the request never gets one), so success is judged purely by whether `tokens` got populated from the request body.

**Verified**: after an abort-based capture, the message count in the thread (checked via `[class*=message-text]` elements containing the sent text) is unchanged from a fresh page load with no send attempt at all — confirming zero delivery. The UI shows no error/toast either; the composer just clears as if nothing happened.

## Full reference implementation

See `examples/discord-bridge/bin/refresh-tokens.ts` in the `google-voice-ws` repo (working, verified end-to-end: real headless intercept-and-abort cycle, tokens captured and written to `.env`, confirmed zero message delivered via before/after thread message-count check). Supports one-shot (`bun run capture-tokens`) and continuous (`LOOP=1 bun run refresh-tokens-loop`, default every 60 min) modes, reusing a persistent Chromium profile dir (`.gv-browser-profile`) so no login flow re-runs after the first successful capture.
