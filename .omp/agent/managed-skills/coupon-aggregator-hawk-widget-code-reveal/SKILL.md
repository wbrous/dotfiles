---
name: coupon-aggregator-hawk-widget-code-reveal
description: "Use when scraping/browser-automating coupon codes from sites using the \"hawk\" coupon widget (TechRadar, Tom's Hardware, Discoup, and similar Future plc / affiliate coupon pages) that show \"Get Code\" buttons — the real code is never in page HTML/DOM and can't be extracted via evaluate() or network sniffing, since clicking fetches the code and immediately same-tab-redirects to the retailer with an affiliate cookie before any response can be captured. Also covers Dell.com blocking headless browser requests outright (\"Access Denied\")."
---

## Problem

Coupon aggregator sites (TechRadar `/coupons/<brand>`, Tom's Hardware `/coupons/<domain>`, Discoup, and other Future plc-network pages) render codes as masked text (e.g. `**********************NUP`) with a "Get Code" button. Attempting to extract the real code via headless browser:

- `tab.evaluate()` reading DOM after click → button has no `data-code` attribute, no reveal happens in-page.
- Clicking the button triggers an instant same-tab navigation to the retailer (e.g. dell.com) with affiliate query params (`cjevent`, `dgc=CJ`, `publisherid`, etc.) — the real code was fetched via an internal API call synchronously with the click and used only for a clipboard-copy + redirect, not rendered as text.
- Setting up `page.on('response')` or `page.on('request')` listeners *before* the click still races the navigation — the reveal API call is fast and the frame navigates away before most listeners fire reliably; this is unreliable, not a hard block, but not worth building infra around for a one-off task.
- Retrying causes stale-tab errors (`Cannot read properties of undefined (reading 'click')`) because the tab already navigated to the retailer from a prior click.

Additionally: `dell.com` product/shop pages return `Access Denied` to headless Chromium (bot detection), even though the coupon aggregator pages themselves load fine.

## What to do instead

1. Don't try to force-reveal codes via DOM/network tricks — treat the aggregator's masked-code list as the ceiling of what's extractable without a real browser session (cookies, real click, human-driven redirect).
2. Report the offer *terms* (discount %, category, expiration) straight from the readable page text — that part is always plaintext and reliable.
3. For the actual code string, tell the user to click "Get Code" themselves (it auto-copies + redirects), or note the site's own text: "click Get Code to reveal, then apply at checkout" — this is by design (affiliate tracking requires the click).
4. If asked to verify against the retailer directly (e.g. dell.com), expect `Access Denied` from headless browser; don't retry with different headers as a first resort — note the block and rely on the aggregator + web_search summaries instead.
5. RetailMeNot triggers a Cloudflare "Just a moment..." challenge under headless browser — skip it, use TechRadar/Tom's Hardware/Discoup instead.
6. couponfollow.com returned an empty body (0-length innerText) after full load — also not scrapable this way; skip.
