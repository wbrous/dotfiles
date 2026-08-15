---
name: quickshell-listview-anchored-toast-stack-animation
description: "Use when implementing or debugging an animated, anchor-pinned stack of items in QML/Quickshell (e.g. a notification toast stack anchored bottom-right or top-right) where new items must join without displacing existing ones, removals must slide survivors into the freed gap, and the stack must support mirroring between top- and bottom-anchored orientations. Covers why ListView's addDisplaced/removeDisplaced and a plain Column+Behavior-on-y both fail for this, the manual Item+Repeater+relayout() replacement, and the \"flies in from off-screen\" bug caused by reading a layer-shell window's height before it's been mapped."
---

## Problem

A stack of cards pinned to one screen corner (e.g. bottom-right), where:
- New cards join at the "open end" (opposite the anchor) WITHOUT moving any existing card, not even instantly.
- Removing a card slides only the cards between it and the open end into the gap; cards on the anchor side of it don't move.
- The whole thing must mirror correctly if the anchor flips (e.g. bar moves from top to bottom, so toasts flip from bottom-right to top-right).

## Why the obvious approaches fail

1. **`Column` + `Behavior on y`**: a positioner (`Column`, `ListView`, `Row`, `Grid`) writes each child's `y` directly via `setGeometry`, which bypasses the property binding system — `Behavior on y` never fires for positioner-managed children. Silent failure: nothing animates, ever.

2. **`ListView` with `addDisplaced`/`removeDisplaced` transitions**: these ARE real Qt Quick properties (Qt 5.13+) and DO fire. But the container itself is typically `height: contentHeight` + `anchors.bottom` so it hugs the anchor tightly (for a clean click-through mask). Every time content height changes (add or remove), the anchor makes the container's own top-left jump *instantly* (unanimated) in the same frame the child transitions try to animate `y`. The instant anchor-driven jump and the animated child-y fight each other: you get "jumps immediately to final screen position, then visibly slides away from it and back" — looks like items are sliding up/down from the wrong place even though the final result is correct.

## The fix: manual Item + Repeater + relayout()

Replace the positioner with a plain `Item` (fixed geometry — anchored so its OWN size never changes with content, e.g. `anchors.top` + `anchors.bottom` filling the whole available window) containing a `Repeater`. Each delegate gets its own `y` as a plain property (`slotY`) driven by a `relayout()` function you call manually, plus `Behavior on y` (this works now because nothing but your own JS ever writes `slotY`).

```qml
Item {
  id: stack
  anchors.top: parent.top; anchors.bottom: parent.bottom   // fixed frame — parent.height never changes with content
  anchors.right: parent.right
  width: 380
  property real contentTotal: 0
  readonly property bool topAnchored: /* derive from your actual anchor config */

  // Repack from the anchor edge outward. The item nearest the anchor is
  // always the OLDEST (nothing ever pushes from the anchor side — new items
  // only ever join at the open end). The NEWEST is always farthest from the
  // anchor (open end). This ordering choice is what makes "new item never
  // displaces anyone" and "removal only moves items toward the open end of
  // the removed one" fall out for free — no anchor-side special casing needed.
  function relayout() {
    if (stack.height <= 0) return   // see "off-screen fly-in" bug below
    var n = repeater.count, gap = 8, acc = 0
    for (var r = 0; r < n; r++) {
      var k = n - 1 - r   // r=0 -> oldest (anchor side), r=n-1 -> newest (open end)
      var d = repeater.itemAt(k)
      if (!d) continue
      d.slotY = stack.topAnchored ? acc : (stack.height - acc - d.height)
      if (!d.animateSlotted) d.animateSlotted = true   // see below
      acc += d.height + gap
    }
    stack.contentTotal = Math.max(0, acc - gap)
  }
  onHeightChanged: relayout()   // catches late-resolving window geometry

  Repeater {
    id: repeater
    model: yourModel
    onCountChanged: stack.relayout()
    delegate: Item {
      property real slotY: 0
      property bool animateSlotted: false
      y: slotY
      height: /* content implicit height */
      Behavior on y {
        enabled: animateSlotted
        NumberAnimation { duration: 300; easing.type: Easing.OutQuad }
      }
      onHeightChanged: stack.relayout()   // repack when content grows/shrinks
      Component.onCompleted: Qt.callLater(stack.relayout)
    }
  }
}
```

Key correctness proof (do this algebra before trusting any variant): with `rank(k) = n-1-k` (oldest=rank0=anchor side, newest=rank(n-1)=open end), a newly-appended item is always the highest rank, so it never appears in any *existing* item's accumulated-height sum — existing items' `slotY` targets are provably unchanged when something is added. On removal, only items with rank > the removed item's rank (i.e. on the open-end side) have their accumulated sum decrease — those are exactly the ones that should slide toward the anchor to close the gap; anchor-side items are provably unaffected.

For a tight click-through mask (Quickshell `mask: Region { item: ... }`), do NOT point it at the fixed-size frame (that would capture a full-height/width click-blocking strip) — add a small companion `Item` sized to `contentTotal` and positioned at the anchor edge, and mask that instead. It can jump instantly on resize (no animation needed, it's invisible/hit-test-only).

## The "flies in from off-screen" bug

On a Wayland layer-shell surface (Quickshell `PanelWindow`) that starts `visible: false` and only becomes `visible: true` when the model goes from empty to non-empty, the window's real height can read `0` for one or more ticks after `visible` flips — the compositor hasn't finished the configure round-trip yet. If `relayout()` runs during that window using `stack.height` (fixed-frame reference height) while it's still `0`, it computes a garbage position (e.g. large negative `y`, far off-screen). If `animateSlotted` is already `true` by the time a later `relayout()` corrects it with the real height, `Behavior on y` animates the huge jump from garbage to correct — visually "flies in from way off-screen" on literally the first item shown after a cold start. Subsequent items never show it because the window is already mapped by then.

Fix with two rules together:
1. `relayout()` bails out entirely (no assignment at all) if the fixed frame's height is `<= 0`.
2. `onHeightChanged: relayout()` on the fixed frame, so whenever the compositor finally reports real geometry, everything recomputes.
3. Flip each delegate's `animateSlotted` (the thing that enables `Behavior on y`) INSIDE `relayout()`, right after that delegate receives its first valid, height-correct position — never on a fixed timer/`Qt.callLater` guess. Enabling a `Behavior` never itself animates (only future changes to the bound property do), so this guarantees no delegate can ever be caught transitioning from a garbage position.

## Debugging technique

Screenshot timing (`grim` full-screen capture, ~150-200ms per shot) is too coarse to catch a 180-300ms animation naturally. Temporarily multiply your fade/slide durations by ~10x (e.g. 180ms → 2500ms), restart the shell, burst-capture with `grim` at ~0.3s intervals, crop to the toast region with `magick -crop WxH+X+Y`, and eyeball frame-by-frame. Revert the durations and restart again before finishing. `grim -g "X,Y WxH"` region syntax was unreliable in this environment — full-screen capture + `magick -crop` was the reliable path.
