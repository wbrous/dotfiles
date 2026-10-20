---
name: procedural-svg-character-batch
description: "Use when generating many varied cartoon character/mascot SVGs (game cards, classroom art, poses/expressions); seeded generator, montage contact-sheet check, brow/id pitfalls."
---

# Batch procedural SVG characters

For requests like "10 SVGs of each type, each looks different, in a fighting stance". Worked example: RR&R rock cards (igneous / sedimentary / metamorphic fighters).

## Procedure
1. Put the generator in a file (e.g. `<out>/generate.py`), not just an `eval` cell. Fixes are then `edit` + rerun, and the user can regenerate. `inspect.getsource` can't read functions defined in `eval` (`OSError: could not get source code`). Regex-patching the SVG output also leaves the generator buggy, so a regenerate brings the bug back.
2. Use one `make(kind, i) -> str` with `random.Random(f"{kind}{i}")`. Each variant stays deterministic, so tweaking one doesn't reshuffle the rest.
3. Canvas: `viewBox="0 0 400 400"`. No background rect, so the art is transparent on any card colour.
4. Body: an irregular polygon from a jittered ellipse (7–12 points, radius ×0.82–1.08, angle jitter ±0.2 rad). Thick dark stroke, `stroke-linejoin="round"`. Limbs are quadratic `path`s with `stroke-linecap="round"`.
5. Paint order: ground shadow → legs/feet → arms → body → texture clipped to the body (`<clipPath>` of the body polygon) → face → fists last, so they overlap the body.
6. Variety:
   - Pick discrete features by index modulo so every option appears (`pose=i%3`, `mouth=i%4`).
   - Take continuous features (size, eye spacing, lean) from the seeded RNG.
   - 3 poses × 4 mouths alone reads as near-clones. If the user wants "each looks different", give every variant at least 2 discrete differences, using more poses (guard, jab, uppercut, kick), accessories (headband, bandage, eye patch, belt), body aspect and texture variants.
7. For educational content, make the category texture show the science. Rocks: igneous = crystal glints + lava cracks; sedimentary = horizontal strata + fossil shells; metamorphic = wavy foliation bands + garnet dots.
8. Check visually: run `montage <out>/*.svg -tile 10x3 -geometry 160x160+4+4 /tmp/sheet.png` (ImageMagick renders SVG), then `read` the PNG. Look at expressions, limb attachment, clipping and overlap.

## Pitfalls
- Angry brows: the inner end (toward the face centre) must be LOWER (larger y) than the outer end. If the inner end is higher, the face looks worried or sad. With the eye at `ex = cx + sx*sp` (`sx=-1` left, `+1` right), use `M{ex - sx*20},{ey-er+2} L{ex + sx*8},{ey-er-14}`.
- Give each file unique ids (`clip-{kind}-{i}`), not a shared `id="b"`. If several SVGs are inlined in one HTML page, `url(#b)` resolves to the first match, so every character is clipped to the first body shape.
- Thick black outlines disappear on dark card backgrounds. Suggest a light panel or glow behind the art, or add a light outer stroke.
