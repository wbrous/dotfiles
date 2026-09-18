---
name: ftc-official-field-manual-goal-geometry-extraction
description: "Use when a FIRST Tech Challenge (FTC) team repo references field elements, goals, scoring structures, or field coordinates (e.g. for auto pathing, teleop vision/targeting, or a programming lesson) and the exact positions/orientations aren't already hardcoded — especially when a repo's season name (e.g. \"Biobuzz\") matches a real current FTC game, meaning an official Competition Manual with authoritative field CAD/dimensions exists at ftc-resources.firstinspires.org rather than needing to guess from a screenshot or ask the user for one."
---

## Problem

A team repo (e.g. an FTC off-season/practice-named repo like "Biobuzz") references field goals/scoring elements in code (shoot poses, flower poses, PIDF "pointing robot towards goal" comments) but has no CAD or manual locally, and no field screenshot is available in the current session. Don't assume it's a custom/fictional practice game — check first.

## Key insight

FTC repo names often match the actual current-season official game name. Check `https://ftc-resources.firstinspires.org/ftc/game` — it lists "Current Game and Season Materials" with the live game name. If it matches the repo name, this is the **real official game**, and authoritative field data exists:

- `https://ftc-resources.firstinspires.org/ftc/game/manual-09` — ARENA section (field dims, TILE coordinate grid figures, structure dimensions)
- `https://ftc-resources.firstinspires.org/ftc/game/manual-10` — Game Details (scoring element staging figure, usually a precise top-down CAD render with the field 6x6 tile grid labeled — this is the single best source for goal x/y/facing)
- `https://ftc-resources.firstinspires.org/ftc/field/apriltag-art` — AprilTag production art/positions
- `https://ftc-resources.firstinspires.org/ftc/field/field-cad-step` — official STEP CAD (ground truth, ±1in tolerance per manual §9.1)
- `https://cad.onshape.com/documents/...` — Onshape field CAD (linked from `/ftc/field`)

## Extraction technique

1. `read` the manual URLs directly — the `read` tool converts PDF pages to markdown via markit, which handles prose fine but **loses figures/diagrams** (renders as `<!-- Page N -->` with no image data, sometimes "Text extraction incomplete").
2. To get diagram data: `curl` the PDF to a temp dir, then `pdftoppm -png -r 150 -f <page> -l <page> file.pdf out` to rasterize specific pages, then `read` the resulting PNG — the read tool will describe the image.
3. For precise pixel-to-inch conversion, use the read tool's `?q=...` query selector on the image, e.g. `image.png?q=This is a top-down CAD view of a 6x6 grid field (24in tiles). Give me x,y positions in inches of <features>.` — this invokes a vision-capable read pass. Treat its numeric output as an estimate (verify against exact numbers quoted in the manual's own prose, e.g. explicit "X in. apart" dimensions).
4. **Cross-validate against the repo's own existing pose data.** If auto/pathing code has example shoot poses with headings, compute the bearing (atan2) from each pose to your candidate goal-diagram positions and compare to the stored heading. A close match (within a couple degrees) confirms both which physical structure a pose targets AND which color/alliance owns which structure — this resolved a real ambiguity (which of two adjacent HIVE structures was "blue" vs "red" in the repo's coordinate frame, where a vision-model guess had them backwards).
5. Always cite the exact manual section/figure and note the manual's own stated tolerance (e.g. ±1in) in any deliverable — don't present figure-diagram-derived coordinates as laser-measured ground truth. Link the STEP/CAD file as the "if you need exact" fallback.

## Anti-pattern avoided

Don't tell the user "I can't see your screenshot, here are placeholder numbers, fill in a blank table yourself" when the real data is one `read` call away on a public official manual — check whether the game is a real current-season game FIRST before treating field geometry as unknowable.
