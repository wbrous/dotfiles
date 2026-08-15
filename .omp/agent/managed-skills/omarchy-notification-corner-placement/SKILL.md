---
name: omarchy-notification-corner-placement
description: "Use when moving Omarchy notification toasts to a different corner (bottom-right etc.), or customizing notification behavior in the cloned omarchy.notifications plugin — right-click clear-all + snooze, max-3 backlog queue. Covers clone workflow and the QML gotchas that break these edits."
---

# Omarchy Notifications Customization

For end-user changes to Omarchy notification toasts: corner placement, right-click behavior, snooze, display caps. The plugin lives under `wils.notifications` after cloning. NEVER edit `/usr/share/omarchy/shell/plugins/notifications/` — that's the packaged original.

## Clone the plugin (first step)

```bash
omarchy plugin clone omarchy.notifications
# -> ~/.config/omarchy/plugins/wils.notifications/  (git-tracked user copy, survives updates)
# shell.json auto-switches: wils.notifications enabled, omarchy.notifications disabled.
# Revert later: omarchy plugin remove wils.notifications (cloneSourceRestores brings original back).
```

Files: `Service.qml` (daemon + popup UI), `NotificationLogic.js` (snapshot/persistence helpers), `components/NotificationCard.qml` (card visuals + mouse handling).

## After ANY edit: full shell restart required

Hot-reload happens on save but can leave transient `ReferenceError: service is not defined` during mid-reload incubation. **Always** finish with:

```bash
omarchy restart shell   # then check: journalctl --user -n 30 | grep -i "referenceerror\|typeerror"
```

A clean cold load should show zero ReferenceErrors (the QDBus portal WARN is unrelated noise).

## Corner placement (bottom-right)

Two COUPLED spots must both change (popup column ignores the placement anchors):

1. `NotificationLogic.js` → `popupPlacement()`: `anchors: { top: true, ... }` → `{ bottom: true, ... }` and swap margin logic (`bottom: position === "bottom" ? clearance : gap`).
2. `Service.qml` → `popupColumn` (ColumnLayout): `anchors.top: parent.top` → `anchors.bottom: parent.bottom`, `topMargin` → `bottomMargin`.

## Right-click = clear all (+ optional snooze)

`NotificationCard.qml`: `MouseArea` with `acceptedButtons: Qt.LeftButton | Qt.RightButton`; right-click emits a signal (e.g. `dismissAllRequested`), left-click keeps `cardClicked`. Service delegate wires `onDismissAllRequested: service.snoozeAndClear()`.

## CRITICAL QML gotchas (all burned in this repo)

1. **No multi-statement signal handlers referencing the root id from Repeater delegates.**
   `onX: { service.a(); service.b() }` inside a `Repeater` delegate throws `ReferenceError: service is not defined` intermittently at load AND runtime. Single-expression handlers (`onX: service.func()`) work. Fix: put the sequence in a ROOT-scope function (`function snoozeAndClear() { ... }`) and call it as ONE expression from the delegate.
2. **Never reference ids of objects that may not be instantiated.**
   Reading `snoozeHover.containsMouse` (a MouseArea inside an overlay that's `visible: false` until toggled) from a root-scope function crashes at runtime: `ReferenceError: snoozeHover is not defined`. Have the overlay report state into root properties via its own signal handlers instead; default to safe values.
3. **`ListModel.count` lags reality.** Model inserts are deferred via `Qt.callLater` (to avoid Repeater incubation crashes), so a cap check on `popupModel.count` over-releases under bursts. Maintain a synchronous `displayedCount` counter: `++` in showPopup, `--` in removePopup/removePopupsByOriginalId, and drive all caps/flushes from it.
4. **`omarchy-shell -q notifications <method>` never echoes return values** (even unknown methods exit 0). Verify IPC-driven behavior via observable side effects (popup state files under `~/.local/state/omarchy/notifications/`, history dir), never via CLI stdout. Live popup files lag async cleanup — prefer a burst test with multiple 1s samples over a single count.
5. Duplicate ids across `Variants { model: Quickshell.screens }` instances are fine with ONE monitor; multi-monitor setups need per-screen id discipline.

## Snooze + max-3 backlog queue design (reference)

- Right-click → `startSnooze()` then `clearPopups()` (order matters: snooze FIRST so clear's flush doesn't release backlog during the pause).
- Snooze = pause + hold: arriving notifications go to `pendingQueue` (never skipped). DND (`doNotDisturb`) is the only thing that still silences/skips.
- Snooze hot-zone: transparent `PanelWindow` over the toast corner, `mask: Region { item: zone }` makes only the zone input-hitting; MouseArea `hoverEnabled` reports `containsMouse` → keeps snooze alive; clicks restart the 10s idle-out timer; snooze lifts only after cursor out of zone 10s (`Timer { running: snoozeActive && !snoozeZoneHovered }`), then `flushPending()`.
- Max-3 queue: `maxVisiblePopups = 3`; if snooze active OR `displayedCount >= 3` → enqueue; flush on every `removePopup` and on snooze end (up to 3 at a time, rest wait for slots). Queued items are in-memory only — lost on shell restart.
- Restore on startup also caps at `maxVisiblePopups`.

## Verification pattern

- Burst test: `for i in $(seq 1 12); do notify-send "T$i" "x" --expire-time=2000; sleep 0.1; done` then sample live popup file count every 1s — must never exceed 3.
- To prove suppression/snooze works: arm snooze via a TEMPORARY IPC method (add `function snoozeOn(): string { service.startSnooze(); return "ok" }` to the IpcHandler, call `omarchy-shell -q notifications snoozeOn`, remove after) then send a notification and check it does NOT create a live popup file.
- Always remove temp IPC/debug methods before finishing; restart shell; confirm zero ReferenceErrors.
