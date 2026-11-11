---
name: flat-lowpoly-flag-wallpaper-python
description: "Generate 4K flat-shaded low-poly wallpaper (pride flag colors, hard edges, no blend) via Python Pillow+scipy Delaunay; skip hand-tracing a reference."
---

# Flat low-poly wallpaper from code

Use when asked to "recreate/make a low-poly wallpaper in 4K, hard lines, no blend", e.g. a pride-flag palette.

## Recipe (worked first try on design)
1. System python on Arch/Omarchy has no PIL/numpy. Use a venv: `uv venv /tmp/bi` (if it exists, `uv pip install --python /tmp/bi/bin/python pillow numpy scipy`). Run with `/tmp/bi/bin/python`.
2. Do NOT hand-trace a reference mesh (vertex lists + Delaunay diverged from the reference edges, cost many iterations). If user says fidelity doesn't matter, or even before, generate instead:
   - Jittered grid (~9x6 cells at 3840x2160, jitter ~0.38 of a cell; border points stay on the border so the frame tiles exactly).
   - `scipy.spatial.Delaunay` triangulation.
   - Each triangle: ONE flat color = flag ramp at centroid y, times (1 +- 0.06) random lightness. No gradients.
   - Flag ramp for bi: pink (214,2,112) to 0.30, purple (155,79,150) at 0.52, blue (0,56,168) from 0.76. Wide purple band looks better than a thin one.
   - Draw polygons dilated ~0.75px outward from centroid to avoid hairline gaps.
3. Verify: `identify` for size, count unique colors (should be ~triangle count, tens), view a downscaled preview.

## Gotchas
- NumPy 2.x: `np.cross` on 2D vectors raises; compute `ab[:,0]*ac[:,1]-ab[:,1]*ac[:,0]`.
- PIL `polygon` fill includes boundary pixels, so raster overlap counts on shared edges are meaningless; check tiling by summing triangle areas == W*H instead.
- Don't issue `read` of an image in the same parallel batch as the bash that creates it (races, "not found").
- Probe flatness on a facet interior, not an arbitrary patch (may straddle an edge).
