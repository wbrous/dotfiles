---
name: hyperion-records-alac-purchase-flow
description: "Use when buying lossless FLAC/ALAC tracks or albums from hyperion-records.co.uk and the \"Download all ALAC/FLAC\" buy buttons seem missing — the track page defaults to showing only MP3 buy buttons even when lossless formats exist."
---

## Problem

Hyperion Records (hyperion-records.co.uk) sells classical recordings as MP3/FLAC/ALAC, often at CD-quality and Studio Master (24-bit/96kHz) tiers. On a track/album page (`dw.asp?dc=...`), the buy buttons default to showing **MP3 only**, even when the page text elsewhere says "Studio Master FLAC & ALAC downloads available". There is no visible ALAC/FLAC "buy" button until you switch a format selector — easy to miss, looks like the checkout button is just gone.

## Fix / Flow

1. Top-right of the nav bar there's a small format dropdown button labeled **"MP3"** (default). Click it.
2. A submenu appears: **"FLAC downloads"**, **"ALAC downloads"**, **"CD / LP only"**. Click the one you want (e.g. "ALAC downloads").
3. The buy-button area on the page re-renders with format-specific buttons, typically:
   - `Download all ALAC 16-bit 44.1 kHz £X.XX` (CD-quality)
   - `Download all ALAC 24-bit 96 kHz £X.XX` (Studio Master, better quality, costs more — recorded that way originally, not upsampled)
4. Click the desired button. This adds to basket via AJAX **silently** — no popup/modal, no page navigation. Confirm via the nav basket icon, which changes from "(No items)" to "1 item".
5. Click the basket icon (top nav) → dropdown shows basket summary + a **"Checkout ..."** link pointing to `/Member/Welcome.aspx`. Click it, sign in / create free account, pay, download the file(s).

## Notes
- Basket/cart page itself: `/Anon/Basket.aspx`.
- Price differs per format tier; Studio Master ALAC/FLAC (24-bit/96kHz) is the highest quality offered and usually only ~£0.40 more than CD-quality for a single track.
- Works the same for whole-album purchases ("View whole album" / "Download all" buttons follow the same format-dropdown dependency).
