---
name: parallel-latex-study-guide-orchestration
description: "Build a large multi-unit study guide/problem set PDF from course PDFs via parallel per-unit author agents, independent reviewers, and a LaTeX master build."
---

## Recipe (worked for 976 Qs / 8 units / 141 pages)

1. **Survey**: `pdftotext -layout` each unit's PDFs (check for scanned/low-text files), list topics from review sheets / "test topics" handouts. Check LaTeX packages with `kpsewhich` (siunitx and mhchem were MISSING on Arch; use own `\q`, `\un`, `\sci`, `\chem` macros built with `\ensuremath` so they work in text AND math mode).
2. **Build contract before dispatch** in `guide/`: `preamble.tex` (macros `\Q` auto-numbering, `\A{k}{}`, `parts` list, `constbox`, `\unitchapter`), `unitwrap.tex` (standalone per-unit compile via `\def\unitnum{N}\input{unitwrap}`), `master.tex`, `audit.sh`, and `CONTRACT.md` (file format, count rule, ramp rule, self-check, short report format). Smoke-test the format with a sample unit first (this caught the `\mathrm` text-mode bug); delete the sample afterward. Patch the preamble by rewriting the whole file, not line-range edits.
3. **Phase 1**: one author agent per unit in a single `task` batch (budget per unit, e.g. 85-120, summing to ~880). Each writes only `unitN_questions.tex` / `unitN_answers.tex`; no gates except one self-compile into `/tmp/unitN`. Tell them `\Q{` must start at column 0 so `grep -c '^\\Q{'` counts.
4. **Audit myself** (never trust reports): counts, A numbers contiguous 1..N, section parity. Known failure: authors restart `\A` numbering per section. Fix mechanically with a regex renumber (safe only if per-section Q and A counts match).
5. **Phase 2**: one independent reviewer per unit that re-solves every problem with python3 BEFORE reading the key. Found real bugs (unbalanced equations, 10x atom counts, wrong keys, duplicate questions, near-verbatim copies of course problems, out-of-scope content like elements not on the course activity series). Very fast "0 defects" reports (<30s) are suspicious; spot-check transcripts via `history://<id>`.
6. **Check difficulty yourself**: measure avg question length first-2 vs last-3 per section, % multipart, read last questions of weakest units. First pass was too easy (one-step, ~0% multipart). Fix: phase 3 appends a 12-problem "Challenge Problems" section per unit (>=3 steps, >=7 multipart, traps), keys continue numbering.
7. **Phase 4**: reviewers for ONLY the new challenge sections. Rule: traps must live in the answer key ("Trap:"), never be announced in the question text ("Trap:", "Hint:", "you cannot use..."). Grep for leaked hints afterwards and classify by position (hints in warm-ups are fine).
8. **Master build**: `pdflatex master.tex` twice; add `\sloppy`, `\emergencystretch=3em`, `\relpenalty=0`, `\binoppenalty=0` to kill overfull boxes in long inline math; grep log for overfull >10pt, `pdftotext | grep '\\\\[a-z]'` for leaked LaTeX; render sample pages with `pdftoppm` and view them. Copy final PDF to project root.

Gotchas: `wait` can return "skipped due to queued completion" - just retry. `edit` PUT line ranges can clobber wrong lines when tags are stale; re-read first.
