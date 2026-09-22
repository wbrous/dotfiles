---
name: latex-geometry-proof-packet-generator
description: "Use when building a LaTeX/TikZ geometry review packet with \"Given → Conclusion/Reason\" drill diagrams and/or N-step two-column proof tables (blank Statement/Reason grids for a student to fill in) — covers designing valid fixed-step-count proofs from a restricted vocabulary list (Definitions/Properties/Postulates/Theorems), TikZ patterns for common diagrams (ray fans, X-line crossings, collinear segment points, triangles with cevians), the reusable \\blanktable-macro pattern for repeated blank Statement/Reason tables, and pitfalls that break compilation or layout: a longtable-based blank-table macro throws \"Undefined control sequence \\blanktable\" / \"Misplaced \\noalign\" on its second use (switch to a plain tabular macro instead), a redundant \\newpage immediately before a \\section (when short section-intro text is followed by another \\newpage before the first subsection) produces a wasted blank page, changing a macro's argument count (e.g. \\cq from 2-arg to 3-arg to add a pre-filled answer) requires updating every call site or compilation silently corrupts, and getting a diagram+Given/Prove+15-row table to fit on one shared page requires trimming per-row height (~0.68cm to ~0.48cm) and skip size (\\bigskip to \\smallskip) rather than just shrinking font."
---

## Context

