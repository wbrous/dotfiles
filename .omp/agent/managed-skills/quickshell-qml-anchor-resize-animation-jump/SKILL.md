---
name: quickshell-qml-anchor-resize-animation-jump
description: "Use when a QML/Quickshell Item or ListView animates a y/position Behavior while also being anchored (e.g. anchors.bottom) with its height bound to content size (e.g. height: contentHeight or a computed total) — symptoms: items appear to instantly jump then animate back, \"slides up from the bottom\" artifacts, or displacement animations fighting layout. Applies to the wils.notifications Omarchy shell plugin (~/.config/omarchy/plugins/wils.notifications/Service.qml) and any similar anchored, content-sized animated stack."
---

## The bug pattern

A container is anchored to a screen edge (e.g. `anchors.bottom: parent.bottom`)
AND its `height` is bound to a value that changes with content (e.g.
`height: contentHeight` or a manually computed `contentTotal`). Meanwhile,
child items animate their own `y` via `Behavior on y { NumberAnimation {...} }`.

When content changes (an item added/removed), the anchor+height binding
repositions the container's top-left corner **instantly** (property bindings
are synchronous), while the child's `y` **animates** over some duration. The
two updates disagree on timing: the container jumps immediately, and the
child's animated `y` chases it back into place — producing a visible
"jump then slide" glitch, often perceived as "it slides up from the bottom"
or similar nonsensical direction.

## The fix

Decouple the animated coordinate system from the anchor/resize machinery:

1. Make the positioning frame's own geometry **fixed** — anchor it to
   something that never resizes (e.g. `anchors.top` + `anchors.bottom` to
   fill the parent window's full height, when the window itself is a
   fixed-size overlay). Do NOT bind its `height` to content.
2. Compute each child's `y` as a **distance from the anchor edge**, walking
   outward from the anchor (the item nearest the anchor point never moves
   unless something between it and the anchor is removed). For a
   bottom-anchored stack: `y = fixedFrameHeight - marginBottom - distFromAnchor - itemHeight`.
   For top-anchored: `y = marginTop + distFromAnchor`.
3. Prove correctness algebraically before testing: an item's distance from
   the anchor only changes when something *between it and the anchor* is
   added/removed. An item added at the far (open) end never changes any
   existing item's distance-from-anchor — so it can never move existing
   items, even with the animation `Behavior` left enabled.
4. If a tight click-through mask is needed (e.g. `mask: Region { item: ... }`
   in a Quickshell `PanelWindow`), do NOT mask the fixed full-size frame —
   add a small companion `Item` sized/positioned to the actual content
   bounds (this one CAN jump/resize instantly since it has no visual
   representation) and mask that instead.
5. Generalize the anchor direction behind one boolean (e.g. `topAnchored`)
   so flipping which edge the stack is pinned to mirrors all the math
   automatically instead of requiring parallel code paths.

## Verifying the fix (screenshot timing gotcha)

Real animations (150-300ms) are too fast to catch reliably with `grim`
screenshot bursts (~100-150ms per capture on this machine). To verify
visually:

1. Temporarily multiply the animation durations by ~10x (e.g. 180ms → 2500ms)
   directly in the QML file.
2. `omarchy restart shell`, trigger the transition, burst-capture with
   `grim /tmp/frame_N.png` (full-screen; `grim -g "X,Y WxH"` region syntax
   was unreliable on this HiDPI setup — capture full screen and crop after
   with `magick in.png -crop WxH+X+Y out.png`).
3. Read the cropped frames to confirm: existing items are pixel-identical
   across an addition; displaced items smoothly interpolate across a removal.
4. Restore the original durations, restart, and re-verify no regressions at
   real speed (`qmllint` + `journalctl --user` grep for QML errors).

## Large in-file QML block replacement gotcha

The `edit` tool's exact-string matching is fragile against large multi-line
QML blocks (whitespace/line-count drift after several prior edits). For
replacing a large, well-bounded block (e.g. an entire `Item { ... }` or
`ListView { ... }`), it's more reliable to locate exact 1-indexed line
boundaries with a small Python brace-depth scanner, then splice the
replacement in with a Python script that rewrites the file's line list —
rather than fighting `edit`'s fuzzy-match threshold on a huge `old_string`.
