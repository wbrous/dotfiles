---
name: legal-pdf-version-diff-by-article
description: "Use when comparing two versions of an EU legislative proposal or other long legal PDF (published vs leaked/draft), or when read output truncates recitals; diff per article."
---

## Problem
The `read` tool on PDFs (markit conversion) truncates long lines at ~768 chars, so recitals and dense paragraphs get cut with "…". Large local PDFs are also skipped by auto-read.

## Procedure
1. For local PDFs use `pdftotext -layout file.pdf /tmp/x.txt` (poppler) and `read`/`grep` the text file. Full recitals survive, unlike with the markit conversion.
2. For URL versions, the `read` output is spilled to an `artifact://N` backing file; its real path is printed in the read result ("Backing file: ..."). Copy THAT path. Do not guess it with `ls -t` over the sessions directory (it matches dozens of unrelated dirs and fails).
3. Compare versions per article, not whole-file:
   - normalise: strip `<!-- Page -->`, `EN EN` footers, markdown `#`/`*`, collapse whitespace;
   - split on `Article N –`; keep the last occurrence per number (the explanatory memorandum also mentions articles);
   - print `difflib.SequenceMatcher` ratio per article, then a word-level diff for ratios < ~0.95.
   - Low ratios are usually list re-lettering and footnote placement from PDF conversion. Confirm by looking at the diff ops before claiming a substantive change. Article 43 will show a low ratio because the financial statement is appended.
4. Compare recitals the same way: split on `(N) ` inside the text between "Whereas:" and "HAVE ADOPTED"; compare counts and lengths.
5. Grep for scope words (operating system, open-source, non-commercial, private server, self-host) in recitals AND articles. Scope-defining recitals (11-13 in COM(2026) 681) often carry the caveats the articles lack.

## Reporting rules
- Say what was and wasn't verified (e.g. cross-referenced regulations like the DMA were not fetched).
- Distinguish recitals (interpretive) from operative articles.
- If a user claims a ban/obligation, check the text; do not confirm from memory.