Building a printable geometry review packet (pdflatex + TikZ, no python needed) with two parts:
- **Conclusions section**: several diagrams, each followed by 5-10 "Given: X. Conclusion: Y. Reason: ____" drill items (student only fills Reason once the packet is "answer-keyed").
- **Proofs section**: N diagrammed two-column proofs, each provable in an exact step count (e.g. 15) using only a restricted vocabulary list (Definitions/Properties/Postulates/Theorems ranges the user specifies — do NOT use postulates/theorems outside the requested range, e.g. exclude SSS/ASA/SAS/CPCTC/parallel-line postulates if the user's vocabulary sheet caps at Postulates 1-10).

## Designing exact-step-count proofs

For each proof, hand-derive the full statement/reason chain BEFORE writing the LaTeX (don't just wing it in the diagram). Reliable technique to hit an exact step count (e.g. 15) without stacking (no combining two givens into one statement line, no reusing one reason to justify two different statements):
1. Pick a base theorem relationship (e.g. angle bisector + given congruence, or two right-angle branches).
2. Fully expand any theorem you'd normally cite in one step into its own definition-level derivation (e.g. expand "Common Segment Theorem" into its SAP+Addition-Property proof rather than citing CST as a single line) — this both adds legitimate steps and demonstrates the underlying reasoning.
3. Mirror the same derivation on a second, structurally parallel branch (two right angles, two bisected angles, two intersecting-line pairs) and combine the two branches via Transitive/Substitution/CCT/CongruentSupplements at the end.
4. Count the final list; add or remove a definitional restatement step (e.g. converting a final congruence to its measure-equality via Def ≅) to land exactly on the target count.
5. Only print the diagram + Given + Prove (+ blank table) in the PDF — keep your derived Statement/Reason list as your own verification, don't leak it into the packet unless an answer key is requested.

## TikZ diagram patterns (robust, reusable)

- **Ray fan from a point**: `\draw[thick,-latex] (O) -- (150:2.3) node[above]{$A$};` repeated at decreasing angles; label angle regions with `\node at (130:1.0) {\footnotesize 1};`.
- **Two lines crossing (X)**: draw as a *skewed* X (e.g. endpoints at 200°/20° and 110°/-70°), not a visually-perpendicular +, unless perpendicularity is actually given — don't visually imply un-given right angles.
- **Two separate X-crossings side by side**: wrap each in its own `\begin{scope}[xshift=...]...\end{scope}`.
- **Collinear points on a segment**: `\draw[thick] (0,0) -- (8,0); \foreach \x/\lab in {0/A,2.5/B,...}{\fill (\x,0) circle (1.5pt); \node[above] at (\x,0.15) {$\lab$};}`.
- **Triangle with a cevian**: three `\coordinate`s + `\draw[thick] (A)--(B)--(C)--cycle;` plus one more `\draw` for the cevian.
- Never visually assume from a diagram what the vocabulary sheet's "may NOT be assumed" list forbids (typically: congruence, measures, relative sizes, midpoint/bisector, perpendicularity/right angles). Only show these when they are actually Given. Things commonly allowed to assume purely from the picture: straightness, betweenness/collinearity, intersection, relative location (interior/exterior), adjacency, linear pair, vertical angles (check the user's own vocabulary sheet for what it explicitly permits — some sheets annotate extra assumable items).

## Reusable blank-table macro — use plain `tabular`, NOT `longtable`

A macro like this, invoked once per proof, is far more reliable than `longtable` when called many times in one document:

```latex
\newcommand{\blanktable}{%
\begin{center}
\renewcommand{\arraystretch}{1}
\begin{tabular}{|c|p{6.5cm}|p{6.5cm}|}
\hline
\textbf{\#} & \textbf{Statements} & \textbf{Reasons} \\
\hline\hline
1. & & \\[0.48cm]\hline
2. & & \\[0.48cm]\hline
...
15. & & \\[0.48cm]\hline
\end{tabular}
\end{center}}
```

**Pitfall confirmed by direct testing**: defining this same table via `\usepackage{longtable}` + `\begin{longtable}...\end{longtable}` inside the macro compiles fine for the *first* invocation, then throws `! Undefined control sequence. \blanktable` / `! Misplaced \noalign` / `! Extra alignment tab has been changed to \cr` on the second and later invocations. Cause not fully diagnosed, but switching to a plain `tabular` (as above) fixed it immediately with zero errors across 10+ reuses. Prefer plain `tabular` inside a repeatable macro; only reach for `longtable` if a single table genuinely needs to span multiple pages (and even then, test with 2+ real invocations before trusting it).

## Fitting diagram + Given/Prove + table on ONE shared page

Default spacing (row skip `\\[0.68cm]`, `\bigskip` before the table) is usually too tall combined with a `\subsection*` heading + diagram + 1-3 lines of Given/Prove text — LaTeX pushes the whole table to the next page, leaving the diagram alone on the prior page. Fix by tuning *vertical space*, not font size:
- Reduce each table row's trailing skip (e.g. `\\[0.68cm]` → `\\[0.48cm]` for a 15-row table with `p{6.5cm}` columns).
- Change `\bigskip` before the table to `\smallskip`.
- Re-render 2-3 representative proof pages (via `pdftoppm -png -r 100 -f N -l N file.pdf out`) and visually confirm the last table row and the diagram are on the same page before declaring done — page-count text extraction alone won't catch this, you must look at an actual rendered page image.

## Blank page from a redundant `\newpage`

If a section's intro paragraph is short and followed immediately by `\newpage` before the first subsection, AND you already had a `\newpage` right before the `\section{...}` line itself, you get one genuinely wasted blank page between them (the short intro text doesn't fill the first forced page, and TeX still needs the second forced break). Fix: keep only ONE `\newpage` at that boundary — right before the first subsequent subsection/diagram/proof, not also before the `\section` command.

## Changing a macro's answer-key behavior (e.g. adding pre-filled conclusions)

When retrofitting a "fill-in-the-blank" macro (e.g. `\cq{n}{given}` producing a blank underline) into an "answer-key" macro (e.g. `\cq{n}{given}{conclusion}` printing the derived conclusion and leaving only Reason blank), you MUST update every call site to the new arity in the same pass — a stale 2-arg call against a 3-arg `\newcommand` does not error cleanly; it silently misparses trailing document text as the missing third argument and corrupts output. Locate all call sites first via `grep` for the macro name, then batch-edit each block (grouped by diagram/section) rather than doing them one at a time — multiple `PUT` operations can be issued in a single edit call against different line ranges of the same file.

## Verification workflow

1. `pdflatex -interaction=nonstopmode file.tex 2>&1 | grep -iE "error|undefined|misplaced|! "` — run twice (LaTeX needs two passes for some counters/refs) and confirm zero matches.
2. `pdftoppm -png -r 100 -f N -l N file.pdf out` to rasterize specific pages, then view them directly — text-extraction-based PDF reads will describe structure but won't reveal genuine layout bugs (page overflow, blank pages, wrong diagram proportions).
3. Spot-check first page, a middle diagram/proof, and the last page — pagination bugs often only surface on the boundary pages.
