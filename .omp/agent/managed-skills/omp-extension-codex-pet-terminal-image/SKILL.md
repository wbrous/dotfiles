---
name: omp-extension-codex-pet-terminal-image
description: "Use when building or debugging an omp/oh-my-pi extension that renders animated terminal graphics (a \"pet\" widget, live status sprite, etc.) via setWidget + Kitty/Sixel/iTerm2 image protocols, or when replicating/porting OpenAI Codex CLI's /pets ambient-terminal-pet feature (codex-rs/tui/src/pets/*). Also covers the Bun.$ shell-result field-name trap (exitCode, not code) that silently breaks code !== 0 checks, why ctx.ui.custom()'s \"overlay\" mode is unsuitable for a persistent ambient widget, and the correct technique for a widget that overlaps/floats over existing content instead of reserving a multi-row block."
---

## Context

Building `~/.omp/agent/extensions/codex-pet/index.ts`: an omp extension replicating OpenAI Codex CLI's ambient terminal pet feature (animated sprite reacting to agent state, rendered via terminal image protocols). Ported from `codex-rs/tui/src/pets/*` (PR #21206). Full behavior spec (row/frame/timing tables, notification kinds, lifetimes) is in that source — read it directly rather than re-deriving from memory.

## Gotcha: `Bun.$` shell result field is `exitCode`, not `code`

```ts
const { stdout, code } = await Bun.$`which magick`.quiet().nothrow();
if (code === 0) { ... } // BUG: `code` is always `undefined`, so this never fires
```

The correct field is `exitCode`. `code` silently exists as `undefined` on the result object (no TS error if the destructure target is loosely typed), so `code !== 0` is always true and `code === 0` is always false — every shell-command-success check silently takes the failure branch. This is exactly the kind of bug `ctx.ui.notify(...)` swallows in headless/print mode (no-op there), so it can pass a live smoke test with zero visible errors while doing nothing. Verify shell-command gated logic by checking its actual side effects on disk (e.g. did the expected cache files get created), not just "did the session run without printing an error."

## Gotcha: `ctx.ui.custom()` overlay mode is a modal primitive, not ambient decor

`ExtensionUIContext.custom(factory, { overlay: true, ... })` looks tempting for a persistent floating widget that shouldn't push a layout row — but tracing `TUI.showOverlay` in `packages/tui/src/tui.ts` shows it unconditionally:
- calls `this.setFocus(component)` synchronously, and
- calls `this.terminal.hideCursor()`, which only gets undone when `overlayStack.length === 0`.

If you never call the `done()` callback (to keep the overlay open indefinitely) and try to hack around the focus steal by calling `tui.setFocus(priorFocus)` from the `onHandle` callback, this does NOT reliably survive — confirmed by live testing: typed keystrokes stopped reaching the composer even after this "restore" hack. `custom()`/`showOverlay` is fundamentally a modal-picker primitive (dialogs, pickers); do not repurpose it for always-on ambient UI. Use `ctx.ui.setWidget(key, factory, { placement: "aboveEditor" | "belowEditor" })` instead for persistent decorations — it does not touch focus or cursor visibility.

## Technique: overlap instead of reserving a multi-row block

`setWidget` reserves exactly as many terminal rows as `Component.render(width)` returns. A naive port of `pi-tui`'s `Image` component reserves `N` rows (image height in cells) by returning `N-1` blank filler lines plus one real line — this visibly pushes a multi-row gap above the composer, which reads as an unwanted "line break" rather than an overlapping decoration.

Fix: report exactly **one** line from `render()`, and paint the full N-row-tall image by using the standard terminal cursor save/move/restore trick:

```ts
const SAVE_CURSOR = "\x1b7";
const RESTORE_CURSOR = "\x1b8";

// cursorRows = imageRows - 1
const moveUp = cursorRows > 0 ? `\x1b[${cursorRows}A` : "";
const body = moveUp + content; // content = the actual image escape sequence(s)
return [cursorRows > 0 ? SAVE_CURSOR + body + RESTORE_CURSOR : body];
```

This tells the layout engine the widget is 1 row tall (so it only adds 1 row of space), while the image visually paints upward over whatever was already rendered in the rows above (the transcript tail) — genuine overlap, not a reserved block.

### Sub-gotcha: right-anchoring every row of a multi-row paint

If the image renderer's "unicode placeholder" protocol path returns multiple real text rows (`result.lines`, one physical terminal row of placeholder characters each — as opposed to the "direct placement" path, which is a single APC/sequence the terminal itself expands over N rows from one cursor position), you must right-shift **every** row individually, not just the first:

```ts
// WRONG: pad only shifts the first row; every row after "\r\n" resets to column 0,
// left-aligning it and (if pad is literal spaces) blanking over existing text there.
return [pad + SAVE_CURSOR + moveUp + result.lines.join("\r\n") + RESTORE_CURSOR];

// RIGHT: shift every row via non-destructive cursor-forward (CUF), not literal
// padding spaces — CUF moves the cursor without touching the cells it crosses,
// so text already on the left of each row stays visible instead of being erased.
const moveRight = padCols > 0 ? `\x1b[${padCols}C` : "";
const content = result.lines
  .map((line, i) => (i === 0 ? transmitPrefix : "") + moveRight + line)
  .join("\r\n");
return [SAVE_CURSOR + moveUp + content + RESTORE_CURSOR];
```

Use `ESC[nC` (Cursor Forward, CUF) for horizontal positioning across multiple painted rows, never literal space characters — spaces overwrite/erase whatever character was already in those cells, which is exactly the "overlapping text and breaking visuals" symptom this produces if you get it wrong. The single-command protocols (direct-placement Kitty, Sixel, iTerm2 — anything that returns `result.sequence` instead of `result.lines`) don't have this problem: the terminal expands the image over N rows itself from one cursor position, so only one shift is ever needed.

### Known limitation: this is overlap, not reflow

Real text-wrap-around (transcript narrowing its own wrap width to leave a permanent gutter for the pet, like Codex's Rust TUI does via `history_wrap_width`) is not achievable through the extension API — extensions have no hook into the core transcript renderer's wrap width. If a transcript line's text already extends into the pet's column range, the sprite will sit on top of those characters rather than the text having wrapped around it in advance. State this limitation explicitly rather than implying full CSS-float-style reflow was achieved.

## Verifying image-protocol rendering without a real screenshot

`hub start` an interactive `omp` TUI session and use `hub logs` to read the raw captured output. On a Kitty-graphics-capable terminal (`xterm-kitty`), look for the `U+10EEEE` Unicode placeholder character repeated with row/column combining diacritics — its presence (and repetition over time, matching animation frame timing) confirms the live-graphics path is actually firing, not falling back to text. To verify focus wasn't stolen by a UI change, use `hub send` to type literal text into the composer and grep the subsequent `hub logs` output for that exact string landing in the input area.
