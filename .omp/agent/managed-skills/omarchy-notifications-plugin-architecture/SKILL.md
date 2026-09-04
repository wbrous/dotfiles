---
name: omarchy-notifications-plugin-architecture
description: "Use when the user's customized omarchy notification plugin (wils.notifications clone): its architecture, the max-3 queue + 250ms pacing, right-click snooze, IPC handler methods and how to add new ones, keybind wiring in ~/.config/hypr/bindings.lua for notification actions, the bottom-right anchored/reflow popup stack, the \"+N more notifications\" overflow indicator, the QML gotchas that break edits, the DND bar-indicator breakage caused by cloning the notifications plugin (fixed via a wils.indicators clone using pluginRegistry.resolveEnabledId), and the omarchy-exec-argv hint rename that silently breaks left-click \"click to edit\" actions (e.g. screenshot toasts) when the clone falls behind a stock update."
---

The user's customizations live in the **user-owned clone**, NOT the packaged copy:

```
~/.config/omarchy/plugins/wils.notifications/     # EDIT HERE
/usr/share/omarchy/shell/plugins/notifications/   # READ-ONLY original (never edit)
```

Created via `omarchy plugin clone omarchy.notifications` (shell.json switched to `wils.notifications`, original disabled). `omarchy plugin remove wils.notifications` reverts to stock (cloneSourceRestores). Plugin hot-reloads on save under ~/.config/omarchy/plugins/, but **hot-reloads are flaky** — after edits, `omarchy restart shell` is the reliable path.

The user has verified against `~/.dotfiles` (a bare git repo, `--git-dir=$HOME/.dotfiles --work-tree=$HOME`) that this file's committed baseline is the source of truth — `git --git-dir=$HOME/.dotfiles --work-tree=$HOME diff -- .config/omarchy/plugins/wils.notifications/Service.qml` shows exactly what's been added on top of the "og code". Keep that diff minimal and match the user's explicit ask — do not bundle unrequested IPC methods or refactors into the same change; when the user says "add ONLY these N shortcuts", the diff must contain only what implements those N things. **Also do not auto-assume the dotfiles-autosync extension picks up config/plugin edits** — it only fires for managed-skills; after fixing/editing files under `.config/omarchy/plugins/`, `git add`+`commit` them into the dotfiles bare repo yourself (through the gitleaks pre-commit hook).

## KNOWN REGRESSION: `omarchy-exec-argv` hint rename breaks left-click actions

