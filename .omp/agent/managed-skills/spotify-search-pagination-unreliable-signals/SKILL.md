---
name: spotify-search-pagination-unreliable-signals
description: "Use when paginating Spotify Web API's /v1/search endpoint (any type: playlist, track, album, etc.) and result counts seem lower than expected, or writing/debugging offset-based pagination loops against Spotify search."
---

## Symptom
Pagination loop against Spotify's `/v1/search` stops early, returning far fewer results than the query should have, even though more real results exist at higher offsets.

## Root cause
None of Spotify search's usual pagination signals are trustworthy:

1. **`response.<type>s.total` under-reports.** Frequently much lower than the real result count, sometimes `0` even when results exist. Do not use `offset >= total` as a stop condition.
2. **A page can return fewer items than the requested `limit` mid-stream — not just at the true end.** E.g. request `limit=50` at `offset=0`, get back 48 items, but `offset=50` still has 50 more real items. So `items.length < limit` is *not* a valid "this is the last page" signal either.

Both bugs were empirically reproduced: mocked a page with `total: 0` but more real pages after it (old `offset >= total` logic stopped after page 1), then mocked a `48`-item page with `total: 100` where page 2 (at offset 50, not 48) had 50 more real items (old `items.length < limit` logic stopped there too).

## Fix
Don't trust any early-stop signal. Always advance `offset` by the `limit` you actually requested (never by `items.length` received), and walk unconditionally up to the API's hard ceiling (`offset + limit <= 1000`, i.e. offset never exceeds ~1000). This bounds the walk to at most `1000 / pageSize` requests (e.g. 20 requests at `limit=50`) — cheap and deterministic regardless of how few real results a query has.

```ts
const SEARCH_PAGE_SIZE = 50;
const SEARCH_MAX_OFFSET = 1000; // Spotify hard limit: offset + limit <= 1000

let offset = 0;
const results = [];
while (offset < SEARCH_MAX_OFFSET && results.length < maxResults) {
  const limit = Math.min(SEARCH_PAGE_SIZE, SEARCH_MAX_OFFSET - offset);
  const json = await fetchSearchPage({ q, limit, offset });
  for (const item of json.items ?? []) {
    // ...filter/collect...
  }
  offset += limit; // NOT items.length, NOT gated on total
}
```

Report actual `scanned` count (items iterated) and Spotify's reported `total` separately to the caller/UI so "0 results" vs "search stopped short" is distinguishable — don't silently trust either number.

There is no way to search past the hard `offset + limit <= 1000` ceiling via the public search endpoint; that part of the limit is real and documented, unlike the pagination-termination signals above.
