---
name: omarchy-cloned-indicator-click-does-nothing
description: "Omarchy bar indicator buttons (night light, stay awake, DND) in a cloned user plugin (e.g. wils.indicators) do nothing on click; firstPartyServiceFor returns null."
---

# Cloned Omarchy indicators: clicks do nothing

## Symptom
Buttons beside the clock (centerBegin, `<user>.indicators` clone of `omarchy.indicators`) reveal on hover but clicking does nothing, and never show active.

## Root cause
Third-party (non-first-party) bar widgets get a `PluginShellApi` whose `firstPartyServiceFor()` returns null: the narrow service proxies are only built when the plugin manifest has kind `bar` (not `bar-widget`). Clone indicator files like `indicators/NightLight.qml` guard with `if (service)`, so clicks silently no-op and `active` stays false. Click routing in Bar.qml is fine.
Verify without clicking: temporary probe `Process` + `Timer` in the indicator that `echo`s `String(root.idleService)` to a /tmp file, then `omarchy restart shell` (hot reload may not fire). Never inject synthetic input; the user's mouse is theirs.

## Fix (edit only ~/.config/omarchy/plugins/<user>.indicators/indicators/*.qml)
Replace service use with the CLI the keybindings use, via `Quickshell.Io` `Process` + `StdioCollector`:
- NightLight: status `omarchy toggle nightlight --status` (JSON `.enabled`), click `omarchy toggle nightlight`
- StayAwake: status `omarchy toggle idle status` (JSON `.enabled`), click `omarchy toggle idle toggle`
- Dnd: status `omarchy-shell notifications isDnd` (text `on`/`off`), click `omarchy toggle notification silencing`
Refresh on `Component.onCompleted`, on `Connections { target: root.indicatorHost; onRefreshRequested }`, and in toggle process `onExited`.

## Gotchas
- Do NOT name a property `enabled` on a BarIndicator (collides with Item.enabled and disables the button); use `nightlightOn`, `stayAwakeOn`.
- Glyph lines are private-use chars: edit with line-range edits, never rewrite those lines; diff `activeText/inactiveText` lines against a backup.
- `hyprctl` from the agent shell needs `HYPRLAND_INSTANCE_SIGNATURE` (from /run/user/1000/hypr/); `omarchy-shell` IPC works without it.
- Same null-proxy issue affects any user widget calling `firstPartyServiceFor` (e.g. wils.audio media).
- Restore toggled state (stay-awake) after testing.
