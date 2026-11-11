---
name: flat-lowpoly-flag-wallpaper-python
description: "Generate a 4K+ flat-shaded low-poly pride-flag wallpaper (hard edges, exact antialiasing, sized to the main display) with a Rust binary in under 50 ms, and regenerate it on Omarchy theme select via a theme-set hook. Includes bar-contrast guarantee and mesh-quality rules."
---

# Flat low-poly flag wallpaper (Rust) + Omarchy theme-set hook

Use for "make/regenerate a low-poly pride wallpaper", "faster / lower CPU", "no thin triangles", or "regenerate when I pick theme X" on Omarchy. Live implementation: `~/.local/share/pride-wallpaper/` (Rust source in `rs/`, installed binary `pride-wallpaper`, old Python `generate.py` kept only as the reference).

## Current result (measured)
- 5760x3840 (2x the 2880x1920 panel) in ~25-45 ms wall, ~85-100 ms CPU, 0.77 MB PNG. Python was 6.8 s wall / 12.4 s CPU.
- Build: `cd rs && cargo build --release && install -m 0755 target/release/pride-wallpaper ../pride-wallpaper` (hook calls the installed copy, so REINSTALL after every rebuild). Deps: png, rayon, serde_json, toml only.

## Design rules the user asked for
- Hard edges, no blending: exact area-coverage rasterization at output resolution (no supersampling, no dilation). Triangles tile the frame so coverages sum to 1 => no seams.
- No thin triangles, all facets big and similar: plain jittered grid, 9-12 columns, jitter <= 0.22 of a cell, NO focal clusters. Enforced by tests (min angle >= 20 deg, biggest/smallest area <= 6x, <= 400 triangles at 16:9). Old design had 0.00 deg slivers and 4,000,000x size spread.
- Size = main display native size x 2 (`--scale`), read from Hyprland's IPC socket (`<XDG_RUNTIME_DIR>/hypr/<sig>/.socket.sock`, send `j/monitors`), NOT a `hyprctl` subprocess (4 ms vs 0.05 ms). Rotated transforms 1/3/5/7 swap w/h. Any failure falls back to 3840x2160. Signature auto-discovered from newest dir when unset (detached hooks).
- Omarchy top bar must stay light: `omarchy-bar-text-color` flips to the dark colour when the wallpaper's top-strip mean luminance exceeds L* = sqrt((Lt+.05)(Ld+.05))-.05 (0.1547 for Pride colours #b0ebe7 / #14021c). Generator keeps the strip (4.2% of height) under L* x 0.88 by darkening only strip-touching facets with a bisected factor; strip mean is computed analytically from facet colours x exact area in strip (no painting).

## Performance lessons (all measured, do not re-learn)
- Specialised rasterizer beats general ones (tiny-skia etc.): per row, solid span memset + exact Sutherland-Hodgman coverage only at edge pixels.
- Render in 16-row bands in parallel with rayon, each band owns a disjoint output slice and a small u16 accumulator (cache resident). A 132 MB full-frame accumulator was the main cost. Deterministic regardless of threads.
- Threads: 6 is the sweet spot (29 ms vs 25 ms at 24 threads, but 96 ms vs 163 ms CPU). Capped in `configure_threads`.
- PNG: `png` crate `Compression::Fast` (fdeflate) + `Filter::Sub` is the fastest single-thread option (~9 ms for 22 MP). libdeflate was SLOWER (44 ms at level 1) on this flat data. `fpng-rs` fails to build with GCC 16 (PCLMUL needs -mpclmul). NoFilter = 65 ms / 66 MB. Hand-rolled parallel zlib not worth the corruption risk.
- Resolve u16->u8 with chunks_exact_mut, not Vec::push.

## Gotchas
- `omarchy theme bg set` while on theme A makes the file A's remembered background; the hook only regenerates when PRIDE's remembered/live background is a `zz-generated-*` file. To opt in: switch to Pride, then pick the generated image there.
- Generated files are named `zz-generated-<ns>.png` so they sort last and never become Pride's default image; hook prunes all but the new one and the one that was showing.
- Hook detaches via `setsid` and logs to `~/.local/state/omarchy/pride-wallpaper.log`; `flock -n` stops pile-ups.
- Grid coordinates: force last row/col to exactly width/height (c*(w/cols) can miss w by a rounding error and leave a hairline uncovered). A test caught this.
- Edit tool: bodyless deletes must use CUT, an empty PUT deletes; re-read after each edit since tags/line numbers shift (several edits clobbered neighbouring code).
- Tests: raster has a brute-force differential test (fast span path vs per-pixel exact coverage on 4,500 random + sliver triangles); keep it when touching `inner_run`.
- System python has no PIL; use `~/.local/share/pride-wallpaper/.venv/bin/python` for image inspection. Parallel `read` of an image created by the same batch races.
