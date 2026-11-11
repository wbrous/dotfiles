---
name: flat-lowpoly-flag-wallpaper-python
description: "Generate a 4K+ flat-shaded low-poly pride-flag wallpaper (hard edges, exact antialiasing, irregular non-grid facets, sized to the main display) with a Rust binary in under 50 ms, and regenerate it on Omarchy theme select via a theme-set hook. Includes bar-contrast guarantee and mesh-quality rules."
---

# Flat low-poly flag wallpaper (Rust) + Omarchy theme-set hook

Use for "make/regenerate a low-poly pride wallpaper", "faster / lower CPU", "no thin triangles", "looks too procedural/grid-like", or "regenerate when I pick theme X" on Omarchy. Live implementation: `~/.local/share/pride-wallpaper/` (Rust source in `rs/`, installed binary `pride-wallpaper`, old Python `generate.py` kept only as the reference).

## HARD RULE: do not switch Omarchy themes to test
The user uses this laptop while you work. `omarchy theme set` / `theme bg set` flips wallpaper and recolours the desktop. NEVER do it unless asked. Verify only by running the binary to /tmp (`pride-wallpaper /tmp/x.png --seed N [--size WxH]`), viewing the PNG, running cargo tests, and `omarchy-bar-text-color ... --background /tmp/x.png` (reads a file only). Copying the binary into place (`install`) is fine; the hook only runs when the user picks Pride.

## Current result (measured)
- 5760x3840 (2x the 2880x1920 panel) in ~25-45 ms wall (30 runs: median 34 ms, worst 42 ms), ~85-110 ms CPU, ~0.8 MB PNG. Python was 6.8 s wall / 12.4 s CPU.
- Build: `cd rs && cargo build --release && install -m 0755 target/release/pride-wallpaper ../pride-wallpaper` (hook calls the installed copy, so REINSTALL after every rebuild). Deps: png, rayon, serde_json, toml only.

## Layout: irregular, NOT a grid (user said grid looked "procedural", pairs of triangles made squares)
- Variable-radius Poisson-disk sampling (`build_points`): a candidate is kept only if >= min(local radius of both) from every kept point, so the minimum spacing is a hard floor (no needles / cramped knots) yet no rows/columns exist. Dart throwing against a uniform accel grid, ~30 attempts per base-cell.
- Local radius = base x spacing_scale(x,y): smooth field from 3 seeded sine ridges, depth 0.38-0.45 => spacing 0.55x-1.45x, facet area up to ~13x spread. Base spacing = longer side / 11-14 (so facet size is the same on any aspect ratio). ~70-190 triangles at 16:9.
- Frame coverage: 4 corners + points walked along every edge at the local radius (last step snapped so no short stub); interior samples keep 0.6 x radius from the edges so no sliver forms at the border.
- Measured over 100 seeds x 3 shapes: min angle 22.7 deg (grid was 21.8), area ratio 11-13x (grid 4.5x, original clustered design 4,000,000x), near-right-isosceles triangles 10.9% (grid 22.0%; a random mesh sits near ~10%, so square pairing is gone).
- Tests enforce: min angle >= 20, area ratio <= 20x (ceiling, variety is wanted), <= 300 triangles at 16:9, density field varies >= 1.5x, no two points closer than 0.45 x local radius.
- The jittered grid (9-12 cols, jitter <= 0.22) was the previous design; it removed slivers but looked mechanical. Do not go back to it. Clusters (extra dense blobs) caused the slivers; do not re-add.

## Other design rules the user asked for
- Hard edges, no blending: exact area-coverage rasterization at output resolution (no supersampling, no dilation). Triangles tile the frame so coverages sum to 1 => no seams.
- Size = main display native size x 2 (`--scale`), read from Hyprland's IPC socket (`<XDG_RUNTIME_DIR>/hypr/<sig>/.socket.sock`, send `j/monitors`), NOT a `hyprctl` subprocess (4 ms vs 0.05 ms). Rotated transforms 1/3/5/7 swap w/h. Any failure falls back to 3840x2160. Signature auto-discovered from newest dir when unset (detached hooks).
- Omarchy top bar must stay light: `omarchy-bar-text-color` flips to the dark colour when the wallpaper's top-strip mean luminance exceeds L* = sqrt((Lt+.05)(Ld+.05))-.05 (0.1547 for Pride colours #b0ebe7 / #14021c). Generator keeps the strip (4.2% of height) under L* x 0.88 by darkening only strip-touching facets with a bisected factor; strip mean is computed analytically from facet colours x exact area in strip (no painting). Re-verified 120/120 light on the Poisson layout.

## Performance lessons (all measured, do not re-learn)
- Specialised rasterizer beats general ones (tiny-skia etc.): per row, solid span memset + exact Sutherland-Hodgman coverage only at edge pixels.
- Render in 16-row bands in parallel with rayon, each band owns a disjoint output slice and a small u16 accumulator (cache resident). A 132 MB full-frame accumulator was the main cost. Deterministic regardless of threads.
- Threads: 6 is the sweet spot (29 ms vs 25 ms at 24 threads, but 96 ms vs 163 ms CPU). Capped in `configure_threads`.
- PNG: `png` crate `Compression::Fast` (fdeflate) + `Filter::Sub` is the fastest single-thread option (~9 ms for 22 MP). libdeflate was SLOWER (44 ms at level 1) on this flat data. `fpng-rs` fails to build with GCC 16 (PCLMUL needs -mpclmul). NoFilter = 65 ms / 66 MB. Hand-rolled parallel zlib not worth the corruption risk.
- Poisson sampling cost is negligible next to raster + PNG.

## Gotchas
- `omarchy theme bg set` while on theme A makes the file A's remembered background; the hook only regenerates when PRIDE's remembered/live background is a `zz-generated-*` file. To opt in: the user switches to Pride, then picks the generated image there.
- Generated files are named `zz-generated-<ns>.png` so they sort last and never become Pride's default image; hook order is generate -> delete other zz-generated files -> `omarchy theme bg set <new>` (delete-before-apply, so no dead entry lingers past the switch). Old image stays decoded in the shell during the crossfade; new renders from its own untouched file.
- Hook detaches via `setsid` and logs to `~/.local/state/omarchy/pride-wallpaper.log`; `flock -n` stops pile-ups.
- Edit tool: bodyless deletes must use CUT, an empty PUT deletes; re-read after each edit since tags/line numbers shift (several edits clobbered neighbouring code). When replacing a struct's fields, grep for every `.field` use in tests too.
- Tests: raster has a brute-force differential test (fast span path vs per-pixel exact coverage on 4,500 random + sliver triangles); keep it when touching `inner_run`.
- System python has no PIL; use `~/.local/share/pride-wallpaper/.venv/bin/python` for image inspection. Parallel `read` of an image created by the same batch races.
