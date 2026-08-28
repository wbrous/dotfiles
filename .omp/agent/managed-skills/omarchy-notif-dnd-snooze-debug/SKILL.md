---
name: omarchy-notif-dnd-snooze-debug
description: "Use when adding/testing Hyprland dispatch commands (e.g. hyprctl dispatch movecursor) on this Omarchy machine and getting a Lua parse error like \"[string \\\"return hl.dispatch(...)\\\"]: ')' expected\", or when debugging why notify-send notifications on this machine silently don't appear/persist as live popup files (check DND state via omarchy-shell notifications isDnd before assuming a snooze/queue bug) — also covers the wils.notifications plugin's snooze-timer gotcha where the idle-out timer never fires if the pointer rests in the bottom-right snooze zone, requiring a direct-set IPC escape hatch rather than waiting it out."
---

## Context
This machine's `hyprctl` on PATH is wrapped so `dispatch` args get evaluated
as Lua (`hl.dispatch(...)`), NOT the standard hyprctl space-separated syntax.
`hyprctl dispatch movecursor 100 100` (and comma/quoted variants) fails with:

```
error: [string "return hl.dispatch(movecursor 100 100)"]:1: ')' expected near '100'
```

Never found a working raw-CLI syntax for `movecursor` on this box in the time
spent — don't burn more time guessing quote/comma variants. If cursor
movement is genuinely needed for a dispatch/test, either read
`~/.config/hypr/*.lua` for a working example of that specific dispatcher call
syntax, or avoid needing it entirely (e.g. add a direct-state-set IPC method
instead of trying to unstick a hover-gated timer via synthetic cursor moves).

## wils.notifications: DND vs snooze — check DND FIRST
If notify-send notifications aren't showing up as live popup files under
`~/.local/state/omarchy/notifications/*.json` and aren't landing in
`history/` either, don't assume it's the snooze/backlog queue. Check DND
first — it's a completely separate silence path with zero on-disk trace for
ephemeral notifications:

```bash
omarchy-shell notifications isDnd     # NOT -q, so you can see the output
```

If `on`, that alone explains total silence. Toggle with
`omarchy-shell notifications setDnd false/true`. **If you flip it only to
debug/verify something, restore it to whatever you found before yielding** —
it's user state you weren't asked to change.

## Snooze timer can get stuck forever
The plugin's `snoozeIdleTimer` only runs while the pointer is OUTSIDE the
bottom-right snooze zone (`running: service.snoozeActive &&
!service.snoozeZoneHovered`). If the user's cursor happens to rest in that
corner, the countdown never starts and snooze never expires on its own —
waiting 10s+ is not sufficient. Don't try to fix this by moving the cursor
via hyprctl (see above, doesn't work reliably here). Instead add/use a direct
IPC method that sets `service.snoozeActive = false` and calls
`service.flushPending()` unconditionally, bypassing the timer/hover state
entirely — this is the reliable fix, not a synthetic mouse move.

## Verification pattern that actually works
`omarchy-shell -q <target> <method>` suppresses ALL output including errors
(exit 0 even for bogus methods). When actually debugging (not just firing
and forgetting), drop `-q` to see the real return value/error:

```bash
omarchy-shell notifications ping        # "ok" if IPC target/handler alive
omarchy-shell notifications isDnd       # see real state, not swallowed
```
