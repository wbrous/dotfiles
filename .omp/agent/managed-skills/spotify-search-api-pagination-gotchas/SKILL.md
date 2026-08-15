---
name: spotify-search-api-pagination-gotchas
description: "Use when paginating Spotify Web API search results (e.g. GET /v1/search, type=playlist/track/album) and result counts seem lower than expected, or writing/debugging offset-based pagination loops against Spotify's search endpoint."
---

## Symptom
Pagination loop against Spotify Web API `/v1/search` (any type, e.g. `playlist`) stops far earlier than expected — e.g. reports scanning 48 items when the response's own `total` field says 100.

## Root causes (both observed, both silent)
1. **`total` field is unreliable.** It frequently under-reports (sometimes `0`) even when more pages genuinely exist. Never use `if (offset >= total) break` as a loop-termination condition.
2. **Short pages happen mid-stream, not just at the end.** A page can return fewer items than the requested `limit` (e.g. 48 when you asked for 50) while more real results are still available at a later offset. So `if (items.length < limit) break` is *also* an unsafe termination signal — it will truncate results.

## Correct pagination pattern
- Always advance `offset` by the `limit` you actually requested, **not** by `items.length` received.
- Only stop when a page comes back **completely empty** (`items.length === 0`) — that's the one signal that isn't observed to lie.
- Bound the loop by Spotify's hard ceiling anyway: `offset + limit <= 1000` (search endpoint max), so worst case is `1000/limit` requests — no infinite-loop risk even if you never trust `total`.

```ts
while (offset < SEARCH_MAX_OFFSET) {
  const limit = Math.min(PAGE_SIZE, SEARCH_MAX_OFFSET - offset);
  const json = await fetchPage(query, limit, offset);
  const items = json.result?.items ?? [];
  if (items.length === 0) break; // only trustworthy stop signal
  // ...process items...
  offset += limit; // not items.length
}
```

## Debugging technique used to isolate this
Reproduce with a hand-rolled mock of `{ items, total }` per offset that deliberately returns a short/partial page with more real data at a later offset, run the actual loop logic against it via `eval`, and assert the scanned count matches the full mock dataset rather than truncating early. This caught both bugs without needing live Spotify credentials.
