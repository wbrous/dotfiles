# Wallpapers

Generating and recoloring pride-flag wallpapers.

## Flat low-poly pride-flag wallpaper (Rust) + Omarchy theme-set hook

**Symptom:** Want/regenerate a 4K+ flat-shaded low-poly pride wallpaper; faster builds; no thin triangles; non-procedural look; regenerate on theme pick.

**Cause / implementation:** Live in `~/.local/share/pride-wallpaper/` (Rust source `rs/`, installed binary `pride-wallpaper`; old Python `generate.py` is reference only). HARD RULE: never `omarchy theme set` / `theme bg set` to test — it flips the user's live desktop. Verify only by running the binary to /tmp, viewing the PNG, `cargo test`, and `omarchy-bar-text-color ... --background /tmp/x.png` (reads a file). `install` after every rebuild — the hook calls the installed copy.

**Fix — result:** 5760x3840 (2x the 2880x1920 panel) in ~25-45ms wall (median 34ms), ~85-110ms CPU, ~0.8MB PNG. Build: `cd rs && cargo build --release && install -m 0755 target/release/pride-wallpaper ../pride-wallpaper`. Deps: png, rayon, serde_json, toml only.

**Fix — irregular layout (NOT a grid):** variable-radius Poisson-disk sampling — a candidate is kept only if >= min(local radius of both) from every kept point (hard floor, no needles/cramped knots, no rows/columns); ~30 attempts per base-cell against a uniform accel grid. Local radius = base × spacing_scale(x,y): smooth field from 3 seeded sine ridges, depth 0.38-0.45 → spacing 0.55x-1.45x, facet area up to ~13x spread. Base = longer side / 11-14. ~70-190 triangles at 16:9. Frame: 4 corners + edge-walked points at local radius (last step snapped), interior samples keep 0.6× radius from edges. Measured over 100 seeds × 3 shapes: min angle 22.7° (grid 21.8), area ratio 11-13× (grid 4.5×), near-right-isosceles 10.9% (grid 22%; random mesh ≈10% — square pairing gone). Tests enforce: min angle ≥20, area ratio ≤20×, ≤300 triangles at 16:9, density varies ≥1.5×, no two points closer than 0.45× local radius. The jittered grid (9-12 cols, jitter ≤0.22) looked mechanical — don't go back; dense clusters caused slivers — don't re-add.

**Fix — other design rules:** hard edges, no blending: exact area-coverage rasterization at output resolution (no supersampling/dilation; tiles sum to 1, no seams). Size = main display ×2 (`--scale`) from Hyprland's IPC socket (`<XDG_RUNTIME_DIR>/hypr/<sig>/.socket.sock`, send `j/monitors`), not a `hyprctl` subprocess (0.05ms vs 4ms); rotated transforms 1/3/5/7 swap w/h; fallback 3840x2160; signature auto-discovered from newest dir when unset. Top bar stays light: `omarchy-bar-text-color` flips at top-strip mean luminance L* = sqrt((Lt+.05)(Ld+.05))-.05 (0.1547 for #b0ebe7/#14021c); generator keeps the strip (4.2% height) under L*×0.88 by darkening only strip-touching facets with a bisected factor, computed analytically from facet colors × exact strip area. Re-verified 120/120 light on the Poisson layout.

**Fix — performance (all measured):** specialized rasterizer beats general ones — per row, solid-span memset + exact Sutherland-Hodgman coverage only at edge pixels. Render in 16-row rayon bands, each owning a disjoint slice + small u16 accumulator (a 132MB full-frame accumulator was the main cost). Deterministic regardless of threads; 6 threads is the sweet spot (29ms vs 25ms at 24 threads, 96ms vs 163ms CPU; capped in `configure_threads`). PNG: `png` crate `Compression::Fast` (fdeflate) + `Filter::Sub` fastest single-thread (~9ms for 22MP); libdeflate SLOWER (44ms level 1); `fpng-rs` fails with GCC 16 (PCLMUL needs `-mpclmul`); NoFilter = 65ms/66MB. Hand-rolled parallel zlib not worth the corruption risk. Poisson sampling cost negligible next to raster+PNG.

