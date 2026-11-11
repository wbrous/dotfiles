# TUI + Procedural SVG Art

Covers building terminal UIs with Bun + OpenTUI, and batch-generating varied procedural SVG cartoon characters.

## Bun + OpenTUI terminal apps

Install: `bun add @opentui/core`. Native FFI renderer requires Bun (Node needs 26.4+ with `--experimental-ffi`).

**Renderer bootstrap:**

```ts
import { createCliRenderer, BoxRenderable, TextRenderable } from "@opentui/core";
const renderer = await createCliRenderer({ exitOnCtrlC: true, targetFps: 30 });
renderer.root.add(myRootBox); // root fills terminal, no need to size it
```

Two APIs: **Renderable classes** (`new BoxRenderable(ctx, opts)`) for direct instance control/mutation, and **Construct factories** (`Box(props, ...children)`) for quick declarative trees. Prefer Renderable classes when mutating state later (list contents, image source, selection).

**Core components:**

- `BoxRenderable` — flexbox container (Yoga layout: flexDirection, justifyContent, alignItems, padding, gap, position relative/absolute + left/top for overlays).
- `TextRenderable` — `content` (plain string or styled template `` t`${fg("#hex")(bold("x"))}` ``).
- `InputRenderable` — `.value`, `.focus()/.blur()/.focused`; events `INPUT` (every keystroke), `CHANGE` (blur/Enter if changed), `ENTER` (submit).
- `SelectRenderable` — vertical list with built-in scrolling; `options: {name,description,value}[]`; events `SELECTION_CHANGED` (highlight moved, good for live preview panes) and `ITEM_SELECTED` (Enter). Methods `getSelectedIndex/Option`, `setSelectedIndex`, `moveUp/moveDown`.
- `ImageRenderable` — `source` accepts path/URL/Blob/Uint8Array/ArrayBuffer; `fit: "fit"|"cover"|"fill"`, `protocol: "auto"|"kitty"|"sixel"|"blocks"`. `await image.loadPromise` after setting source. **`fit:"fill"` stretches the image to exactly fill the box**, so terminal-cell coordinates map linearly onto source pixel coordinates — the essential trick for crop/selection tools without extra math libs.
- `NativeImage` (from `@opentui/core`) — decode/manipulate images with zero extra deps (no sharp/jimp): `NativeImage.load(path|url)`, `.raw("rgba8")` → `{data,width,height,stride}`, `.resize({width,height,kernel})`, `.extract({left,top,width,height})`, `.rotate/.flip/.flop/.composite`. All ops immutable (return new image); **must `.dispose()` every image you own**, including operation results. `NativeImage.fromRgba(uint8Array, width, height)` builds synthetic images for unit tests without real files.

**Focus & keyboard:** only one component focused at a time; `renderer.keyInput` is a **global** EventEmitter (`"keypress"` gives `KeyEvent {name, ctrl, shift, meta, sequence, raw}`) firing alongside normal focus routing — safe for app-level shortcuts (Tab-cycle focus, F-key tab switching) even while an Input has focus, since function keys don't get typed as text. Manual focus-cycling: keep an ordered `Renderable[]` of focusables per view, find current via `.focused`, `.focus()` next/prev on Tab/Shift+Tab. Key names: `"return"`, `"escape"`, `"space"`, `"tab"`, `"up"/"down"/"left"/"right"`, `"f1".."f12"`.

**Crop/selection tool (no extra deps):** render the image with `fit:"fill"` in a fixed-cell `BoxRenderable`; overlay a bordered `BoxRenderable` with `position:"absolute"` + left/top/width/height in cells as the selection rect; update on arrow keys (plain arrows = move, Shift+arrows = resize, clamp to bounds); on confirm map cell rect → pixels (`px = round(cellX/boxWidthCells * nativeImage.width)`, same for y/w/h), then `nativeImage.extract({left,top,width,height})`.

**Perceptual image matching without a library:** dHash on `NativeImage.raw()` pixels: resize to 9x8, grayscale via luminance, compare each pixel to its right neighbor → 64-bit hash (bigint). Confidence = `1 - hammingDistance(a,b)/64`. Validated: identical → 1.0, random noise → ~0.5, structurally inverted → mid-range (dHash only encodes local gradient direction, not global polarity).

**Gotchas:** `createCliRenderer`'s default `consoleMode: "console-overlay"` **captures `console.log`** — pass `consoleMode: "disabled"` when testing via eval/scripts so logs/errors stay visible. No built-in reactive terminal-resize handling for simple apps — read `process.stdout.columns/rows` once at startup. `bun run <file>.ts` auto-loads `.env` (no dotenv needed). Sending function keys through a PTY test harness as literal `"\u001bOQ"` strings doesn't work (typed literally, not interpreted as escape) — don't rely on it for automated smoke tests; verify boot/render + Ctrl+C exit instead.

_Migrated from: opentui-bun-tui-app_

## Batch procedural SVG characters

For requests like "10 SVGs of each type, each looks different, in a fighting stance" (worked example: rock-type cards — igneous/sedimentary/metamorphic fighters).

**Procedure:**

1. Put the generator in a file (e.g. `<out>/generate.py`), not just an `eval` cell. Fixes are then edit + rerun, and the user can regenerate. `inspect.getsource` can't read `eval`-defined functions (`OSError: could not get source code`). Regex-patching the SVG output leaves the generator buggy, so a regenerate brings the bug back.
2. One `make(kind, i) -> str` with `random.Random(f"{kind}{i}")`. Each variant deterministic, so tweaking one doesn't reshuffle the rest.
3. Canvas: `viewBox="0 0 400 400"`. No background rect — art stays transparent on any card colour.
4. Body: irregular polygon from a jittered ellipse (7–12 points, radius ×0.82–1.08, angle jitter ±0.2 rad). Thick dark stroke, `stroke-linejoin="round"`. Limbs are quadratic `path`s with `stroke-linecap="round"`.
5. Paint order: ground shadow → legs/feet → arms → body → texture clipped to the body (`<clipPath>` of the body polygon) → face → fists last (overlap the body).
6. Variety: discrete features by index modulo so every option appears (`pose=i%3`, `mouth=i%4`); continuous features (size, eye spacing, lean) from the seeded RNG. 3 poses × 4 mouths alone reads as near-clones — for "each looks different", give every variant ≥2 discrete differences, using more poses (guard, jab, uppercut, kick), accessories (headband, bandage, eye patch, belt), body aspect and texture variants.
7. For educational content, make the category texture show the science: igneous = crystal glints + lava cracks; sedimentary = horizontal strata + fossil shells; metamorphic = wavy foliation bands + garnet dots.
8. Check visually: `montage <out>/*.svg -tile 10x3 -geometry 160x160+4+4 /tmp/sheet.png` (ImageMagick renders SVG), then read the PNG. Look at expressions, limb attachment, clipping and overlap.

**Pitfalls:**

- Angry brows: the inner end (toward face centre) must be LOWER (larger y) than the outer end. Inner-higher reads as worried/sad. With eye at `ex = cx + sx*sp` (`sx=-1` left, `+1` right): `M{ex - sx*20},{ey-er+2} L{ex + sx*8},{ey-er-14}`.
- Unique ids per file (`clip-{kind}-{i}`), never shared `id="b"`. If several SVGs are inlined in one HTML page, `url(#b)` resolves to the first match — every character gets clipped to the first body shape.
- Thick black outlines disappear on dark card backgrounds. Suggest a light panel or glow behind the art, or add a light outer stroke.

_Migrated from: procedural-svg-character-batch_
