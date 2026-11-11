# LaTeX Gotchas

Single-document fixes: keep code blocks on one page, boxed-note environments, and primary-source essay mechanics.

## Never let a code block split across pages

**Symptom:** An `lstlisting` frame cut at a page boundary, continuing on the next page.

**Fix:** `\usepackage{needspace}`, then before every listing:

```latex
\needspace{N\baselineskip}
\begin{lstlisting}
...
\end{lstlisting}
```

Pick `N` = block line count + ~4-6 headroom. `needspace` inserts a page break when remaining space is insufficient, so the whole block lands together on a fresh page — simpler and more reliable than floats or `samepage` for verbatim/listings. Keep blocks under ~50-55 lines at `footnotesize` with line numbers (about what fits on US-letter, 1in margins, with a heading + lead-in). Longer files: split presentation across steps ("add this field", "add this method", "wire into loop()"), never one giant dump.

Verify visually: `pdftoppm -png -r 150 file.pdf pageprefix`, then read a sample of pages back.

_Migrated from: latex-beginner-tutorial-single-page-code-blocks_

## The `\filebox` banner + examples/ folder pattern

**Symptom:** Tutorial readers can't tell which real file a code block edits, or have nothing to diff against.

**Fix:** Banner macro called right before each block:

```latex
\newcommand{\filebox}[2]{%
  \par\vspace{4pt}\noindent\colorbox{fileBg}{\parbox{\dimexpr\textwidth-2\fboxsep}{%
    \small\textbf{File:} \texttt{#1} \hfill \textbf{Full reference copy:} \texttt{examples/#2}%
  }}\vspace{-2pt}
}
```

`\filebox{pedro/Constants.java}{pedro/Constants.java}`. Build `examples/` as real, complete files matching the PDF's final wired-up state, each header-commented ("REFERENCE COPY — see doc/lessons/<pdf>.pdf, Step N. Not wired into the build."). Place it OUTSIDE the build source root (e.g. `doc/lessons/examples/`, never under `TeamCode/src/main/java/`) so reference files can't be compiled or collide with real symbols.

Ground example values in real data: cite the authoritative source (game manual, CAD, spec) near the block, with its stated tolerance — flag sourced-vs-illustrative numbers explicitly, never silently swap placeholders for sourced values.

Beginner-tutorial structure that works, per step: What's broken/missing → What we're building (plain-English plan) → one full code block → "reading this block, piece by piece" walkthrough → how to prove it worked. Open with a Step 0 primer teaching language *shape* via analogy (class = labeled box, field = sticky note, method = named action, `public`/`private`/`static` = who may touch it, e.g. `Follower` = GPS receiver + steering wheel) — when told "don't teach syntax", skip grammar mechanics (semicolons/braces), not `public static` semantics.

_Migrated from: latex-beginner-tutorial-single-page-code-blocks_

## `\newenvironment` boxed note: Missing } inserted

**Symptom:** A definition like this compiles with `! Missing } inserted.` at `\end{note}`:

```latex
\newenvironment{note}{\par\vspace{4pt}\noindent\colorbox{noteBg}{\begin{minipage}{\dimexpr\textwidth-2\fboxsep}\vspace{2pt}}}{\end{minipage}}\vspace{4pt}}
```

**Cause:** `\colorbox{color}{<content>}` needs `<content>` fully brace-balanced. Opening `minipage` in begin-code and closing it in end-code splits one balanced construct across two `\newenvironment` argument groups — fundamentally broken, not a typo.

**Fix:** Use a construct designed to straddle begin/end:

```latex
\newenvironment{note}{\par\vspace{6pt}\noindent\begin{quote}\small\itshape}{\end{quote}\vspace{2pt}}
```

Rule: every brace-argument macro (`\colorbox`, `\fbox`, `\parbox`) opened in begin-code must close in begin-code; only true `\begin{x}`/`\end{x}` environments may pair across the split. For a genuinely colored box, use `mdframed` or `tcolorbox` environment forms, which solve the split internally.

_Migrated from: latex-newenvironment-boxed-note-brace-mismatch_

## Long primary-source essay: finding texts, counting words, footnote-only citations

**Scope:** Long (e.g. 10k-word) LaTeX essay citing only primary sources, MLA/Chicago footnotes, no bibliography.

**Locating full text fast:** go straight to the URL with `read`, not `web_search` alone. Reliable hits: Darwin *Origin* 1st ed. at `https://www.gutenberg.org/files/1228/1228-0.txt` (no embedded page numbers — cite famous stable pages only when confident, e.g. p.1 intro, pp.489-90 "entangled bank"); Darwin autobiography (Malthus-1838 anecdote) at `https://www.gutenberg.org/cache/epub/2010/pg2010.txt`; Darwin+Wallace 1858 Linnean paper (real printed pp.45-62 baked into transcription, both authors in one fetch) at `https://darwin-online.org.uk/converted/published/1858_species_F350.html`; Mendel English trans. (section-numbered, cite `sec. N`) at `http://www.mendelweb.org/Mendel.plain.html` (esp.org PDF mirror times out); Watson & Crick 1953 at `https://www.nature.com/articles/171737a0` (paywalled, but the `meta-dc.description` tag verbatim-quotes "It has not escaped our notice..." with pp.737-38). Never guess PMC/DOI IDs (a guessed Avery-1944 ID resolved to an unrelated 1936 paper) — `web_search` for the exact URL first. For hard-paywalled papers (Kettlewell 1955, Dobzhansky page quotes, Zuckerkandl-Pauling 1965), verified secondary-quoted figures are safe with original bibliographic info — never fabricate unseen block quotes.

**Hitting word count:** count rendered text, not `.tex` bytes — strip `\footnote{...}` recursively, then `\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^}]*\})?`, split on whitespace (in `eval`/python). First full drafts undershoot (~5800 for a nominal 10k 8-section plan is typical) — budget a second pass of ~15-20 insertions (300-600 words each) via `edit PUT >N` across all sections, recounting after each batch.

**No-LaTeX-engine verification:** check brace-depth = 0 across the file and `\begin{env}`/`\end{env}` lists match when sorted. State explicitly this is mechanical, not a render check (`sudo`/package installs need an interactive password you won't have).

**Footnote-only format:** full citation (Author, *Title*, Publisher, Year, page) in `\footnote{}` at first use, shortened (`Author, *Short Title*, page`) after, no `\bibliography`/Works-Cited; plain `\footnote{}`, no `natbib`/`biblatex`, single self-contained `.tex` with no `.bib`.

_Migrated from: latex-essay-primary-source-research-without-subagents_
