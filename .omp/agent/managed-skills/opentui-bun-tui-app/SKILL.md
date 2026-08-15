---
name: opentui-bun-tui-app
description: "Use when building a terminal UI app with Bun + @opentui/core (OpenTUI) — covers renderer setup, Renderable-class API (Box/Text/Input/Select/Image), focus routing, image cropping via NativeImage, and perceptual-hash image matching without extra image libs."
---

## OpenTUI (Bun-only TUI framework) key facts

Install: `bun add @opentui/core`. Native FFI renderer requires Bun (Node needs 26.4+ with `--experimental-ffi`).

### Renderer bootstrap
```ts
import { createCliRenderer, BoxRenderable, TextRenderable } from "@opentui/core";
const renderer = await createCliRenderer({ exitOnCtrlC: true, targetFps: 30 });
renderer.root.add(myRootBox); // root fills terminal, no need to size it
```
Two APIs exist: **Renderable classes** (`new BoxRenderable(ctx, opts)`) for direct instance control/mutation, and **Construct factories** (`Box(props, ...children)`) for quick declarative trees. Prefer Renderable classes when you need to mutate state later (list contents, image source, selection).

### Core components
- `BoxRenderable` — flexbox container (Yoga layout: flexDirection, justifyContent, alignItems, padding, gap, position "relative"/"absolute" + left/top for overlays).
- `TextRenderable` — `content` (plain string or `t\`${fg("#hex")(bold("x"))}\`` styled template).
- `InputRenderable` — `.value`, `.focus()/.blur()/.focused`, events via `InputRenderableEvents`: `INPUT` (every keystroke), `CHANGE` (on blur/Enter if changed), `ENTER` (submit).
- `SelectRenderable` — vertical list w/ built-in scrolling; `options: {name,description,value}[]`; events `SelectRenderableEvents.SELECTION_CHANGED` (highlight moved, good for live preview panes) and `ITEM_SELECTED` (Enter pressed). Methods: `getSelectedIndex/Option`, `setSelectedIndex`, `moveUp/moveDown`.
- `ImageRenderable` — `source` accepts path/URL/Blob/Uint8Array/ArrayBuffer; `fit: "fit"|"cover"|"fill"`, `protocol: "auto"|"kitty"|"sixel"|"blocks"`. `await image.loadPromise` after setting source. **`fit:"fill"` stretches the image to exactly fill the box, which makes terminal-cell coordinates map linearly onto source pixel coordinates** — essential trick for building crop/selection tools without extra math libraries.
- `NativeImage` (from `@opentui/core`) — decode/manipulate images with zero extra deps (no sharp/jimp needed): `NativeImage.load(path|url)`, `.raw("rgba8")` → `{data,width,height,stride}`, `.resize({width,height,kernel})`, `.extract({left,top,width,height})` (crop), `.rotate/.flip/.flop/.composite`. All ops are immutable (return new image); **must `.dispose()` every image you own**, including operation results.
- `NativeImage.fromRgba(uint8Array, width, height)` — build a synthetic image from raw RGBA bytes; useful for unit-testing image code without real files.

### Focus & keyboard
- Only one component focused at a time; `renderer.keyInput` is a **global** EventEmitter (`"keypress"` gives `KeyEvent {name, ctrl, shift, meta, sequence, raw}`) that fires alongside normal focus routing — safe to use for app-level shortcuts (Tab-cycle focus, F-key tab switching) even while an Input has focus, since function keys don't get typed as text.
- Manual focus-cycling pattern: keep an ordered `Renderable[]` of focusables per view, find current via `.focused`, call `.focus()` on next/prev on `Tab`/`Shift+Tab`.
- Key names: `"return"` (Enter), `"escape"`, `"space"`, `"tab"`, `"up"/"down"/"left"/"right"`, `"f1".."f12"`.

### Building a crop/selection tool (no extra deps)
1. Render the image with `fit:"fill"` inside a `BoxRenderable` of known fixed cell width/height.
2. Overlay a bordered `BoxRenderable` with `position:"absolute"` + `left/top/width/height` in cells as the selection rectangle; update these on arrow-key handlers (plain arrows = move, Shift+arrows = resize, clamp to box bounds).
3. On confirm, map cell rect → pixel rect: `px = round(cellX/boxWidthCells * nativeImage.width)` (same for y/w/h), then `nativeImage.extract({left,top,width,height})`.

### Perceptual image matching without a library
Implement dHash directly on `NativeImage.raw()` pixels: resize to 9x8, grayscale via luminance formula, compare each pixel to its right neighbor → 64-bit hash (bigint). Confidence = `1 - hammingDistance(a,b)/64`. Validated behavior: identical images → 1.0, random noise → ~0.5, structurally inverted → mid-range (not 0, since dHash only encodes local gradient direction, not global polarity).

### Gotchas found in practice
- `createCliRenderer`'s built-in console overlay (`consoleMode: "console-overlay"`, default) **captures `console.log`**, hiding it from normal stdout — pass `consoleMode: "disabled"` when testing renderer code via eval/scripts so `console.log`/thrown errors are visible.
- Terminal size: no built-in reactive resize handling documented for simple apps — read `process.stdout.columns/rows` once at startup for fixed-size layouts; acceptable for short-lived CLI tools.
- `bun run <file>.ts` auto-loads `.env` — no dotenv package needed.
- Sending function keys (F1/F2 etc.) through a PTY test harness via literal `"\u001bOQ"` text strings doesn't work (gets typed literally, not interpreted as an escape sequence) — most harnesses need real byte-level escape injection or don't support arbitrary function keys at all; don't rely on this for automated smoke tests, just verify boot/render and Ctrl+C exit instead.
