---
name: omp-extension-codex-pet-terminal-image
description: "Use when building or debugging an omp/oh-my-pi extension that renders animated terminal graphics (a \"pet\" widget, live status sprite, etc.) via setWidget + Kitty/Sixel/iTerm2 image protocols, or when replicating/porting OpenAI Codex CLI's /pets ambient-terminal-pet feature (codex-rs/tui/src/pets/*). Also covers the Bun.$ shell-result field-name trap (exitCode, not code) that silently breaks code !== 0 checks."
---

## Context

Built `~/.omp/agent/extensions/codex-pet/` replicating OpenAI Codex CLI's `/pets`
feature (source: `codex-rs/tui/src/pets/*`, PR #21206). Useful reference for any
future omp extension that needs to draw a live, animated inline image in the
terminal, or that needs to port Codex TUI behavior faithfully.

## Codex `/pets` source-of-truth facts (confirmed by reading the Rust source)

- Grid: 8 columns, 192x208px frames. v1 atlas = 1536x1872 (9 rows), v2 = 1536x2288
  (11 rows, adds a "look" direction grid Codex's own CLI ignores).
- Row -> state: idle=0, run-right=1, run-left=2, wave=3, jump=4, failed=5,
  waiting=6, running=7, review=8. **Only idle/running/waiting/review/failed are
  ever reachable** from Codex's real state machine — the rest are unused
  app-parity leftovers, safe to skip when porting.
- Per-frame ms durations with a longer final frame; a state animation plays its
  primary cycle **3x** then settles into the idle tail
  (`loopStart = primary.length * 3`): idle `[1680,660,660,840,840,1920]`,
  running row7×6 `120x5+220`, waiting row6×6 `150x5+260`, review row8×6
  `150x5+280`, failed row5×8 `140x7+240`.
- Notification lifetimes: running 3min, waiting 24h, review 7d, failed 60min;
  expiry reverts to idle.
- Triggers: turn/agent start -> running; any approval/elicitation/user-input
  request -> waiting; turn complete (not auto-continuing) -> review; an error
  -> failed.
- Target render box: `PET_TARGET_HEIGHT_PX=75 / TERMINAL_ROW_HEIGHT_PX=15` =>
  5 rows tall; for 192x208 frames that works out to ~9 columns wide.
- Codex's Rust CLI hard-rejects any spritesheet that isn't exactly 1536x1872
  (9 rows) even though `spriteVersionNumber: 2` / 11-row sheets exist in the
  wild (community/app format) — `PetFile` has no `deny_unknown_fields`, so
  unknown manifest keys are silently ignored, not validated. When porting to
  your own extension, prefer inferring `rows = imageHeight / frameHeight`
  instead of hardcoding 9, so both v1 and v2 sheets load correctly.

## omp extension mechanics for a live animated terminal image

- `ctx.ui.setWidget(key, factory, { placement: "aboveEditor" | "belowEditor" })`
  where `factory: (tui: TUI, theme: Theme) => Component` — this is the extension
  surface for a persistent widget above/below the composer (closest analogue to
  Codex's composer-anchored pet). `setFooter`/`setHeader` exist in the type but
  are **no-ops in interactive mode** — don't use them for this.
- `Component.render(width): readonly string[]` is the whole contract. Capture
  `tui` inside the factory closure so a background timer can later call
  `tui.requestRender()` to trigger a repaint when the animation frame changes.
- Do NOT reuse pi-tui's high-level `Image` component/`ImageBudget` for an
  *animated* sprite — `ImageBudget` is designed to transmit an image's bytes
  **once** and only re-emit cheap placement/move commands after that. An
  animation needs new pixel bytes every tick, which that budget model doesn't
  support (it will just replay frame 0 forever).
- Instead call the low-level `renderImage(base64, dims, { maxWidthCells,
  maxHeightCells, imageId, includeTransmit: true })` from `@oh-my-pi/pi-tui`
  directly every render, with **includeTransmit: true on every call** (retransmit
  full data under the same stable `imageId` each frame — this is the standard
  way terminal apps animate Kitty graphics). Handle all three return shapes:
  - `result.lines` (Kitty Unicode-placeholder path, when the terminal supports
    it): prepend `result.transmit ?? ""` onto `lines[0]` yourself — the
    high-level `Image`/`ImageBudget` classes normally handle queuing this, but
    at the low level you own that responsibility.
  - `result.sequence` + `result.rows` with no `.lines` (direct Kitty placement,
    Sixel, iTerm2): reproduce the cursor-save/move-up/restore trick from
    `pi-tui`'s `Image.render()` (`\x1b7` save, `\x1b[{rows-1}A` up, emit
    `transmit+sequence`, `\x1b8` restore), with `rows-1` blank `\x1b[0m`
    reserved lines above it so the renderer accounts for the image's height.
  - `null` (no image protocol at all): render a dim text fallback line.
- For right-aligning a fixed-width sprite inside a wider widget row, just
  prepend `" ".repeat(width - targetCols)` to every returned line — the
  padding is plain text and doesn't disturb the escape-sequence cursor tricks
  as long as it comes first.
- Drive the animation with `ctx.setTimeout`/`ctx.clearTimer` (not raw
  `setTimeout`) recursively rescheduling itself with the delay-to-next-frame
  computed from the animation track, calling `tui.requestRender()` each tick.
  These are auto-cleared on `session_shutdown` and contain thrown errors so a
  bad tick can't crash the whole session.
- Keep one state-machine instance per `ctx.sessionManager.getSessionId()` in a
  module-level `Map`, not a single global — subagents/task children get their
  own session ids and must not share one pet clock.

## Bun.$ shell result field-name trap

`Bun.$` (aka `Bun.$`cmd`.quiet().nothrow()`) result objects expose the exit
code as **`exitCode`**, not `code`:

```ts
const r = await Bun.$`some-command`.quiet().nothrow();
r.code;      // undefined — always! `code !== 0` silently always true.
r.exitCode;  // the real exit code.
```

Destructuring `const { code } = await Bun.$...` silently compiles fine (no
type error caught it in this case) and makes every `code !== 0` check
permanently true, so every shell invocation looks like a failure even when it
actually succeeded — and if the failure path is wired to a UI notification
that's a no-op in headless/print mode (`ctx.hasUI === false`), the bug is
**completely silent**: no error, no output, just missing side effects (in this
case: ImageMagick frame-slicing silently "never running"). Always destructure
`exitCode`, and when debugging a Bun.$-based extension feature that seems to
do nothing, check this first before anything else.

## Verifying a terminal-graphics feature without eyes on the screen

`hub logs` on a `hub start`'d interactive TUI process dumps raw terminal
bytes as a scrollback capture — actual pixel graphics won't render in that
text dump, but the **escape sequences prove the code path fired**: for Kitty
Unicode-placeholder graphics look for the literal `U+10EEEE` placeholder
character repeated in a row (one per cell) with row/column diacritics
attached — appearing repeatedly over time on a schedule confirms the
animation loop is actually ticking and re-rendering, which is the strongest
evidence obtainable without a real screenshot.
