# LaTeX Study Guides and Proof Packets

Building large multi-unit study guides and geometry proof packets in pure `pdflatex` + `tikz`.

## Parallel study-guide orchestration (recipe for ~976 Qs / 8 units / 141 pages)

**Scope:** Multi-unit problem-set PDF built from course PDFs via parallel per-unit authors, independent reviewers, and a master build.

1. **Survey:** `pdftotext -layout` each unit's PDFs (flag scanned/low-text files); list topics from review/"test topics" handouts. Check packages with `kpsewhich` — `siunitx` and `mhchem` were MISSING on Arch; use own `\q`, `\un`, `\sci`, `\chem` macros built with `\ensuremath` so they work in text AND math mode.
2. **Contract first** in `guide/`: `preamble.tex` (macros `\Q` auto-numbering, `\A{k}{}`, `parts` list, `constbox`, `\unitchapter`), `unitwrap.tex` (standalone per-unit compile via `\def\unitnum{N}\input{unitwrap}`), `master.tex`, `audit.sh`, `CONTRACT.md` (format, count rule, ramp rule, self-check, short report format). Smoke-test with a sample unit first (caught a `\mathrm` text-mode bug); delete the sample after. Patch the preamble by rewriting the whole file, never line-range edits.
3. **Phase 1:** one author agent per unit in a single batch (budget per unit, e.g. 85-120). Each writes only `unitN_questions.tex` / `unitN_answers.tex`; `\Q{` must start at column 0 so `grep -c '^\\Q{'` counts. No gates except one self-compile into `/tmp/unitN`.
4. **Audit yourself** (never trust reports): counts, A-numbers contiguous 1..N, section parity. Known failure: authors restart `\A` numbering per section — fix mechanically with regex renumber only if per-section Q/A counts match.
5. **Phase 2:** one independent reviewer per unit that re-solves every problem with python3 BEFORE reading the key. Real bugs found: unbalanced equations, 10x atom counts, wrong keys, duplicates, near-verbatim course-problem copies, out-of-scope content. Sub-30s "0 defects" reports are suspicious — spot-check transcripts.
6. **Difficulty check yourself:** avg question length first-2 vs last-3 per section, % multipart, read last questions of weakest units. First pass was too easy (~0% multipart, one-step). Fix: phase 3 appends a 12-problem "Challenge Problems" section per unit (≥3 steps, ≥7 multipart, traps); keys continue numbering.
7. **Phase 4:** reviewers for ONLY the new challenge sections. Rule: traps live in the answer key ("Trap:"), never announced in the question ("Trap:", "Hint:", "you cannot use..."). Grep for leaked hints after, classify by position (warm-up hints fine).
8. **Master build:** `pdflatex master.tex` twice; add `\sloppy`, `\emergencystretch=3em`, `\relpenalty=0`, `\binoppenalty=0` to kill overfull boxes in long inline math; grep log for overfull >10pt, `pdftotext | grep '\\\\[a-z]'` for leaked LaTeX; render samples with `pdftoppm` and view. Copy final PDF to project root.

Orchestration gotchas: `wait` can return "skipped due to queued completion" — just retry. `edit` PUT with stale tags can clobber wrong lines — re-read first.

_Migrated from: parallel-latex-study-guide-orchestration_

## Geometry proof packets: exact-N-step proofs, diagrams, blank tables

**Setup:** Pure `pdflatex` + `tikz`. Packages: `geometry`, `tikz`, `amsmath,amssymb`, `xcolor` (answer key), `titlesec` (custom headers).

**Vocabulary constraint:** A numbered range ("Postulates 1-10", "Theorems 1-11") is a hard constraint — a sheet may list MORE (e.g. CPCTC/SSS/etc. at 11-17) that are out of scope. Re-check before designing.

**Designing exact-N-step two-column proofs:** one fact per statement line, one reason per line — no stacking, no hidden double justifications. To hit an exact count (e.g. 15), use "mirror-and-combine": two symmetric branches (~5-7 steps each to a measure/congruence fact), joined by one Transitive/CCT/CongruentSupplements/RAT step. Extend geometric scope (second given, numeric follow-up, second corresponding-parts pair) instead of padding with unused steps. **Hand-verify top-to-bottom against the printed Given text** — two real failure modes: (1) a `Given:` line silently missing a needed fact (midpoint clause, second congruence pair) after hand-transcription into LaTeX; (2) a proof shorter than required once written plainly (Common-Segment-style derivations collapse to ~9 steps) — write out the full statement list and count, don't trust design notes. Also check "different" proofs sharing a base derivation aren't accidental duplicates.

**TikZ patterns:** ray fan `\draw[thick,-latex] (O) -- (angle:len)` at spaced angles (150,110,70,30,0) + sector labels `\node at (midangle:0.7)`; X-line crossing with two `latex-latex` lines at skewed angles (200°↔20°, 110°↔-70°) so perpendicularity isn't implied — reuse via `scope[xshift=...]`; right-angle corner L-shape + `\draw` right-angle box + interior ray; collinear points `\foreach \x/\lab in {...}{\fill...}` with `\cong` tick labels below gaps; triangle cevian via three `\coordinate`s + `cycle` + internal segment.

**Blank-table macro:** plain `tabular` in a `\newcommand{\blanktable}`, 15 rows with `\\[0.48cm]` spacing — never `longtable` inside a reused macro (its internal state breaks on 2nd/3rd invocation: "Extra alignment tab / Misplaced \noalign / \omit / Undefined control sequence"). Fit diagram + Given/Prove + table on one page: `\\[0.48cm]` rows (`sed -i 's/\[0\.68cm\]/[0.48cm]/g'`) and `\smallskip` before the table (`sed -i 's/^\\bigskip$/\\smallskip/'`) — a 15-row table at ~23cm content fits ~23.4cm usable height at 0.9in letter margins.

**Macro pitfalls:** re-read before line-numbered inserts (stale numbers land content before `\begin{document}` or before the macro it needs); don't `\newpage` on both sides of a short section-intro (strands heading + paragraph on a blank page); changing a macro's arg count requires updating every call site in the same pass (stale 2-arg call against 3-arg `\newcommand` silently eats the next brace group).

_Migrated from: latex-geometry-proof-packet-generator_

## Answer-key generation (parallel document)

**Scope:** Companion answer-key PDF for drills and proof tables; doubles as a correctness pass on the student document — backport fixes.

Build a second `.tex` file (student PDF stays clean); reuse the exact same TikZ code verbatim (copy-paste). Fill-in drills: `\cqkey{n}{given}{conclusion}{reason}` with reason in `\textcolor{red}{\bfseries ...}` (pre-filled conclusions stay black). Proof tables: `\krow{n}{statement}{reason}` (`#1. & \color{red}#2 & \color{red}#3 \\ \hline`) inside shared `\keytablehead`/`\keytablefoot`; structure black, answers red.

_Migrated from: latex-geometry-proof-packet-generator_
