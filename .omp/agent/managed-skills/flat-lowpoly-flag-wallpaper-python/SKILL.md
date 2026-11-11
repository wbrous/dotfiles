---
name: flat-lowpoly-flag-wallpaper-python
description: "Generate 4K flat-shaded low-poly wallpaper (pride flag colors, hard edges, no blend) via Python Pillow+scipy Delaunay; also regenerate it on each Omarchy theme select via a theme-set hook. Skip hand-tracing a reference."
---

# Flat low-poly wallpaper from code

Use when asked to "recreate/make a low-poly wallpaper in 4K, hard lines, no blend", e.g. a pride-flag palette, or to "regenerate the wallpaper each time I pick theme X" on Omarchy.

## Recipe (worked first try on design)
1. System python on Arch/Omarchy has no PIL/numpy. Use a venv: `uv venv /tmp/bi` (if it exists, `uv pip install --python /tmp/bi/bin/python pillow numpy scipy`). Run with `/tmp/bi/bin/python`. For anything that must survive reboot (hooks!), use a durable venv, e.g. `~/.local/share/<name>/.venv`, never /tmp.
2. Do NOT hand-trace a reference mesh (vertex lists + Delaunay diverged from the reference edges, cost many iterations). If user says fidelity doesn't matter, or even before, generate instead:
   - Jittered grid (~9x6 cells at 3840x2160, jitter ~0.38 of a cell; border points stay on the border so the frame tiles exactly).
   - `scipy.spatial.Delaunay` triangulation.
   - Each triangle: ONE flat color = flag ramp at centroid y, times (1 +- 0.06) random lightness. No gradients.
   - Flag ramp for bi: pink (214,2,112) to 0.30, purple (155,79,150) at 0.52, blue (0,56,168) from 0.76. Wide purple band looks better than a thin one.
   - Draw polygons dilated ~0.75px outward from centroid to avoid hairline gaps.
3. Verify: `identify` for size, count unique colors (should be ~triangle count, tens), view a downscaled preview.
4. "A little different each time": derive grid size/jitter/band edges from the seed within tight bounds (8-10 cols, 5-6 rows, jitter .33-.42, bands +-.03), default seed = `secrets.randbits(31)`, `--seed N` for reproducibility. Write PNG to a temp file then `os.replace` (atomic).

## Omarchy: regenerate on theme select
- Omarchy runs `~/.config/omarchy/hooks/theme-set.d/*` after every theme change with the slug in `$1` (e.g. `pride`). Hook = no-op unless `$1` matches.
- Output into `~/.config/omarchy/backgrounds/<slug>/` (picked up automatically, merged with the theme's own `backgrounds/`). NEVER overwrite files inside `~/.config/omarchy/themes/<slug>/` (Aether-managed themes own them).
- Hook then calls `omarchy theme bg set <file>` (the hook fires AFTER the stock wallpaper was applied, so it crossfades to the new one).
- Use a NEW filename each time (`generated-$(date +%s%N).png`), never rewrite the file currently on screen; prune old ones but keep the new file and the one that was showing (`readlink -f ~/.local/state/omarchy/current/background`).
- `flock -n` on a lock file so rapid theme flipping can't stack renders.
- Test: `OMARCHY_THEME_WAIT=1 omarchy theme set Nord; ... set Pride` (switching to the already-current theme only cycles backgrounds, so switch away first). `OMARCHY_THEME_WAIT=1` makes the call wait for hooks.

## Gotchas
- NumPy 2.x: `np.cross` on 2D vectors raises; compute `ab[:,0]*ac[:,1]-ab[:,1]*ac[:,0]`.
- PIL `polygon` fill includes boundary pixels, so raster overlap counts on shared edges are meaningless; check tiling by summing triangle areas == W*H instead.
- Don't issue `read` of an image in the same parallel batch as the bash that creates it (races, "not found").
- Probe flatness on a facet interior, not an arbitrary patch (may straddle an edge).
- Right after `omarchy theme set`, `readlink ~/.local/state/omarchy/current/background` can briefly show the previous wallpaper (shell repoints after the crossfade); wait 1-2s before asserting.
- A `jq: parse error` line from `omarchy theme set` comes from the stock script's `owe status` call, not from user hooks.
