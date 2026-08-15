---
name: spotify-playlist-search-total-unreliable
description: "Use when paginating Spotify Web API's /v1/search endpoint (type=playlist or others) and result counts seem too low, when writing/debugging offset-based pagination loops against it, or when the total field in the response looks inconsistent with actual item counts."
---

## Symptom
- Pagination stops early (sometimes after just page 1) even though more real results exist.
- Response's `playlists.total` (or equivalent `total` field) is `0` or otherwise implausibly low/wrong compared to items actually being returned.
- A page returns fewer items than the requested `limit` mid-stream (not just at the true end), and more real results exist at higher offsets anyway.

## Root causes (both empirically confirmed, not speculation)
1. **`total` is unreliable.** Spotify's playlist-search `total` frequently under-reports, sometimes literally `0`, even when hundreds of real results exist. Never use `offset >= total` as a loop-termination condition.
2. **Short pages don't mean "end of results."** A page with `items.length < limit` can still be followed by more real results at the next offset. `items.length < limit` is *not* a trustworthy end-of-results signal either.
3. **The search index itself is incomplete server-side** (documented: `spotify/web-api#1096`, multiple Spotify community threads). Even with perfect exhaustive pagination, Spotify's playlist search will not surface every real, public, matching playlist for common query terms. This is unfixable client-side — don't over-promise "exhaustive" results to users; only exhaustive *of what Spotify's index returns*.

## Fix
- Advance `offset` by the `limit` you actually requested each iteration — never by `items.length` returned.
- Only stop the loop when `offset` reaches the API's hard ceiling (`offset + limit <= 1000` for Spotify search — also a hard, real, undocumented-workaround-around limit).
- Track/report `scanned` (real item count) and `reportedTotal` (Spotify's claimed total) separately in any UI/diagnostics — don't imply the two numbers should match; explicitly note `total` is known-unreliable so users aren't confused when e.g. "scanned 772, total ~0" shows up together.
- This bounds worst case to `ceil(1000/50) = 20` requests, so removing all early-stop trust costs nothing meaningful.
