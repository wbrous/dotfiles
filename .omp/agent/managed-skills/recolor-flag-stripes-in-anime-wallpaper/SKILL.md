---
name: recolor-flag-stripes-in-anime-wallpaper
description: "Replace a flat-stripe flag (e.g. trans to bi) in a wallpaper/illustration, including matching stripes on a character's clothing, using numpy/scipy/cv2 in a venv."
---

## Setup
No PIL/numpy by default on this box: `python3 -m venv /tmp/bi && /tmp/bi/bin/pip install -q numpy pillow scipy opencv-python-headless`.
Do NOT issue a script-writing bash call and a `read` of its output image in the same parallel batch (read races the file write). Make crops in one call, read them in the next.

## Procedure that worked
1. Find stripe bounds: print colour changes down a column far from the character (x~100). Flag was 5x114px; bi is 2:1:2 (228/114/228). Bi hexes: magenta D60270, purple 9B4F96, blue 0038A8.
2. Background: per-row original colour = column x=100. core = pixels with dist<6 to that row colour; flood-label (scipy.ndimage.label) and keep components touching BOTH left and right edge strips (seed both sides, else right side is missed). Soft-blend only within 3px dilation. Do NOT use a pure colour-distance mask: it bleeds onto same-coloured clothing.
3. Clothing mask: classify by HSV hue (blue h170-225, pink h>330|<15, white low-S high-V), keep big components, close+fill holes for a silhouette, dilate 3px so the sweater's RIM HIGHLIGHT (pale, low-saturation, fails the hue test) is included, propagate band id to unclassified pixels by nearest classified pixel (<=10px). Assign each band component to a target colour by centroid y.
4. Clothing colour transfer = ONE scalar per pixel: s = Y/Y_band_base. s<=1: new = target*s. s>1: new = target + (255-target)*clip((s-1)/(smax-1)). Median-blur s lightly. Clamp smax>=1.35 or the near-white band (Y~249) amplifies jitter into white speckle on the purple stripe.
   FAILED alternatives (do not retry): Lab chroma scaling (goes grey/brown); per-channel three-anchor map (rim highlight turns yellow/mint because R,G saturate at 255 while B stays at base).
5. Character-edge fringe: DO NOT use hue/colour tests to separate skin from the old cream/white stripe (skin highlight is almost the same colour, so the mask paints purple into the skin and leaves a ragged edge). Instead build a GEOMETRIC silhouette: dark lineart (Y<110/120) in a window, morphological close (k~7-9 ellipse), fill holes, label, take component containing a known interior point. Inside the silhouette restore ORIGINAL pixels; in a <=4px ring outside it repaint with new_row_colour * a, a = projection of original onto old row colour (darkness alpha vs black).
   - Hand outline has gaps so whole-character fill_holes misses it; union a dedicated hand silhouette.
   - Exclude blue-hue (cuff/sleeve) pixels, dilated 2px, from the hand restore or the original light-blue cuff gets pasted back with a hard seam.
6. Final sweep: everything OUTSIDE the (character | hand) silhouette, inside the exact flag rows, that differs from the new row colour by >6 gets repainted as new_row*a. Clip to exact flag rows (padding above the flag draws a stray line).
7. Tiny enclosed pockets of old stripe (e.g. between sweater hem and shorts): box-scoped recolour with reddish test; 1px seams between old stripes are blends t*A+(1-t)*B, rebuild with new colours the same way.

## Pitfalls
- Global "pocket"/segment-to-black/hue rules eat skin highlights, nails and silver bracelets. Prefer silhouette geometry over colour tests; revert if edges get dotted.
- Verify with 4-8x NEAREST side-by-side crops (original | result) of: both shoulder tops, the sleeve outer edge, the hand, the cuff. User spotted flaws at that scale that a full-frame view hid.
- Stop chasing a few residual pixels (<10px at 2560x1440).
