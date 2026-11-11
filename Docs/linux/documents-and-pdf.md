# Documents and PDFs on Linux

HEIC→PDF assembly, JS-rendered slide decks, and per-article legal PDF diffs.

## Combine numbered HEIC images into one ordered PDF

**Symptom:** N numbered images (`1.HEIC`..`13.HEIC`) need to become one PDF with numeric page order.

**Cause/notes:** `imagemagick` (`magick`) + `libheif` provide HEIC decode (`pacman -Q imagemagick libheif`). Don't rely on `img2pdf` — often not installed. `magick` directly on `.HEIC` also works for the final PDF step, but JPG-first is more reliable for large batches and keeps intermediates inspectable.

**Fix:**
```sh
mkdir -p _pdf_tmp
for i in $(seq 1 13); do
  magick "$i.HEIC" "_pdf_tmp/$(printf '%02d' $i).jpg"
done
# zero-padded names avoid 1,10,11,...,2 lexicographic misordering
magick _pdf_tmp/01.jpg _pdf_tmp/02.jpg ... _pdf_tmp/13.jpg "Output.pdf"
# list files explicitly in order — don't rely on glob expansion order
rm -rf _pdf_tmp
ls -la Output.pdf   # nonzero, plausible for page count x ~2-3MB/photo
```

_Migrated from: heic-images-to-ordered-pdf_

## Read JS-rendered slide decks (Slides / Canva / SharePoint)

**Symptom:** Reading a Google Slides / Canva / SharePoint presentation URL returns only og:title metadata or `<!-- image -->` placeholders — these viewers render slides to `<canvas>` with no DOM text to scrape.

**Fix order (cheapest first):**
1. **Google Slides pptx export** (works when the deck has real text boxes): read `https://docs.google.com/presentation/d/<ID>/export/pptx` directly — auto-converts to clean per-slide markdown. If every slide is only `<!-- image -->` with no text, the deck is canvas-rendered → fall back to screenshots.
2. **Canva / SharePoint / canvas-only Slides:** no text export exists; use a headless browser tab. Canva/SharePoint editors load a thumbnail sidebar (left strip, ~x=100 at 1024 wide): click each thumbnail and screenshot the main pane after each click (screenshot → temp path → read the path to view/OCR; don't bulk-dump base64 into eval output). Watch for stale-click artifacts — the first click sometimes doesn't register; verify via the highlighted thumbnail border in the screenshot, not trust in the click. Long decks (10+ slides): the sidebar scrolls — either wheel-scroll it between batches or click into the main canvas for focus then `PageDown`/`ArrowRight` + short sleep + screenshot in a loop.
3. **Google Slides `mobilepresent`** (pptx all-image): keyboard `ArrowRight` from the first slide only works if you first jump `Home` then press `ArrowRight` exactly `i` times for slide i with ~700ms sleep + screenshot — a single `ArrowRight` per iteration can jump to the last slide when the `#slide=id.p` fragment doesn't land on slide 1.

**Multi-deck reviews:** open all deck URLs as separate headless tabs in parallel first, then extract each (pptx attempt for Slides, screenshot-loop for Canva/SharePoint) in parallel where possible; read screenshots in batches of ~8–10.

_Migrated from: extract-jsrendered-slide-decks_

## Diff two versions of a long legal PDF per article

**Symptom:** Comparing published vs leaked/draft versions of an EU legislative proposal (or other long legal PDF); reader output truncates recitals (long lines cut at ~768 chars with "…") and large local PDFs are skipped.

**Fix:**
1. Local PDFs: `pdftotext -layout file.pdf /tmp/x.txt` (poppler), then read/grep the text — full recitals survive.
2. URL versions: reader output spills to an `artifact://N` backing file whose real path is printed in the read result — copy THAT path; don't guess with `ls -t` over the sessions dir.
3. Compare per article, not whole-file: normalise (strip `<!-- Page -->`, `EN EN` footers, markdown `#`/`*`, collapse whitespace); split on `Article N –`; keep the last occurrence per number (the explanatory memorandum also mentions articles); print `difflib.SequenceMatcher` ratio per article, word-level diff for ratios < ~0.95. Low ratios are usually list re-lettering and footnote placement from PDF conversion — check diff ops before claiming substance. Article 43 will show low ratio because the financial statement is appended.
4. Recitals: split on `(N) ` between "Whereas:" and "HAVE ADOPTED"; compare counts and lengths.
5. Grep scope words (operating system, open-source, non-commercial, private server, self-host) in recitals AND articles — scope-defining recitals (11–13 in COM(2026) 681) often carry caveats the articles lack.

**Reporting rules:** say what was and wasn't verified (e.g. cross-referenced regulations like the DMA were not fetched); distinguish recitals (interpretive) from operative articles; if a user claims a ban/obligation, check the text — don't confirm from memory.

_Migrated from: legal-pdf-version-diff-by-article_
