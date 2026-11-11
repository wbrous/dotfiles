# Omarchy notifications plugin (wils.notifications clone)

Customizing the Omarchy notification toasts: corner placement, right-click snooze, max-3 queue, pacing, overflow indicator, IPC, and the QML gotchas that break edits.

## Clone workflow

**Symptom:** edits to notification behavior don't survive updates, or you're tempted to edit the packaged copy.

**Cause:** `/usr/share/omarchy/shell/plugins/notifications/` is the packaged original.

**Fix:** clone once and edit the user copy:

```bash
omarchy plugin clone omarchy.notifications
# -> ~/.config/omarchy/plugins/wils.notifications/ (git-tracked, survives updates)
# shell.json auto-switches: wils.notifications enabled, omarchy.notifications disabled.
# Revert: omarchy plugin remove wils.notifications (cloneSourceRestores brings original back).
```

Files: `Service.qml` (daemon + popup UI), `NotificationLogic.js` (snapshot/persistence helpers), `components/NotificationCard.qml` (card visuals + mouse handling).

After ANY edit, hot-reload can leave transient `ReferenceError: service is not defined` mid-incubation. Always finish with:

```bash
omarchy restart shell
journalctl --user -n 30 | grep -i "referenceerror\|typeerror"
```

A clean cold load shows zero ReferenceErrors (the QDBus portal WARN is unrelated noise). Hot-reloads are flaky — `omarchy restart shell` first before auditing logic when behavior looks stale with no error trace.

## Corner placement (bottom-right)

**Fix:** two coupled spots must both change (popup column ignores placement anchors):

1. `NotificationLogic.js` → `popupPlacement()`: `anchors: { top: true, ... }` → `{ bottom: true, ... }`, swap margin logic.
2. `Service.qml` → popup column: `anchors.top: parent.top` → `anchors.bottom: parent.bottom`, `topMargin` → `bottomMargin`.

The popup stack itself is a fixed-size frame (`anchors.top` + `anchors.bottom` bound to the window, never to content); card `y` is computed by `relayout()` walking from the anchor edge outward, generalized off `topAnchored`. See `qml-animation.md` for the animation math.

## Right-click = clear all + snooze

**Fix:** `NotificationCard.qml` `MouseArea` with `acceptedButtons: Qt.LeftButton | Qt.RightButton`; right-click emits e.g. `dismissAllRequested`, left-click keeps `cardClicked`. Service delegate wires `onDismissAllRequested: service.snoozeAndClear()`.

