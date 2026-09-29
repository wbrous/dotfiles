---
description: "Use when building a LaTeX/TikZ geometry review packet with \"Given → Conclusion/Reason\" drill diagrams and/or N-step two-column proof tables (blank or filled-in answer-key versions) — covers designing valid fixed-step-count proofs from a restricted vocabulary list (Definitions/Properties/Postulates/Theorems), TikZ patterns for common diagrams (ray fans, X-line crossings, collinear segment points, triangles with cevians, perpendicular-corner pairs), the reusable blank-table macro pattern, generating a companion answer-key PDF with \\textcolor{red} answers via a parallel \\cqkey/\\krow macro set reusing the same TikZ diagrams, and pitfalls that break compilation, layout, or logical validity."
---

## Setup
Pure `pdflatex` + `tikz` — no python/venv needed for this class of document. Packages: `geometry`, `tikz`, `amsmath,amssymb`, `xcolor` (for answer key), `titlesec` (for custom `\section`/`\subsection*` headers).

## Restricting to an approved vocabulary list
If the user gives numbered Definitions/Properties/Postulates/Theorems ranges (e.g. "Postulates 1-10", "Theorems 1-11"), treat that range as a hard constraint on which reasons a proof may cite. A postulates sheet often lists MORE items than the assigned range (e.g. CPCTC/SSS/ASA/SAS/parallel-postulate stuff at postulates 11-17) — those are out of scope even though they're on the same reference sheet. Re-check the range before designing proofs; using an out-of-range theorem invalidates the proof for the assignment.

## Designing exact-N-step two-column proofs
- "No stacking" means: one fact per statement line, one reason per line — never combine two givens into one statement or cite "same reason, two lines" in a way that hides two separate justifications.
- A reliable way to hit an exact step count (e.g. 15) is the "mirror-and-combine" pattern: build two structurally symmetric branches (e.g. two independent right-angle/complementary/supplementary setups) that each take ~5-7 steps to reach a measure or congruence fact, then join them with one Transitive/CCT/CongruentSupplements/RAT step at the end. Padding with genuinely unused steps (facts nobody needs later) is bad practice — instead extend the geometric scope (add a second given relation, a numeric follow-up computation, a second corresponding-parts pair) so every step is load-bearing.
- **Before finalizing a proof, hand-verify it top-to-bottom against the printed Given text** — not just against your notes/plan. Two failure modes bit this project:
  1. A `Given:` line silently missing a fact the derivation needs (e.g. "M is the midpoint of AB" needed for a Midpoint Theorem step, or a second segment-congruence pair needed to force two sums equal) — this happens easily when hand-transcribing a designed proof into LaTeX text and dropping a clause.
  2. A proof that's actually shorter than the required step count once written plainly (e.g. Common-Segment-Theorem-style derivations collapse to ~9 steps) — catch this by explicitly writing out the full statement list and counting, don't just trust the original design notes.
- When two "different" proofs end up using the same base derivation (e.g. two segment proofs both starting from the same AB≅DE/BC≅CD setup), verify their `Given`/`Prove` text actually diverges enough that they're not accidental duplicates with different bugs.

## TikZ diagram patterns that work well
- Ray fan from a point: `\draw[thick,-latex] (O) -- (angle:len) node[above]{$Label$};` at evenly spaced angles (e.g. 150,110,70,30,0) draws a clean multi-ray angle diagram; small angle-sector labels via `\node at (midangle:0.7) {\footnotesize N};`.
- X-line crossing: two `latex-latex` lines through the origin at skewed angles (e.g. 200°↔20° and 110°↔-70°) avoids visually implying perpendicularity when that's not given; reuse this exact pattern for two side-by-side crossings via `\begin{scope}[xshift=...cm]`.
- Right-angle corner with interior ray: an L-shaped corner (`\draw[thick] (-1.6,0)--(1.6,0); \draw[thick,-latex](0,0)--(0,1.9);`) plus a small right-angle box `\draw[thick](0,0.28)--(0.28,0.28)--(0.28,0);` and one more ray for the interior point.
- Collinear points on a segment: `\foreach \x/\lab in {0/A,1.6/B,...}{\fill (\x,0) circle(1.4pt); \node[above=2pt] at (\x,0){$\lab$};}`; add `\cong` tick-mark labels below specific gaps with `\node[below] at (midx,-0.35){\footnotesize $\cong$};` when a given congruence needs visual reinforcement.
- Triangle with a cevian: three `\coordinate`s plus `\draw[thick] (A)--(B)--(C)--cycle;` and one internal segment from a vertex to a point on the opposite side.

