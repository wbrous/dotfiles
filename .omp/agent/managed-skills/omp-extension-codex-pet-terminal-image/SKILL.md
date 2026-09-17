---
name: omp-extension-codex-pet-terminal-image
description: "Use when building or debugging an omp/oh-my-pi extension that renders animated terminal graphics (a \"pet\" widget, live status sprite, etc.) via setWidget + Kitty/Sixel/iTerm2 image protocols, or when replicating/porting OpenAI Codex CLI's /pets ambient-terminal-pet feature (codex-rs/tui/src/pets/*). Also covers the Bun.$ shell-result field-name trap (exitCode, not code) that silently breaks code !== 0 checks, and why ctx.ui.custom()'s \"overlay\" mode is unsuitable for a persistent ambient widget."
---

## Bun.$ shell result field is `exitCode`, not `code`

`await Bun.$\`cmd ${args}\`.quiet().nothrow()` returns `{ stdout, stderr, exitCode }`. There is no `code` field — destructuring `const { code } = await Bun.$...` silently gives `undefined`, so any `code !== 0` check is *always true*. This makes every shelled-out command look like it failed, and if the failure path is swallowed by `ctx.ui.notify(...)` (a no-op in headless/print mode), the bug is completely silent. Always destructure `exitCode`.

## setWidget vs ctx.ui.custom() for a persistent ambient widget

`ctx.ui.setWidget(key, factory, {placement: "aboveEditor"|"belowEditor"})` reserves real layout rows equal to whatever height the component's `render(width)` returns. This is the *correct* primitive for a persistent, non-modal decoration (status bar, ambient pet, etc.) — it does NOT steal focus.

`ctx.ui.custom(factory, {overlay: true, ...})` looks tempting for "true overlap with zero reserved space," but it is fundamentally a **modal dialog primitive**: `TUI.showOverlay()` (its underlying call) unconditionally does `this.setFocus(component)` AND `this.terminal.hideCursor()` synchronously when the overlay is created, and only restores the cursor once the overlay stack is empty. There is no "non-focus-stealing" option. Attempting to "steal then immediately restore focus" via the `onHandle` callback does NOT reliably work — verified by testing: typed keystrokes into the composer stopped landing while the overlay was active, even with an immediate `tui.setFocus(priorFocus)` call in `onHandle`. Don't use `custom()`/overlay for anything meant to coexist with normal typing.

## Achieving "overlap" instead of "reserved block" within setWidget's real constraint

If the requirement is "the pet should overlap the transcript, not push a multi-row gap above the composer," the fix is NOT to reserve `N` rows of blank filler lines (the way `pi-tui`'s own `Image.ts` direct-placement path does, via `RESERVED_IMAGE_ROW` blank lines — that pattern exists specifically so the image *does* occupy real scrollback-safe space). Instead:

- Report **exactly one line** from `render(width)`.
- Paint the full N-row-tall sprite by wrapping in `SAVE_CURSOR (\x1b7)` → move cursor up `(rows-1)` lines (`\x1b[{n}A`) → emit the image placement/sequence (single Kitty `a=p`, Sixel DCS, or iTerm2 sequence — all three protocols paint downward from cursor position in one command, so one `moveUp` + one sequence suffices) → `RESTORE_CURSOR (\x1b8)`.
- For the Kitty **unicode-placeholder** grid path (`renderImage()` returns `result.lines`, an array of N real text-cell rows instead of one `sequence`), there's no single "paint N rows" primitive — join the rows with `\r\n` inside the same `SAVE_CURSOR ... RESTORE_CURSOR` wrapper; `RESTORE_CURSOR` guarantees exact position recovery regardless of intermediate `\r\n` cursor movement, so this is safe.
- This visually paints over whatever was already rendered in the rows above (the transcript tail), using only 1 line of real layout footprint — the actual overlap behavior the user wants, achieved entirely within the `setWidget` contract (no focus-stealing, no cursor hiding).

## Command surface: prefer a single command name

When porting a feature whose upstream CLI names a command `/pets` with an alias `/pet` (or vice versa), don't automatically register both. If asked to trim it down, just remove `pi.registerCommand("pets", ...)` and keep the one canonical name (`pet`), pointing both at the same handler function was pointless duplication once only one name is wanted.

## Verification technique for terminal-graphics extensions

`hub start` a real `omp` TUI session (not headless `-p`), then `hub logs` — even though it's a flat scrollback text dump (not a true screen capture), the raw bytes contain the actual escape sequences sent to the terminal. Grep for `U+10EEEE` (Kitty Unicode placeholder base char) to confirm the graphics path is actually firing across repaint ticks (proves animation timing works), and `hub send` a test string then grep for it in the tail to confirm keyboard focus reached the composer (proves no accidental focus-stealing). This is the only practical way to verify Kitty-graphics-protocol extension behavior without a real interactive terminal window to look at.
