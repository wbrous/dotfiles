---
name: extract-jsrendered-slide-decks
description: "Use when needing to read/review the content of a Google Slides, Canva, or SharePoint (Office Online) presentation link — especially \"review these workshop slides\" style requests — and the read tool returns only metadata/title or a blank canvas because the deck is JS-canvas-rendered rather than text-based."
---

## Problem

`read` on a Google Slides / Canva / SharePoint presentation URL often returns only
og:title/og:description metadata, or a wall of `<!-- image -->` placeholders, because
these viewers render slides to `<canvas>` — there is no DOM text to scrape.

## Fix order (cheapest first)

1. **Try Google Slides pptx export first** (works when the deck actually has real
   text boxes, not canvas-only images):
   `https://docs.google.com/presentation/d/<ID>/export/pptx`
   Read this URL directly — the `read` tool auto-converts pptx via markit and gives
   clean per-slide markdown with real bullet text. This is dramatically cheaper than
   screenshotting. If every slide comes back as only `<!-- image -->` comments with no
   text, the deck is canvas-rendered and you must fall back to browser screenshots (below).

2. **Canva / SharePoint (Office Online) / canvas-only Google Slides**: no text export
   exists. Use the `browser` device:
   - `action: "open"` the URL as a headless tab (works even for edit-mode links with
     `?usp=sharing` etc. — no auth needed for anonymous-viewable links).
   - Canva and SharePoint editors load with a **thumbnail sidebar** (left strip of
     slide thumbnails, ~x=100 in a 1024-wide viewport). Click each thumbnail
     (`tab.page.mouse.click(x, y)`) and screenshot the main pane after each click —
     screenshots must run through `tab.screenshot({})`, saved to a temp path, then
     immediately `read` that path to view/OCR the image inline. Do NOT try to bulk-dump
     base64 image data into eval output — it silently multiplies token/tool payload.
   - Watch for **stale-click artifacts**: the first click on a thumbnail sometimes
     doesn't register (page hasn't finished loading, or coordinates are 1px off the
     hit target) — screenshot will show the previous slide unchanged even though the
     thumbnail highlight appears to move. Verify by checking the highlighted thumbnail
     border position in the screenshot itself, not just trusting the click succeeded.
   - Long decks (10+ slides): thumbnail sidebar scrolls. Either scroll the sidebar with
     `tab.page.mouse.wheel({deltaY: N})` between click batches, or prefer keyboard
     navigation on the main slide canvas (click into it once for focus, then
     `PageDown`/`ArrowRight` + short sleep + screenshot in a loop) — this is more
     reliable than fighting scroll offsets in a thumbnail strip.

3. **Google Slides `mobilepresent` view** (when pptx export is all-image): keyboard
   `ArrowRight` from the *first* slide only works reliably if you first jump `Home`
   then re-press ArrowRight the correct number of times per iteration — a single
   `ArrowRight` per loop iteration frequently jumps straight to the last slide because
   the deep-link fragment (`#slide=id.p`) doesn't always land on slide 1. Safer pattern:
   click into the canvas for focus, then `Home`, then press `ArrowRight` exactly `i`
   times for the i-th slide, sleep ~700ms, screenshot.

## General screenshot workflow (all three cases)

```
const result = await tool.browser({ action: "run", name: "<tabname>", code: `
  const sleep = (ms) => new Promise(r=>setTimeout(r,ms));
  const paths = [];
  for (let i=0; i<N; i++){
    // navigate one slide forward (method depends on host, see above)
    await sleep(700);
    paths.push(await tab.screenshot({}));
  }
  return paths;
`});
```
Then `read` each returned path individually (do not try to view many at once in one
call if avoidable — batch reasonable groups of ~8-10 to keep context usage sane).

## Multi-deck review requests

When asked to review several linked decks at once (e.g. "review all workshop
slideshows"), open all deck URLs as separate headless tabs in parallel
(`browser action: open`, different `name` per tab) first, then run extraction on each
— pptx export attempt for Google Slides links, screenshot-loop for Canva/SharePoint —
in parallel eval calls where possible.