## Blank-table macro (student version)
Define once, call per proof — avoids retyping 15 rows:
```
\newcommand{\blanktable}{%
\begin{center}\renewcommand{\arraystretch}{1}
\begin{tabular}{|c|p{6.5cm}|p{6.5cm}|}
\hline\textbf{\#} & \textbf{Statements} & \textbf{Reasons} \\ \hline\hline
1. & & \\[0.48cm]\hline
2. & & \\[0.48cm]\hline
... (through 15.)
\end{tabular}\end{center}}
```
**Use plain `tabular`, not `longtable`, for a reusable macro invoked many times** — `longtable`'s internal state does not survive being wrapped in a `\newcommand` and re-invoked repeatedly; it throws "Extra alignment tab / Misplaced \noalign / Misplaced \omit / Undefined control sequence" errors starting on the 2nd or 3rd call even though the 1st call compiles fine. A plain `tabular` has no such state and works for unlimited reuse.

## Fitting diagram + Given/Prove + table on one page
With `\\[0.68cm]` row spacing and `\bigskip` before the table, a 15-row table plus a modest diagram plus 2 lines of Given/Prove text can just barely overflow onto a second page (~23cm content vs ~23.4cm usable height at 0.9in margins on letter). Fix: shrink row spacing to `\\[0.48cm]` (`sed -i 's/\[0\.68cm\]/[0.48cm]/g'`) and change `\bigskip`→`\smallskip` before the table (`sed -i 's/^\\bigskip$/\\smallskip/'`). This reliably keeps every proof self-contained on one page without touching diagram scale.

## Common macro/pagination pitfalls
- **Insertion point drift**: when using an edit tool's line-numbered `PUT >N` to append content, always re-read the file immediately beforehand to get current line numbers — content inserted "after line N" from a stale line count can land *before* `\begin{document}` or before a macro it depends on (e.g. a `\cq{...}` call landing before `\newcommand{\cq}` is defined), causing silent structural breakage that only shows up as garbled rendering, not a compile error.
- **Double `\newpage`**: an explicit `\newpage` right before a `\section{...}` heading, combined with another explicit `\newpage` right after its short intro paragraph and before the next content block, produces a genuinely wasted blank page (the section heading + 1 paragraph doesn't fill a page, so it gets stranded alone between two forced breaks). Only put `\newpage` on one side of a short section-intro, not both.
- **Changing a macro's arg count** (e.g. `\cq{n}{given}` → `\cq{n}{given}{conclusion}`) requires updating every call site in the same edit pass — a stale 2-arg call against a 3-arg `\newcommand` doesn't error cleanly, it just consumes the next brace-group in the document as the missing argument, corrupting the following content.

## Answer-key generation (parallel document)
Build a second `.tex` file (e.g. `..._answerkey.tex`) rather than appending an answer section to the student file, so the student PDF stays clean. Reuse the *exact same* TikZ diagram code verbatim (copy-paste, don't regenerate). Pattern:
- For fill-in-the-blank drill items: `\cqkey{n}{given}{conclusion}{reason}` where `reason` is wrapped `\textcolor{red}{\bfseries ...}` (conclusion can stay black if it was already pre-filled in the student version — only the genuinely blank field needs to be red).
- For proof tables: don't reuse the blank-table macro; use a `\krow{n}{statement}{reason}` macro (`#1. & \color{red}#2 & \color{red}#3 \\ \hline`) called once per row inside a shared `\keytablehead`/`\keytablefoot` pair, so every row's actual answer content is red while table structure/borders stay black.
- Building the answer key is also the natural point to catch proof-design bugs (see "hand-verify" above) since it forces writing out every step explicitly — treat answer-key authoring as a correctness pass on the student document too, and backport any fixes.
