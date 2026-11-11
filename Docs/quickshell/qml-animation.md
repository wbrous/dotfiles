# QML anchored-stack animation

How to build an animated toast/card stack pinned to a screen corner in QML/Quickshell without position glitches.

## Positioner-managed children ignore `Behavior on y`

**Symptom:** a `Column`/`ListView`/`Row`/`Grid` of cards never animates position changes despite `Behavior on y`.

**Cause:** positioners write each child's `y` via `setGeometry`, bypassing property bindings — `Behavior on y` never fires. Silent failure.

**Fix:** don't rely on a positioner for animated children. Use a plain `Item` frame with a `Repeater`, each delegate owning a plain `slotY` property set by a manual `relayout()` function; `Behavior on y` works because only your own JS writes `slotY`.

## Anchored content-sized frame fights child animation ("jump then slide")

**Symptom:** items instantly jump to their final screen position, then visibly slide away and back; or "slides up from the bottom" artifacts on add/remove.

**Cause:** container is anchored to an edge (`anchors.bottom`) AND its height is bound to content (`height: contentHeight`). On content change the anchor repositions the container's top-left instantly (synchronous binding) while child `y` animates over ~300ms — instant jump and animated chase disagree.

**Fix:** decouple the animated coordinate system from anchor/resize machinery:

1. Fixed positioning frame: `anchors.top` + `anchors.bottom` filling the whole window height (window itself is fixed-size overlay). Never bind frame height to content.
2. Each child's `y` = distance from the anchor edge, walking outward from the anchor. Bottom-anchored: `y = frameHeight - distFromAnchor - itemHeight`. Top-anchored: `y = distFromAnchor`.
3. Ordering: nearest the anchor is always the OLDEST (new items join at the open end). Prove it: with `rank(k) = n-1-k`, a new append is always the highest rank, never in any existing item's accumulated-height sum — existing `slotY` targets provably unchanged on add. On removal only items on the open-end side of the removed one shift toward the anchor.
4. Generalize direction behind one boolean (`topAnchored`) so flipping the corner mirrors the math.

```qml
Item {
  id: stack
  anchors.top: parent.top; anchors.bottom: parent.bottom
  anchors.right: parent.right
  width: 380
  property real contentTotal: 0
  readonly property bool topAnchored: /* from anchor config */

  function relayout() {
    if (stack.height <= 0) return   // layer-shell geometry not ready yet
    var n = repeater.count, gap = 8, acc = 0
    for (var r = 0; r < n; r++) {
      var k = n - 1 - r
      var d = repeater.itemAt(k)
      if (!d) continue
      d.slotY = stack.topAnchored ? acc : (stack.height - acc - d.height)
      if (!d.animateSlotted) d.animateSlotted = true
      acc += d.height + gap
    }
    stack.contentTotal = Math.max(0, acc - gap)
  }
  onHeightChanged: relayout()

  Repeater {
    id: repeater
    model: yourModel
    onCountChanged: stack.relayout()
    delegate: Item {
      property real slotY: 0
      property bool animateSlotted: false
      y: slotY
      Behavior on y {
        enabled: animateSlotted
        NumberAnimation { duration: 300; easing.type: Easing.OutQuad }
      }
      onHeightChanged: stack.relayout()
      Component.onCompleted: Qt.callLater(stack.relayout)
    }
  }
}
```

Note: `ListView` `addDisplaced`/`removeDisplaced` (Qt 5.13+) ARE real and do fire — but they suffer the same anchor-jump fight when the container is content-sized and anchored, so the manual approach is still preferred.

## Tight click-through mask


**Fix:** add a small companion `Item` sized to `contentTotal`, positioned at the anchor edge, and mask that instead. It may jump instantly (invisible, hit-test only).

## First toast "flies in from off-screen"

**Symptom:** first item after a cold start animates from far off-screen.

**Cause:** on a layer-shell `PanelWindow` starting `visible: false`, the window height reads `0` for ticks after `visible` flips (compositor configure round-trip pending). `relayout()` computing against height 0 yields garbage (large negative `y`); when corrected later, `Behavior on y` animates the huge jump.

**Fix (all three together):**
1. `relayout()` bails with no assignment if frame height `<= 0`.
2. `onHeightChanged: relayout()` on the frame recomputes when real geometry arrives.
3. Flip each delegate's `animateSlotted` inside `relayout()` right after its first valid position — never on a timer. Enabling a `Behavior` never animates by itself; only future changes do.

## Verifying animations visually

Real 150–300ms animations are too fast for `grim` (~150–200ms/shot). Temporarily multiply fade/slide durations ~10x (180ms → 2500ms), restart the shell, burst-capture full-screen `grim` at ~0.3s intervals, crop the toast region with `magick -crop WxH+X+Y`, eyeball frame-by-frame. Revert durations and restart. (`grim -g` region syntax was unreliable here — full-screen + `magick -crop` is the reliable path.)

_Migrated from: quickshell-listview-anchored-toast-stack-animation, quickshell-qml-anchor-resize-animation-jump_