**Symptom**: left-clicking a toast that's supposed to run a command (e.g. the screenshot toast's "click to edit" / `Super+Alt+,`) does nothing — no error, no launched app, just silently falls through to the "focus the sending app" fallback (which itself does nothing useful for `app_name=omarchy-action` toasts since there's no window to focus).

**Root cause**: an upstream Omarchy update changed `/usr/share/omarchy/bin/omarchy-notification-send`'s `--exec` handling from a single shell-string hint (`omarchy-exec`, run via `Util.execDetached`) to a JSON-array argv hint (`omarchy-exec-argv`, run via `Util.execArgv`, safer — never touches a shell). The stock plugin (`/usr/share/omarchy/shell/plugins/notifications/`) was updated in lockstep, but a **cloned** plugin under `~/.config/omarchy/plugins/wils.notifications/` does NOT auto-update with system package upgrades — it's a point-in-time copy. If the clone still has the old single-string reader, `entry.exec` (looked up via hint key `omarchy-exec`) is always empty because the sender only ever sets `omarchy-exec-argv` now, and every click-action toast becomes silently inert.

**Diagnosis path that found this**: read `NotificationCard.qml`'s `onClicked` → `cardClicked` signal → `Service.qml`'s `invokeDefaultAction` (looked structurally correct in isolation) → grepped for the hint key name (`omarchy-exec`) across the whole clone (`NotificationLogic.js`'s `execFromHints`) → compared against the **stock** plugin's equivalent function with the same grep and found it reads `omarchy-exec-argv` instead, plus a `parseExecArgv` validator and `Util.execArgv` runner that don't exist in the clone at all. Confirming a hot-reload/restart isn't the cause (it wasn't — `omarchy restart shell` came up clean, no QML errors, bug persisted) was a useful early elimination step before finding the real hint-key mismatch.

**Fix** (grep `exec` across the whole plugin dir to find every touch point — do NOT assume `Service.qml` alone):
- `NotificationLogic.js`: rename `execFromHints(hints)` → `execArgvFromHints(hints)` reading hint `"omarchy-exec-argv"` instead of `"omarchy-exec"`; add `parseExecArgv(value)` (JSON.parse + validate: array, all-string, non-empty program, program doesn't start with `-`; returns `null` on any failure — fails closed on a malformed/tampered hint). Rename the `exec` role to `execArgv` in `POPUP_ROLES`, `snapshotOf()`, `historyEntry()`, and the exports object at the bottom.
- `Service.qml`: in `invokeDefaultAction`, replace `var command = String(entry.exec || "")` + `Util.execDetached(command)` with `var argv = NotificationLogic.parseExecArgv(entry.execArgv)` + `Util.execArgv(argv)`. Rename the two remaining `exec:`-keyed popupModel-entry literals (the restore-from-history entry and the synthetic "silenced notifications" glyph entry) to `execArgv:`. Update the doc comment above `invokePopupDefault` that names the role.
- `Util.execArgv` already exists in the **shared, non-cloned** `qs.Commons` module (`/usr/share/omarchy/shell/Commons/Util.qml`) — it's a system-shared import, not per-plugin-cloned, so it's always current; no need to vendor it.

**Verification recipe** (no UI automation needed — this plugin's toasts aren't reachable via computer-use/accessibility trees since they're bare wlroots layer-shell surfaces, not normal app windows):
```bash
omarchy restart shell   # confirm clean, no QML/journal errors
/usr/share/omarchy/bin/omarchy-notification-send "Test" "body" --expire-time=60000 \
  --exec bash -c "touch /tmp/exec_test_marker"
sleep 0.3
cat ~/.local/state/omarchy/notifications/<newest>.json   # confirm execArgv key is a populated JSON array, not exec:""
omarchy-shell notifications invokeLast   # fires the real click path (invokePopupDefault(0)) via IPC — returns "none" if popupModel is empty (toast already gone), "ok" on success
ls -la /tmp/exec_test_marker   # confirms the argv actually ran
```
Note: `omarchy-shell -q notifications <bogus-method-name>` exits 0 silently even for a method that doesn't exist on the IpcHandler (documented gotcha) — always use a *real* method name (check the `IpcHandler { target: "notifications" }` block for what's actually exposed, e.g. `invokeLast`, `dismissOne`, `dismiss(summary)`, `isDnd`, `toggleDnd`, `setDnd`, `showHistory`, `clear`, `dismissAll`, `ping`) and drop `-q` to see its actual string return, per the existing "does NOT echo return values" gotcha below.

## Current custom behavior (all in Service.qml)

1. **Bottom-right toasts, anchor-flip aware** — `popupColumn` is a *fixed-size* frame (`anchors.top` + `anchors.bottom`, bound to the window, which never resizes) — NOT sized to content. Binding the frame's own height/position to content was the original bug: it shifted the anchor point instantly on every add/remove while each card's `y` animated separately, producing "jumps then slides back". Card `y` is computed purely by `relayout()` walking from the anchor edge outward: the item nearest the anchor is always the OLDEST, the newest is always at the open end (farthest from anchor). A new arrival is appended past every existing card in that walk, so existing cards' positions never change on arrival — only a removal shifts cards on the open-end side of the removed one. Everything is generalized off `popupColumn.topAnchored` (read from `popupPlacement.anchors.top`) so flipping the popup corner mirrors all the math automatically.
2. **Right-click on a toast = clear ALL + start snooze** (`onDismissAllRequested: service.snoozeAndClear()` on the NotificationCard delegate). `snoozeAndClear()` (root scope, ~line 129) runs `startSnooze()` FIRST then `clearPopups()` — order matters so the clear doesn't flush the backlog. **This function is already fully modular and never reads or writes `doNotDisturb`** — snooze (`snoozeActive`) and DND (`doNotDisturb`) are two entirely separate persisted properties, checked independently in `handleNotification()` (DND check first at line ~280, snooze check at line ~295). They have never been combined in the committed code; if a user reports "snooze and DND seem coupled", it is almost certainly a *symptom-conflation* from debugging narrative, not an actual code bug — grep `doNotDisturb` across the whole file to confirm before touching anything.
3. **Snooze**: 10s pause (`snoozeIdleMs: 10000`), extended while pointer is in the bottom-right snooze overlay zone (`snoozeZoneHovered` from the overlay MouseArea) or clicks there; ends via `snoozeIdleTimer` when pointer has been out of zone 10s → then `flushPending()`. **Known gap**: if the user's real mouse cursor happens to rest in that bottom-right zone, the idle-out timer never runs (`running: service.snoozeActive && !service.snoozeZoneHovered`) and the snooze can appear "stuck" indefinitely — not a bug per se, but worth knowing when debugging "notifications aren't showing up" reports, since a snoozed arrival produces **zero on-disk trace** (no live popup file — `persistPopupFile` only runs from `showPopup`, never from `enqueuePending`).
4. **Max-3 display queue** (`maxVisiblePopups: 3`): if 3 toasts are up OR snoozing, new notifications go to `pendingQueue` (never dropped). Released as slots free, paced **250ms apart** (`pendingEmitTimer`). DND (`doNotDisturb`) still silences (skips) — only the snooze queues.
5. **`displayedCount`** is a synchronous counter mirroring on-screen toasts (popupModel.count lags because inserts are deferred via Qt.callLater). ALL cap checks use `displayedCount`, not `popupModel.count`.
6. **"+N more notifications" overflow indicator** (`components/OverflowIndicator.qml` + `overflowIndicator` in Service.qml): a one-line pseudo-toast shown when `pendingQueue` holds more than fits on screen. `queuedCount` is a synchronous mirror of `pendingQueue.length`, kept in sync manually at every mutation site — `pendingQueue.push`/`.shift()` mutate in place and do NOT fire `onPendingQueueChanged`, so nothing reactive can hang off that property directly. The indicator is positioned by `relayout()` as one more step past the newest real card in the same open-end walk (so it renders on TOP of the stack when bottom-anchored, flips to the bottom when top-anchored, matching item 1's anchor-flip design). Its visibility is driven by `visible: opacity > 0.001` (NOT a hard `visible: count>0` toggle) — see gotcha below.
7. **First-toast-after-cold-window jump**: `popupColumn.height` can read `0` for a beat while the layer-shell surface is still being mapped (only around the very first toast ever, before the window has ever been visible). `relayout()` bails out entirely if `popupColumn.height <= 0` rather than computing a garbage off-screen position, and `onHeightChanged: relayout()` reruns it the moment real geometry arrives. Each card's `Behavior on y` (`animateSlotted`) is only flipped true *inside* `relayout()`, right after that specific card receives its first real, height-valid position — so turning the animation on can never itself be the thing that animates a stale/garbage spot.

## DND (Do Not Disturb): persisted, IPC-controlled, and the bar-indicator clone trap

`doNotDisturb` lives in a `PersistentProperties { id: persisted }` block (in-process survives QML reloads via `reloadableId`) plus a debounced on-disk backstop (`~/.config/omarchy/plugins/wils.notifications/notifications.json`-equivalent settings file, `flushSettings()`/`loadSettings()`). IPC (`target: "notifications"`): `isDnd()`, `toggleDnd()`, `setDnd(value)`. These always operate correctly against the live cloned service — IPC target names are a global namespace, unaffected by plugin cloning.

**Trap**: the bar's DND indicator (`omarchy.indicators` plugin → `bar/indicators/Dnd.qml`, NOT part of the notifications plugin) hardcodes:
```qml
readonly property var notificationService: bar?.shell?.firstPartyServiceFor("omarchy.notifications")
```
`shell._services` is keyed strictly by the *manifest id that's actually enabled* (`_syncServices()` in shell.qml only registers under the real plugin id). After `omarchy plugin clone omarchy.notifications` the original `omarchy.notifications` is disabled and never gets a `_services` entry — `firstPartyServiceFor("omarchy.notifications")` silently returns `null`. Symptom: the DND bar icon always renders inactive and **clicking it does nothing at all** (guarded by `if (root.notificationService)`), so DND can look "stuck on" (or stuck off) forever from the user's perspective, even though `isDnd`/`setDnd` via IPC work fine — this is a UI wiring bug, not a DND logic bug, and is completely unrelated to the snooze feature.

**Fix**: clone the `omarchy.indicators` bar-widget plugin (`omarchy plugin clone omarchy.indicators --edit`, lands at `~/.config/omarchy/plugins/wils.indicators/indicators/Dnd.qml`) and replace the hardcoded id lookup with the shell's own official clone-redirection helper:
```qml
readonly property string notificationServiceId:
  bar?.shell?.pluginRegistry?.resolveEnabledId("omarchy.notifications") ?? "omarchy.notifications"
readonly property var notificationService: bar?.shell?.firstPartyServiceFor(notificationServiceId)
```
`pluginRegistry.resolveEnabledId(id)` (services/PluginRegistry.qml) is the canonical mechanism for exactly this: it maps a built-in plugin id to whichever enabled installed plugin declares `manifest.omarchy.clonedFrom === id` (falls back to the id itself if nothing was cloned). It's already used this way throughout `shell.qml` (`summon`, `hide`, `isPluginOpen`, `toggle`, `callIfLoaded`) — reuse it rather than hand-rolling a loop over `installedPlugins` (which is also easy to get wrong: the `clonedFrom` field is nested at `manifest.omarchy.clonedFrom`, not top-level `manifest.clonedFrom`). This same trap applies to any other first-party bar indicator/panel that hardcodes a `firstPartyServiceFor("omarchy.<x>")` lookup for a plugin the user might clone (NightLight.qml → `omarchy.nightlight`, StayAwake.qml → `omarchy.idle`, media BarWidget.qml/Panel.qml → `omarchy.media`, etc.) — same fix pattern applies.

`shell.json`'s `bar.layout` entry must also be updated from `{"id": "omarchy.indicators"}` to `{"id": "wils.indicators"}` — `omarchy plugin clone --edit` does this automatically.

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
- **`omarchy-shell -q notifications <method>` does NOT echo return values** (even nonexistent methods exit 0). Drop the `-q` flag to see the actual "ok"/error return during debugging — `omarchy-shell notifications isDnd` prints `on`/`off` directly. Otherwise verify by side effects (live popup files under ~/.local/state/omarchy/notifications/, history under .../history/) not stdout.
- QML `console.log` is not visible in journalctl; write to a file via a Process if you need debug output.
- Live popup files lag/mislead: measure cap with file-count bursts (send 12+ rapid, sample `ls ~/.local/state/omarchy/notifications/*.json | wc -l` → must stay ≤3). Also: **if DND or snooze is silently on, notifications produce zero live-file trace at all** — always check `omarchy-shell notifications isDnd` first when a burst test shows unexpectedly 0 files, before assuming the cap/pacing logic is broken.
- **Screenshot/behavioral verification of animation timing**: temporarily multiply `fadeMs`/`slideMs` by ~10-15x (e.g. 180→2500), restart, capture a burst of `omarchy capture screenshot --fullscreen` at short sleep intervals to catch mid-animation frames, verify positions with `grim -g "<w>x<h>+<x>+<y>"` crops of the toast corner, then restore the original values and restart again before declaring done. Real-speed animation (150-300ms) is too fast for `omarchy capture` (~1-2s per shot) to ever catch mid-transition.
- **`hyprctl dispatch <name> <args>` on this machine requires Lua-call syntax, not classic hyprctl space-separated args** — e.g. moving the cursor is NOT `hyprctl dispatch movecursor 100 100`, it needs the Hyprlang/lua-config-aware form. Don't fight this to work around a UI test; prefer a dedicated IPC/debug method in the QML service instead of trying to simulate mouse input via hyprctl.
- **Toasts are not reachable via computer-use/accessibility-tree automation** — they're bare wlroots layer-shell surfaces (PanelWindow with `WlrLayershell.namespace`), not normal application windows, so there's no accessibility tree or window handle to click. Verify click-behavior changes via the plugin's own IPC (`invokeLast`, etc.) plus on-disk side effects, not simulated mouse clicks.

## Verification quick path

```bash
omarchy restart shell
notify-send "Test" "msg" --expire-time=60000   # long-lived so it lingers
# cap: rapid burst (for i in $(seq 1 12); notify-send ...; done), sample live file count ≤3
# pacing: dismissOne then measure ms until next queued toast's file appears (~250-300ms)
# overflow indicator: burst > 3, confirm "+N more notifications" appears above/below the 3
#   per anchor direction, and N == sent - 3; dismiss one, confirm N decrements live
# DND: omarchy-shell notifications isDnd / setDnd true|false / toggleDnd — always check
#   this FIRST if a burst test shows unexpectedly 0 live files
omarchy-shell -q notifications dismissAll       # clear all
```