Snooze design (reference): right-click runs `startSnooze()` FIRST then `clearPopups()` (order matters so the clear doesn't flush the backlog). Snooze = pause + hold: arrivals go to in-memory `pendingQueue` (never skipped, lost on restart). DND is the only thing that still silences. Snooze hot-zone: transparent `PanelWindow` over the toast corner, `mask: Region { item: zone }`; `hoverEnabled` MouseArea keeps snooze alive while hovered; 10s idle-out timer (`running: snoozeActive && !snoozeZoneHovered`) then `flushPending()`.

## Max-3 queue, 250ms pacing, overflow indicator

- `maxVisiblePopups = 3`; if snoozing or `displayedCount >= 3`, enqueue. Flush on every `removePopup` and snooze end, up to 3 at a time, paced 250ms apart (`pendingEmitTimer`).
- `displayedCount` is a synchronous counter (`++` in showPopup, `--` in removePopup); `ListModel.count` lags reality (inserts deferred via `Qt.callLater`), so all caps use `displayedCount`.
- `"+N more notifications"` overflow indicator (`components/OverflowIndicator.qml`): shown when the pending queue holds more than fits. `queuedCount` mirrors `pendingQueue.length` by hand at every mutation (`push`/`shift` don't fire change signals). Positioned by `relayout()` one step past the newest card. Visibility driven by `visible: opacity > 0.001`, never a hard `visible: count>0` toggle (a hard toggle kills the opacity fade — see gotchas).
- Restore on startup also caps at `maxVisiblePopups`.

## DND vs snooze — check DND first

**Symptom:** `notify-send` produces no live popup files under `~/.local/state/omarchy/notifications/*.json` and nothing in `history/`.

**Cause:** DND is a separate silence path with zero on-disk trace for ephemeral notifications — don't assume a snooze/queue bug.

**Fix:**

```bash
omarchy-shell notifications isDnd     # NOT -q, so output is visible
omarchy-shell notifications setDnd false  # restore prior value after debugging
```

DND (`doNotDisturb`) and snooze (`snoozeActive`) are independent persisted properties checked separately in `handleNotification()`. If a report says they "seem coupled", grep `doNotDisturb` to confirm — it's symptom-conflation, not code coupling.

## Snooze timer stuck forever

**Symptom:** snooze never expires.

**Cause:** the idle-out timer only runs while the pointer is OUTSIDE the snooze zone; a cursor resting in the corner means the countdown never starts.

**Fix:** don't move the cursor via `hyprctl` (see below). Add/use a direct IPC method setting `service.snoozeActive = false` + `service.flushPending()` unconditionally, bypassing timer/hover state.

## IPC debugging

`omarchy-shell -q <target> <method>` suppresses ALL output including errors (exit 0 even for bogus methods). When debugging, drop `-q` to see real returns:

```bash
omarchy-shell notifications ping        # "ok" if target/handler alive
omarchy-shell notifications isDnd       # real state
```

Known IPC methods include `invokeLast`, `dismissOne`, `dismiss(summary)`, `isDnd`, `toggleDnd`, `setDnd`, `showHistory`, `clear`, `dismissAll`, `ping`. Temp debug methods (e.g. `snoozeOn`) must be removed before finishing; restart and confirm zero ReferenceErrors.

This machine's `hyprctl dispatch` args are evaluated as Lua (`hl.dispatch(...)`), so `hyprctl dispatch movecursor 100 100` fails with `')' expected near '100'`. Don't guess quote/comma variants; read `~/.config/hypr/*.lua` for syntax or, better, add a direct-state-set IPC method instead of synthetic cursor moves. Toasts are bare layer-shell surfaces — no accessibility tree, and no mouse-click simulation exists here (`xdotool` fails under Wayland, `wtype` is keyboard-only). Verify clicks via IPC (`invokeLast`) + on-disk side effects, or ask the user to click.

## `omarchy-exec-argv` hint rename breaks left-click actions

**Symptom:** left-clicking an action toast (e.g. screenshot "click to edit") silently does nothing — falls through to the app-focus fallback.

**Cause:** upstream `omarchy-notification-send --exec` changed from single-string hint `omarchy-exec` (run via `Util.execDetached`) to JSON-array hint `omarchy-exec-argv` (run via `Util.execArgv`). The stock plugin updated in lockstep; a clone is a point-in-time copy and still reads the old key, so `entry.exec` is always empty.

**Fix:** grep `exec` across the whole plugin dir; rename `execFromHints` → `execArgvFromHints` reading `omarchy-exec-argv`, add `parseExecArgv` (JSON.parse + validate array/all-string/non-empty/no leading `-`, fails closed), rename the `exec` role to `execArgv` in roles/snapshot/history/exports, and in `invokeDefaultAction` use `NotificationLogic.parseExecArgv(entry.execArgv)` + `Util.execArgv(argv)` (lives in shared `qs.Commons`, always current). Verify with:

```bash
/usr/share/omarchy/bin/omarchy-notification-send "Test" "body" --expire-time=60000 \
  --exec bash -c "touch /tmp/exec_test_marker"
omarchy-shell notifications invokeLast
ls -la /tmp/exec_test_marker
```

## QML gotchas

- Multi-statement `onX: { service.a(); service.b() }` in a Repeater delegate throws intermittent `ReferenceError: service is not defined`. Put the sequence in a root-scope function, call it as one expression.
- Never reference overlay ids (e.g. `snoozeHover.containsMouse`) from root scope before the overlay is visible — `ReferenceError`. Have the overlay report state into root properties via its own handlers.
- Never bind a positioning frame's size/position to content when children animate `y` (jump-then-slide; see `qml-animation.md`).
- Hard `visible: someCondition` kills an opacity fade on the same item (`visible:false` hides instantly). Use `opacity: active ? 1 : 0` (Behavior-animated) + `visible: opacity > 0.001`; hook `onVisibleChanged` too since computed `visible` settles a tick after the flag.
- `grep -c` on `{`/`}` is unreliable for brace balance (counts lines containing braces, not occurrences); use a character-level scan.
- QML `console.log` is not visible in journalctl; write to a file via a Process for debug output.
- Live popup files lag async cleanup — burst-test with 1s samples, not single counts. If a burst shows 0 files, check DND/snooze first.

## Verification quick path

```bash
omarchy restart shell
notify-send "Test" "msg" --expire-time=60000
# cap: burst 12 rapid sends, live file count must stay <= 3
# pacing: dismissOne, next queued toast's file appears ~250-300ms later
# overflow: burst > 3 shows "+N more", N == sent - 3; dismiss one, N decrements
omarchy-shell -q notifications dismissAll
```

_Migrated from: omarchy-notification-corner-placement, omarchy-notif-dnd-snooze-debug, omarchy-notifications-plugin-architecture_
