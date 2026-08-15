---
name: omarchy-notifications-plugin-architecture
description: "Use when editing or debugging the user's customized omarchy notification plugin (wils.notifications clone): its architecture, the max-3 queue + 250ms pacing, right-click snooze, the bottom-right anchored/reflow popup stack, the \"+N more notifications\" overflow indicator, and the QML gotchas that break edits (delegate-scope service id resolution, overlay id availability, hot-reload races, animate-on-visible-toggle traps)."
---

The user's customizations live in the **user-owned clone**, NOT the packaged copy:

```
~/.config/omarchy/plugins/wils.notifications/     # EDIT HERE
/usr/share/omarchy/shell/plugins/notifications/   # READ-ONLY original (never edit)
```

Created via `omarchy plugin clone omarchy.notifications` (shell.json switched to `wils.notifications`, original disabled). `omarchy plugin remove wils.notifications` reverts to stock (cloneSourceRestores). Plugin hot-reloads on save under ~/.config/omarchy/plugins/, but **hot-reloads are flaky** — after edits, `omarchy restart shell` is the reliable path.

## Current custom behavior (all in Service.qml)

1. **Bottom-right toasts, anchor-flip aware** — `popupColumn` is a *fixed-size* frame (`anchors.top` + `anchors.bottom`, bound to the window, which never resizes) — NOT sized to content. Binding the frame's own height/position to content was the original bug: it shifted the anchor point instantly on every add/remove while each card's `y` animated separately, producing "jumps then slides back". Card `y` is computed purely by `relayout()` walking from the anchor edge outward: the item nearest the anchor is always the OLDEST, the newest is always at the open end (farthest from anchor). A new arrival is appended past every existing card in that walk, so existing cards' positions never change on arrival — only a removal shifts cards on the open-end side of the removed one. Everything is generalized off `popupColumn.topAnchored` (read from `popupPlacement.anchors.top`) so flipping the popup corner mirrors all the math automatically.
2. **Right-click on a toast = clear ALL + start snooze** (`onDismissAllRequested: service.snoozeAndClear()` on the NotificationCard delegate). snoozeAndClear() runs `startSnooze()` FIRST then `clearPopups()` — order matters so the clear doesn't flush the backlog.
3. **Snooze**: 10s pause (`snoozeIdleMs: 10000`), extended while pointer is in the bottom-right snooze overlay zone (`snoozeZoneHovered` from the overlay MouseArea) or clicks there; ends via `snoozeIdleTimer` when pointer has been out of zone 10s → then `flushPending()`.
4. **Max-3 display queue** (`maxVisiblePopups: 3`): if 3 toasts are up OR snoozing, new notifications go to `pendingQueue` (never dropped). Released as slots free, paced **250ms apart** (`pendingEmitTimer`). DND (`doNotDisturb`) still silences (skips) — only the snooze queues.
5. **`displayedCount`** is a synchronous counter mirroring on-screen toasts (popupModel.count lags because inserts are deferred via Qt.callLater). ALL cap checks use `displayedCount`, not `popupModel.count`.
6. **"+N more notifications" overflow indicator** (`components/OverflowIndicator.qml` + `overflowIndicator` in Service.qml): a one-line pseudo-toast shown when `pendingQueue` holds more than fits on screen. `queuedCount` is a synchronous mirror of `pendingQueue.length`, kept in sync manually at every mutation site — `pendingQueue.push`/`.shift()` mutate in place and do NOT fire `onPendingQueueChanged`, so nothing reactive can hang off that property directly. The indicator is positioned by `relayout()` as one more step past the newest real card in the same open-end walk (so it renders on TOP of the stack when bottom-anchored, flips to the bottom when top-anchored, matching item 1's anchor-flip design). Its visibility is driven by `visible: opacity > 0.001` (NOT a hard `visible: count>0` toggle) — see gotcha below.
7. **First-toast-after-cold-window jump**: `popupColumn.height` can read `0` for a beat while the layer-shell surface is still being mapped (only around the very first toast ever, before the window has ever been visible). `relayout()` bails out entirely if `popupColumn.height <= 0` rather than computing a garbage off-screen position, and `onHeightChanged: relayout()` reruns it the moment real geometry arrives. Each card's `Behavior on y` (`animateSlotted`) is only flipped true *inside* `relayout()`, right after that specific card receives its first real, height-valid position — so turning the animation on can never itself be the thing that animates a stale/garbage spot.

## Architecture map (Service.qml)

- `popupModel` (ListModel) + `popupColumn` (fixed-size `Item`, NOT sized to content) inside a per-screen PanelWindow (Variants over Quickshell.screens). `popupRepeater` (Repeater over popupModel) holds the card delegates; `overflowIndicator` is a sibling Item after the Repeater.
- `handleNotification` → DND-silence? queue (snooze/full)? else `showPopup`.
- `showPopup(notification, snapshot)` — bumps displayedCount, persists, callLater inserts + refreshPopup.
- `enqueuePending` / `flushPending` / `maybeReleasePending` (timer-paced) — backlog machinery. Every mutation of `pendingQueue` must also update `queuedCount = pendingQueue.length` immediately after, by hand.
- `removePopup` decrements displayedCount, then calls `flushPending()`; also `removePopupsByOriginalId` decrements per removed row (replaces_id supersession).
- Snooze overlay: separate per-screen PanelWindow (`omarchy-notification-snooze` namespace), `mask: Region { item: snoozeZone }`, MouseArea `snoozeHover` with hoverEnabled.

## QML gotchas that WILL break edits (learned the hard way)

- **`service.` id references from Repeater delegates are unreliable** — a multi-statement handler `onX: { service.a(); service.b() }` throws intermittent `ReferenceError: service is not defined` at runtime. Fix: define the sequence as a root-scope function and call it single-expression: `onDismissAllRequested: service.snoozeAndClear()`.
- **Overlay ids are NOT resolvable before the overlay is visible.** `startSnooze()` must NOT read `snoozeHover.containsMouse` — the overlay doesn't exist until snoozeActive=true → ReferenceError on first right-click. The overlay's own `onContainsMouseChanged` writes `service.snoozeZoneHovered` instead.
- **Never bind a positioning frame's own size/position to its content** if children need independently-animated `y`. Content-bound geometry moves the anchor instantly while a child's `Behavior on y` animates separately — the two fight (jump-then-slide-back). Use a frame fixed to something that never changes (the window), and compute each child's `y` purely from distance-to-anchor deltas.
- **A hard `visible: someCondition` toggle kills any opacity fade-out on the same item** — `visible:false` hides it instantly regardless of an in-flight `Behavior on opacity`. Fix: gate visibility off the animated value instead — `opacity: active ? 1 : 0` (Behavior-animated) + `visible: opacity > 0.001`. Since that computed `visible` settles a tick *after* the driving `active`/`count` flag changes, hook `onVisibleChanged` too (not just `onActiveChanged`) wherever something (like a layout's `relayout()`) needs to react to the item actually starting/stopping rendering.
- **Hot-reload races**: editing Service.qml can throw transient ReferenceError/SyntaxError at line numbers that shift, or report a stale plugin-load-failed error from a mid-edit partial write; a full `omarchy restart shell` clears it. Check `journalctl --user | grep -iE "error|syntax"` after restart (empty = clean) — if an error persists after a clean restart, re-verify actual brace balance with a character-level awk scan (`grep -c` on `{`/`}` is unreliable — it counts *lines containing* a brace, not brace occurrences, and multi-brace lines silently break the count).
- **`omarchy-shell -q notifications <method>` does NOT echo return values** (even nonexistent methods exit 0). Verify by side effects (live popup files under ~/.local/state/omarchy/notifications/, history under .../history/) not stdout.
- QML `console.log` is not visible in journalctl; write to a file via a Process if you need debug output.
- Live popup files lag/mislead: measure cap with file-count bursts (send 12+ rapid, sample `ls ~/.local/state/omarchy/notifications/*.json | wc -l` → must stay ≤3).
- **Screenshot/behavioral verification of animation timing**: temporarily multiply `fadeMs`/`slideMs` by ~10-15x (e.g. 180→2500), restart, capture a burst of `omarchy capture screenshot --fullscreen` at short sleep intervals to catch mid-animation frames, verify positions with `grim -g "<w>x<h>+<x>+<y>"` crops of the toast corner, then restore the original values and restart again before declaring done. Real-speed animation (150-300ms) is too fast for `omarchy capture` (~1-2s per shot) to ever catch mid-transition.

## Verification quick path

```bash
omarchy restart shell
notify-send "Test" "msg" --expire-time=60000   # long-lived so it lingers
# cap: rapid burst (for i in $(seq 1 12); notify-send ...; done), sample live file count ≤3
# pacing: dismissOne then measure ms until next queued toast's file appears (~250-300ms)
# overflow indicator: burst > 3, confirm "+N more notifications" appears above/below the 3
#   per anchor direction, and N == sent - 3; dismiss one, confirm N decrements live
omarchy-shell -q notifications dismissAll       # clear all
```
