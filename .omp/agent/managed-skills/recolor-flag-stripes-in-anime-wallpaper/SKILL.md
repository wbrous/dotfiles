---
name: recolor-flag-stripes-in-anime-wallpaper
description: "Replace a flat-stripe flag (e.g. trans to bi) in a wallpaper/illustration, including matching stripes on a character's clothing, using numpy/scipy/cv2 in a venv."
---

## Setup
No PIL/numpy by default on this box: `python3 -m venv /tmp/bi && /tmp/bi/bin/pip install -q numpy pillow scipy opencv-python-headless`.
Do NOT issue a script-writing bash call and a `read` of its output image in the same parallel batch (read races the file write).

## Procedure that worked
1. Find stripe bounds: print colour changes down a column far from the character (x~100). Flag was 5x114px; bi is 2:1:2 (228/114/228). Bi hexes: magenta D60270, purple 9B4F96, blue 0038A8.
2. Background: per-row original colour = column x=100. core = pixels with dist<6 to that row colour; flood-label (scipy.ndimage.label) and keep components touching BOTH left and right edge strips (seed both sides, else right side is missed). Soft-blend only within 3px dilation. Do NOT use a pure colour-distance mask: it bleeds onto same-coloured clothing.
3. Clothing: classify by HSV hue (blue h170-225, pink h>330|<15, white low-S high-V), keep big components, close+fill holes for a silhouette, then assign each band component to a target colour by centroid y. Recolour as target * (pixel luminance / band base luminance) to keep shading; leave dark lineart (Y<95) alone.
4. Fringe (old antialiasing halo): rebuild as new colour * alpha where alpha=Y/Y_old, using the nearest converted pixel's colour; clip to exact flag rows (padding above the flag draws a stray line).
5. Enclosed pockets of old stripe between hem and shorts: recolour with tight box + reddish test.

## Pitfalls
- Global "pocket"/segment-to-black rules eat skin highlights, nails and silver bracelets because pale skin resembles the white stripe. Exclude the hand box or keep fixes box-scoped; revert if edges get dotted.
- 1px seams between old stripes are blends t*A+(1-t)*B; rebuild with new colours the same way.
- Check results with 4-8x NEAREST zoom crops; stop chasing a few residual pixels.
