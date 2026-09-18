---
name: latex-beginner-tutorial-single-page-code-blocks
description: "Use when writing a LaTeX PDF tutorial/lesson for a beginner audience (e.g. \"make this as easy to follow as a YouTube tutorial\", \"I have 0 clue what I'm doing\") that includes source-code listings — covers structuring the doc as What's-broken/What-we're-building/full-code/line-by-line-explanation per step, teaching general language structure (class/method/field, public/private/static) via plain-English analogies instead of syntax rules when asked to \"not teach syntax\", using the needspace package (\\needspace{N\\baselineskip} before each lstlisting) to force a page break rather than let a code block split across pages, a \\filebox{realpath}{examples/path} banner macro to label which real repo file a block belongs in and which file in an accompanying examples/ folder mirrors it, and placing that examples/ folder's reference source files outside the actual build's source root (e.g. outside TeamCode/src/main/java in an FTC repo) so they can never accidentally get compiled into the app while still being real, complete, diffable files cited from the PDF."
---

## When this applies

User asks for a tutorial/lesson PDF (LaTeX) aimed at someone with zero background, often phrased like "I have 0 clue what I'm doing", "make it as easy to follow as a YT tutorial", "don't teach syntax, teach [framework] and general [language] structure", and wants code blocks that don't split across pages plus a companion `examples/` folder they can reference.

## Document structure that works

Per step: **What's broken/missing → What we're building (plain-English plan) → one full code block → "reading this block, piece by piece" prose walkthrough → how to prove it worked**. This repeats identically for every step so the reader builds a reading habit.

Open with a short **Step 0 primer** that teaches the *shape* of the language/framework via analogies, not grammar:
- class = "a labeled box of related stuff"
- field = "a labeled sticky note the box remembers"
- method = "a named action: give it inputs, it does work, maybe hands back a result"
- `public`/`private`/`static` = "who's allowed to touch it" / "belongs to the class itself, not one instance"
- Framework-specific core object (e.g. PedroPathing's `Follower`) explained as a real-world analogy ("GPS receiver plus steering wheel in one object").

Explicitly do NOT explain semicolons, braces, statement termination, etc. when the user says "don't teach syntax" — that instruction means skip grammar mechanics, not skip explaining `public static` semantics (those ARE structure, not syntax, and the user usually wants exactly that).

## Never let a code block split across pages

`\usepackage{needspace}`, then before every `lstlisting`:
```latex
\needspace{N\baselineskip}
\begin{lstlisting}
...
\end{lstlisting}
```
Pick `N` = (line count of the block + ~4-6 for headroom). `needspace` checks remaining vertical space on the current page at that point and inserts a page break if insufficient, so the whole block lands together on a fresh page. This is far simpler and more reliable than trying to use floats or `samepage` for verbatim/listings content. Verify visually: render each PDF page to an image (`pdftoppm -png -r 150 file.pdf pageprefix`) and read a sample of pages back to confirm no listing frame is cut off at a page boundary and continues on the next.

Keep individual code blocks under ~50-55 lines at `footnotesize` with line numbers — that's roughly what fits on one US-letter page with 1in margins alongside a heading and a couple sentences of lead-in text. If a single real file is longer than that, split its presentation across multiple steps/blocks (e.g. "add this field", "add this method", "wire it into loop()") rather than dumping the whole file as one giant listing that can't possibly fit one page.

## The `\filebox` banner + examples/ folder pattern

Macro:
```latex
\newcommand{\filebox}[2]{%
  \par\vspace{4pt}\noindent\colorbox{fileBg}{\parbox{\dimexpr\textwidth-2\fboxsep}{%
    \small\textbf{File:} \texttt{#1} \hfill \textbf{Full reference copy:} \texttt{examples/#2}%
  }}\vspace{-2pt}
}
```
Call it right before each code block: `\filebox{pedro/Constants.java}{pedro/Constants.java}`. This tells the reader exactly which real repo file they're editing and which mirror file in the `examples/` folder they can diff against if something doesn't match.

Build the `examples/` folder as real, complete files (not fragments) that exactly match the PDF's final wired-up state. Header-comment each one: "REFERENCE COPY — see doc/lessons/<pdf>.pdf, Step N. Not wired into the build." Critically, place this folder **outside the actual build's source root** (e.g. `doc/lessons/examples/` instead of anywhere under `TeamCode/src/main/java/` in an Android/FTC Gradle project) so the reference files can never accidentally get picked up by the compiler, get their package-private/public symbols collide with the real files, or otherwise pollute the real build — while still being genuine, complete, syntactically real source the student can open side-by-side with their own work.

## Grounding code content in real data

If the tutorial's example values (e.g. field goal coordinates) are drawn from an external authoritative source (official game manual, CAD, spec doc), cite that source directly in the tutorial prose near the relevant code block, and note the source's own stated tolerance/caveat rather than presenting the numbers as exact truth. Don't silently swap unsourced placeholder numbers for sourced ones without flagging the change and citing where they came from — the reader needs to know which parts of the document are load-bearing facts vs. illustrative examples.
