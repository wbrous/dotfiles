---
name: spotify-search-playlist-pagination-pitfalls
description: "Use when paginating Spotify Web API's /v1/search?type=playlist endpoint and result counts seem too low, or when writing/debugging offset-based pagination loops against it — covers unreliable total/short-page signals and the underlying incomplete search index."
---

## Symptom
Client-side pagination against `GET /v1/search?type=playlist` returns far fewer playlists than expected for a query you know has many real matches (e.g. a common title).

## Two distinct, stacked problems

1. **Client-side pagination bugs (fixable):** Spotify's per-page pagination signals for this endpoint are unreliable — do not trust them as loop-termination conditions:
   - `playlists.total` frequently under-reports (sometimes `0`) even when more results exist.
   - A page returning fewer items than the requested `limit` does **not** reliably mean "last page" — Spotify can return a short/partial page mid-stream with more real results at higher offsets.

   **Fix:** never trust `total` or short-page-length to stop early. Always advance `offset` by the `limit` you actually requested (not by `items.length` received), and loop unconditionally until `offset` reaches the hard API ceiling (`offset + limit <= 1000`). This bounds the walk to at most `1000/limit` requests (e.g. 20 requests at limit=50) — cheap, and the only way to guarantee you've seen everything the API will hand back for that offset window.

2. **Server-side index incompleteness (NOT fixable client-side):** Even with fully correct/exhaustive pagination to offset 1000, Spotify's playlist search index itself is documented and widely reported as incomplete. Real, public playlists — including ones owned by Spotify itself — routinely don't surface via `/v1/search`, regardless of pagination correctness. See `spotify/web-api#1096` on GitHub and multiple Spotify Community threads (e.g. "Not all Spotify playlists appearing in search", "Spotify API Not Returning All Public Playlists Owned by Spotify").

   There is no known workaround for this from the client. If a user reports suspiciously low result counts for a common/generic playlist title, first confirm pagination is exhaustive (per #1), then attribute any remaining gap to this documented Spotify-side limitation rather than continuing to chase it as a bug in your own code.

## Practical guidance
- When building a UI/tool around this endpoint, surface diagnostics (e.g. "combed through N playlists, Spotify reported ~M total") so gaps are visible/debuggable rather than silently swallowed.
- Document the known incompleteness for end users (link the GitHub issue) instead of implying pagination = completeness.