**Gotchas:** `omarchy theme bg set` on theme A makes the file A's remembered background; the hook only regenerates when PRIDE's remembered/live background is a `zz-generated-*` file — opt in by switching to Pride then picking the generated image there. Generated files named `zz-generated-<ns>.png` (sort last, never Pride's default); hook order: generate → delete other zz-generated files → `omarchy theme bg set <new>`. Old image stays decoded during crossfade. Hook detaches via `setsid`, logs to `~/.local/state/omarchy/pride-wallpaper.log`, `flock -n` against pile-ups. System python has no PIL — use `~/.local/share/pride-wallpaper/.venv/bin/python`. Edit-tool: bodyless deletes need CUT; re-read after each edit (tags shift). Keep the brute-force differential raster test when touching `inner_run`.

_Migrated from: flat-lowpoly-flag-wallpaper-python_

## Recoloring flat-stripe flags in an anime wallpaper (e.g. trans → bi)

**Symptom:** Replace a flat-stripe flag's colors, including matching stripes on clothing.

**Cause:** Pure color-distance masks bleed onto same-colored clothing; per-channel percentage maps destroy shading. Position-dependent band/silhouette masks are required.

**Fix — setup:** no PIL/numpy by default: `python3 -m venv /tmp/bi && /tmp/bi/bin/pip install -q numpy pillow scipy opencv-python-headless`. Never issue the script-writing call and a `read` of its output image in the same parallel batch (read races the write); make crops in one call, read in the next.

**Fix — procedure:**
1. Stripe bounds: print color changes down a column far from the character (x~100). (Original flag was 5×114px; bi is 2:1:2 = 228/114/228. Bi hexes: magenta D60270, purple 9B4F96, blue 0038A8.)
2. Background: per-row original = column x=100. Core = pixels dist<6 to row color; flood-label (`scipy.ndimage.label`), keep components touching BOTH edge strips (seed both sides). Soft-blend only within 3px dilation.
3. Clothing mask: HSV hue (blue h170-225, pink h>330|<15, white low-S high-V), keep big components, close+fill holes, dilate 3px (includes the pale rim highlight that fails the hue test), propagate band id to unclassified pixels by nearest classified pixel (≤10px). Assign each band by centroid y.
4. Clothing transfer = ONE scalar per pixel: s = Y/Y_band_base. s≤1: new = target×s. s>1: new = target + (255-target)×clip((s-1)/(smax-1)). Median-blur s lightly. Clamp smax≥1.35 or the near-white band (Y~249) speckles. FAILED alternatives (don't retry): Lab chroma scaling (grey/brown); per-channel three-anchor map (rim turns yellow/mint as R,G saturate while B stays).
5. Character-edge fringe: build a GEOMETRIC silhouette, not hue tests (skin highlight ≈ old cream stripe; color masks paint purple into skin). Dark lineart (Y<110/120) in a window, close (k~7-9 ellipse), fill holes, label, take component with a known interior point. Inside: restore ORIGINAL pixels; ≤4px ring outside: repaint `new_row_color × a`, a = projection of original onto old row color. Hand outline has gaps — union a dedicated hand silhouette. Exclude blue-hue (cuff) pixels, dilated 2px, from the hand restore or the cuff pastes back with a seam.
6. Final sweep: outside (character|hand) silhouette, inside exact flag rows, differing from new row color by >6 → repaint `new_row×a`. Clip to exact rows (padding draws a stray line).
7. Tiny enclosed old-stripe pockets: box-scoped recolor with reddish test; 1px seams between old stripes are blends t·A+(1-t)·B — rebuild with new colors the same way.

Verify with 4-8× NEAREST side-by-sides (original|result) of both shoulder tops, sleeve edge, hand, cuff — flaws hide at full-frame scale. Stop chasing <10 residual px at 2560x1440. "Map every old flag color to bi by percentage" was TESTED and FAILS (5-band pattern, repaints skin/face/legs pink, background purple). PhotoCraft `select.colorRange` is the same color-only selection — adds nothing; don't touch the live GUI.

_Migrated from: recolor-flag-stripes-in-anime-wallpaper_
