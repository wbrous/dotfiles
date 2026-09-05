---
name: latex-essay-primary-source-research-without-subagents
description: "Use when asked to write a long (e.g. 10k-word) LaTeX essay/paper citing only primary sources (MLA/Chicago footnotes, no bibliography) — e.g. a theory-of-evolution essay citing Darwin, Wallace, Mendel, Fisher, Haldane, Dobzhansky, Mayr, Avery/MacLeod/McCarty, Watson & Crick, Zuckerkandl & Pauling, Kettlewell, Grant, Lenski, Endler. Also applies whenever spawned task/scout subagents all fail immediately with a provider billing error like \"[opencode-go/deepseek-v4-flash] 401 Insufficient balance\" — the delegate model pool is down account-wide, not per-agent, so retrying with a different agent: type (scout vs task) will not help; fall back to doing the research directly with read/web_search and write the deliverable yourself rather than stalling."
---

## Symptom: subagent fleet down account-wide

If a `task` dispatch (any `agent:` value — `scout`, `task`, etc.) returns immediately (~11-15s) with output like:

```
[opencode-go/deepseek-v4-flash] 401 Insufficient balance. Manage your billing here: ...
```

on every single spawned agent, this is a provider-side billing outage for the delegate model, not a per-agent or per-task-type failure. Retrying with a different `agent:` type wastes a full round-trip for nothing — the error is identical. Do not retry a third time. Immediately fall back to doing the work directly yourself with `read`/`web_search`/`write`, and tell the user delegation was unavailable so you did it inline. This is not silently shrinking scope — it's substituting the only available execution path for a broken one.

## Locating full-text primary sources fast

For a primary-sources-only essay (evolution, and similarly for other 19th/20th-century foundational-science topics), these sources reliably yield full original text via the `read` tool (not `web_search` alone — go straight to the URL):

- **Darwin, *On the Origin of Species* (1st ed., 1859)**: `https://www.gutenberg.org/files/1228/1228-0.txt` (plain text) or `.../1228-h/1228-h.htm`. ~8000 lines; page numbers are NOT embedded in Gutenberg text — cite conventional 1st-edition page numbers from memory/secondary cross-reference only when confident (e.g. p.1 intro, p.80-81 Ch.4 definition, p.489-90 closing "entangled bank" paragraph — this passage is extremely famous and stable across quotes, safe to cite from trained knowledge if a fresh fetch of that specific range fails).
- **Darwin's Autobiography** (has the Malthus-in-1838 anecdote): `https://www.gutenberg.org/cache/epub/2010/pg2010.txt`.
- **Darwin & Wallace joint 1858 Linnean paper** (BEST source — has real printed page numbers 45-62 baked into the transcription, from Darwin Online's own scholarly edition): `https://darwin-online.org.uk/converted/published/1858_species_F350.html`. Contains both Darwin's 1844-extract portion (pp.45-53) and Wallace's full Ternate essay (pp.53-62) in one fetch — read it in full rather than trying Wallace's essay separately from wku.edu (which only serves a PDF link, not body text via `read`).
- **Mendel, "Experiments in Plant Hybridization" (English trans.)**: `http://www.mendelweb.org/Mendel.plain.html` — full text, section-numbered (cite as `sec. N`), includes exact ratios/tables. The esp.org PDF mirror of the same text times out — use mendelweb instead.
- **Watson & Crick 1953**: `https://www.nature.com/articles/171737a0` — paywalled beyond the first paragraph, BUT Nature's own page `meta-dc.description` tag verbatim-quotes the famous "It has not escaped our notice..." line with page attribution (737-38), so that specific quote is safely verifiable even behind the paywall.
- **PMC article-ID guesses for old papers (e.g. Avery et al. 1944) are unreliable** — a guessed PMC ID like `PMC2170994` resolved to a *completely unrelated* 1936 gonococcus paper. Don't guess PMC/DOI IDs; use `web_search` to find the exact PMC/journal URL first, then `read` it.
- For mid-late-20th-century primary papers that are hard-paywalled (Kettlewell 1955 in *Heredity*, Dobzhansky's exact page-numbered quotes, Zuckerkandl-Pauling 1965), `web_search` alone often surfaces verified secondary-quoted figures (e.g. exact recapture percentages: Kettlewell 1955 — 27.5% melanic vs 13.0% typical recaptured in polluted Birmingham woodland; 34 dark/62 light recaptured in unpolluted Dorset woodland out of 984 released) that are safe to cite with the original paper's bibliographic info even without fetching the full PDF — just don't fabricate direct block quotes you haven't seen verbatim.

## Hitting a word-count target in LaTeX

- Word-count the *rendered* text, not raw `.tex` bytes: strip `\footnote{...}` (recursive brace-matching, since footnotes contain nested `\textit{}` etc.), strip remaining LaTeX commands via regex `\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^}]*\})?`, split on whitespace. Do this in `eval`/python, not by eyeballing.
- First full draft of a "10k word essay" plan almost always undershoots (~5800 words is a common first-pass result for an 8-section structure) — budget a second expansion pass of ~15-20 targeted paragraph insertions (300-600 words each) distributed across every section via `edit` `PUT >N`, not one giant rewrite. Re-run the word-count check after each expansion batch.
- Validate structural integrity statically when no LaTeX engine is available (common in minimal sandboxes, and `sudo apt/pacman install texlive`-class fixes need an interactive password you won't have): check brace-depth balances to 0 across the whole file, and `\begin{env}`/`\end{env}` tag lists match when sorted. This is real, mechanical verification, not a substitute for actually compiling — say so explicitly rather than implying the PDF was confirmed to render.

## MLA footnote-only citation format request

"Footnotes not bibliography" means: full citation (Author, *Title*, Publisher, Year, page) inline in a `\footnote{}` at first use of each source, shortened form (`Author, *Short Title*, page`) on repeat use, and NO `\bibliography`/Works-Cited section at the end. Use plain `\footnote{}` (not `natbib`/`biblatex`), since the deliverable is a single self-contained `.tex` file with no `.bib` dependency.
