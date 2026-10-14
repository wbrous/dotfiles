---
name: omp-web-search-provider-selection
description: "Choosing or switching the omp web_search provider: web role, fallback chain, testing with omp q, which tool is actually answering."
---

# omp web_search provider selection

## Key facts (from omp://tools/web_search.md and omp://settings.md)
- Provider choice is the `web` model role: `modelRoles.web`. Candidates are catalog selectors: `web/<engine>` (e.g. `web/exa`, `web/parallel`, `web/brave`, `web/duckduckgo`, `web/google`) or a chat model with `webSearch` grounding (e.g. `anthropic/claude-haiku-4-5`, a `google-antigravity/...` Gemini model).
- Fallbacks: `retry.fallbackChains.web`. If unset, the built-in default chain is used: parallel, hosted, exa, firecrawl, searxng, startpage, duckduckgo, ecosia, google, mojeek (public is explicit-only).
- The in-session tool has no per-call model override. One-shot override only via CLI: `omp q --model web/duckduckgo "query"` (aliases: `omp search`, `omp web-search`).
- Legacy `providers.webSearch*` keys are auto-migrated into the role and chain; do not set them.
- Per-candidate timeout: `providers.webSearchTimeoutSeconds` (default 60, max 300).

## Gotcha: which tool is answering?
The session may also have a separate mounted `web_search` tool (e.g. an Ollama-backed one returning sources only). It is NOT governed by `modelRoles.web`. Check the tool inventory and the result shape before assuming a config change affects it. Grounded providers (Perplexity, Gemini, Anthropic, Codex, OpenAI, xAI) return an `answer` plus citations; engine-style ones return sources only.

## Procedure
1. `read cfg://modelRoles` (the `web` key lives inside the modelRoles record; `cfg://modelRoles/web` errors as unknown) and `read cfg://retry/fallbackChains`.
2. Read `omp://tools/web_search.md` (Provider selection + adapter sections) for availability requirements per provider.
3. Writes to cfg:// need user approval; set session-only first, test, then ask before `/save`.
4. Test a candidate with `omp q --model <selector> "niche query"` before persisting.

## Selection guidance
- Best for niche technical lookups: grounded providers with citations (Perplexity if the user has an account; Gemini via an already-logged-in google-antigravity).
- Good keyless fallbacks that surface GitHub issues/PRs/wiki pages: `web/exa`, `web/parallel`.
- Scraped engines (google/ecosia/mojeek/ddg/startpage) can hit bot challenges and are last resort.
- Unverified: whether a specific Gemini selector is a valid grounded `web` candidate on a given install; confirm with `omp q --model`.
