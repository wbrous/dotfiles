---
name: latex-newenvironment-boxed-note-brace-mismatch
description: "Use when writing a LaTeX \\newenvironment (e.g. a boxed/colored \"note\" callout) that wraps a \\colorbox or \\fbox around a minipage split across the begin-code and end-code arguments, and pdflatex fails with \"Missing } inserted\" pointing at the environment's \\end{...} usage — a colorbox/fbox brace opened in the begin-code cannot be closed in the end-code because \\begin{minipage}...\\end{minipage} must be balanced within a single one of the two argument groups, not spread across both."
---

## Symptom

```latex
\newenvironment{note}{\par\vspace{4pt}\noindent\colorbox{noteBg}{\begin{minipage}{\dimexpr\textwidth-2\fboxsep}\vspace{2pt}}}{\end{minipage}}\vspace{4pt}}
```

Compiling with `pdflatex` gives `! Missing } inserted.` pointing at a call site like `\end{note}`, even though the definition itself "looks" balanced at a glance.

## Root cause

`\colorbox{color}{<content>}` requires `<content>` to be a fully self-contained, brace-balanced group. Opening `\begin{minipage}` inside the begin-code argument and only calling the matching `\end{minipage}` inside the *end-code* argument splits one balanced construct across two separate `\newenvironment` argument groups — the `\colorbox{...}` brace closes before the minipage does, and TeX can't reconcile it. This is fundamentally broken, not a typo — no brace-counting fix rescues it.

## Fix

Don't try to split a colorbox+minipage across begin/end. For a simple callout box, prefer something that doesn't require prop matching across the split, e.g.:

```latex
\newenvironment{note}{\par\vspace{6pt}\noindent\begin{quote}\small\itshape}{\end{quote}\vspace{2pt}}
```

This is a `quote` environment (single balanced construct, `\begin`/`\end` naturally straddle the two argument slots because `\begin{quote}` and `\end{quote}` are designed to pair that way) rather than a colorbox/minipage combo that isn't.

If a colored background box is genuinely required, use a package built for cross-boundary environments (e.g. `mdframed` or `tcolorbox`'s own environment forms) instead of hand-rolling colorbox+minipage — those packages already solve the begin/end brace-splitting problem internally.

## General lesson

When authoring a `\newenvironment{name}{<begin-code>}{<end-code>}`, every brace-delimited macro argument opened in `<begin-code>` must also close in `<begin-code>` (or be closed by `<end-code>` only if the macro itself is explicitly designed to pair `\begin{x}`/`\end{x}` — i.e. it's itself a LaTeX environment, not a brace-argument macro like `\colorbox`, `\fbox`, or `\parbox`).
