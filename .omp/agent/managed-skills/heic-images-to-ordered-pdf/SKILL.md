---
name: heic-images-to-ordered-pdf
description: Use when combining multiple numbered .HEIC (or other) image files into a single ordered PDF on Linux — covers converting HEIC to JPG via ImageMagick+libheif then assembling with magick.
---

## Task
Combine N numbered image files (e.g. `1.HEIC`..`13.HEIC`) into one PDF, pages in numeric order.

## Tools
- `imagemagick` (`magick`) + `libheif` (provides HEIC decode support) — check with `pacman -Q imagemagick libheif`.
- Do NOT rely on `img2pdf` — often not installed; imagemagick alone suffices.

## Recipe
1. Convert each HEIC to JPG with zero-padded names so shell/glob ordering is numeric-safe:
   ```sh
   mkdir -p _pdf_tmp
   for i in $(seq 1 13); do
     magick "$i.HEIC" "_pdf_tmp/$(printf '%02d' $i).jpg"
   done
   ```
   (Padding avoids `1,10,11,...,2` lexicographic misordering.)
2. Assemble into a single PDF, listing files explicitly in the desired order (safest — don't rely on glob expansion order):
   ```sh
   magick _pdf_tmp/01.jpg _pdf_tmp/02.jpg ... _pdf_tmp/13.jpg "Output.pdf"
   ```
3. Clean up temp dir: `rm -rf _pdf_tmp`.

## Notes
- `magick` directly on `.HEIC` inputs also works for the final PDF step (skips JPG intermediate), but converting to JPG first is more reliable for large batches and keeps intermediate artifacts inspectable.
- Verify with `ls -la Output.pdf` (nonzero size, plausible for page count × ~2-3MB/photo).
