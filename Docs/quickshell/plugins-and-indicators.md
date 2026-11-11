# Plugins, indicators, and panel overlays

Cloned bar indicators that do nothing on click, panel-kind overlay plugins, custom xkb layout variants, and the Hyprland keymap cache gotcha.

## Cloned indicators: clicks do nothing

**Symptom:** bar indicator buttons (night light, stay awake, DND) in a cloned user plugin (e.g. `wils.indicators` clone of `omarchy.indicators`) reveal on hover but clicking does nothing, never show active.

**Cause:** third-party bar widgets get a `PluginShellApi` whose `firstPartyServiceFor()` returns null — narrow service proxies are only built when the manifest has kind `bar`, not `bar-widget`. Clone indicator files guard with `if (service)`, so clicks silently no-op. Click routing in Bar.qml is fine.

**Fix:** edit only `~/.config/omarchy/plugins/<user>.indicators/indicators/*.qml`; replace service use with the CLI the keybindings use, via `Quickshell.Io` `Process` + `StdioCollector`:

- NightLight: status `omarchy toggle nightlight --status` (JSON `.enabled`), click `omarchy toggle nightlight`
- StayAwake: status `omarchy toggle idle status` (JSON `.enabled`), click `omarchy toggle idle toggle`
- Dnd: status `omarchy-shell notifications isDnd` (text `on`/`off`), click `omarchy toggle notification silencing`

Refresh on `Component.onCompleted`, on `Connections { target: root.indicatorHost; onRefreshRequested }`, and in the toggle process `onExited`.

**Alternative for the notifications DND indicator:** clone `omarchy.indicators` and replace the hardcoded lookup with the shell's clone-redirection helper:

```qml
readonly property string notificationServiceId:
  bar?.shell?.pluginRegistry?.resolveEnabledId("omarchy.notifications") ?? "omarchy.notifications"
readonly property var notificationService: bar?.shell?.firstPartyServiceFor(notificationServiceId)
```

Update `shell.json` `bar.layout` from `{"id": "omarchy.indicators"}` to `{"id": "wils.indicators"}` (`clone --edit` does this automatically). Same trap/fix applies to any first-party indicator hardcoding `firstPartyServiceFor("omarchy.<x>")` (NightLight → `omarchy.nightlight`, StayAwake → `omarchy.idle`, media → `omarchy.media`).

**Gotchas:** don't name a property `enabled` on a BarIndicator (collides with `Item.enabled`, disables the button) — use `nightlightOn`/`stayAwakeOn`. Glyph lines are private-use chars: line-range edits only, never rewrite; diff against backup. `hyprctl` from an agent shell needs `HYPRLAND_INSTANCE_SIGNATURE` (from `/run/user/1000/hypr/`); `omarchy-shell` IPC works without it. Verify with a temporary `Process`+`Timer` probe echoing state to /tmp (never synthetic input), then `omarchy restart shell`. Restore toggled state (stay-awake) after testing.

## Panel-kind plugin for a reactive draggable overlay

- `manifest.json`: `"kinds": ["panel"]`, `"keepLoaded": true`, `"entryPoints": { "panel": "Whatever.qml" }`.
- MUST add `{"id": "your.plugin.id"}` to top-level `plugins[]` in `~/.config/omarchy/shell.json` — panel/overlay/menu/service kinds are gated on `isEnabled()` checking `plugins[]` membership. Bar-widget kinds enable via `bar.layout` instead. Forgetting this: file correct but never loads.
- Root QML is a plain `Item` containing a `PanelWindow` (`import Quickshell.Wayland`) with `visible` bound to the detection boolean. `WlrLayershell.layer: WlrLayer.Overlay`, `keyboardFocus: WlrKeyboardFocus.None`, `exclusionMode: ExclusionMode.Ignore`.
- SVG assets: `Image { source: "assets/foo.svg" }` directly — Qt's SVG plugin renders it; set `sourceSize` for crisp scaling.
- `kinds` must match what the QML renders: no `PanelWindow` (e.g. just launches an external process) → `"service"` kind, not `"panel"`. Mismatch means the shell's kind loader never instantiates it — syntactically fine, hot-reloads clean, but nothing runs.

**Dragging — correct pattern:** make the `PanelWindow` stationary and full-screen (`anchors { top: true; bottom: true; left: true; right: true }`), click-through except the card (`mask: Region { item: card }`), position the draggable card via its own `x`/`y`, and drag with Qt's built-in `MouseArea.drag.target` (never hand-rolled delta math, never move the layer-shell surface via margins — compositor round-trip lags; press-point deltas without rebasing compound into acceleration):

```qml
MouseArea {
  anchors.fill: parent
  drag.target: card
  drag.axis: Drag.XAndYAxis
  drag.minimumX: 0
  drag.maximumX: Math.max(0, panel.screenW - card.width)
  drag.minimumY: 0
  drag.maximumY: Math.max(0, panel.screenH - card.height)
  onReleased: { pos.x = card.x; pos.y = card.y }
}
```

Persist in `PersistentProperties` only on release; apply back (clamped) in `PanelWindow.onVisibleChanged`, not as a permanent binding (fights `drag.target`).

After editing: `omarchy-shell shell rescanPlugins` (or save — hot-reloads). Verify no QML errors (`journalctl _PID=<quickshell pid>`, look for `Local plugin changed, reloading`) and surface mapped (`hyprctl layers | grep <namespace>`).

## Detecting the active keyboard layout from Quickshell

Reference: `/usr/share/omarchy/shell/plugins/bar/widgets/KeyboardLayout.qml` + `KeyboardLayoutModel.js`. Poll `hyprctl -j devices`, read `.keyboards[].active_keymap` (human string set via `name[Group1]` in the xkb block). Filter pseudo-keyboards: `/^(hl-virtual-keyboard|power-button|sleep-button|lid-switch|video-bus)/`. Refresh on Hyprland IPC events, not a timer: `Connections { target: Hyprland; function onRawEvent(event) { if (event.name.indexOf("activelayout") !== -1 || event.name === "configreloaded") refresh() } }` (needs `import Quickshell.Hyprland`).

## Custom xkb layout variant (e.g. Gallium)

1. Get the letter grid from the layout's own canonical source (its GitHub repo's Linux XKB file) verbatim — not a description site, not a hand-derived guess.
2. Map onto correct XKB physical key names for `us(basic)`: top `AD01`–`AD10`; home `AC01`–`AC11` (11 keys — `AC10` is `;`, `AC11` is `'`; a 10-key grid silently shifts everything after the 9th home key); bottom `AB01`–`AB10` (`AB08`–`AB10` are the physical comma/period/slash keys). Punctuation needs shift-pair names (`comma/less`, `period/greater`, `slash/question`, `apostrophe/quotedbl`, `semicolon/colon`). End with `include "level3(ralt_switch)"`.
3. Append `xkb_symbols "<name>"` (include `us(basic)`, override differing keys) to `/usr/share/X11/xkb/symbols/us` (sudo; fingerprint → PTY run).
4. No XML registration needed — `evdev.xml` is only for GUI pickers; Hyprland/xkbcommon resolves via the generic `%l(%v)` rule in `evdev`.
5. Validate with `xkbcli compile-keymap --layout us,us --variant ,<name> --options grp:alts_toggle` (the exact Hyprland path; `setxkbmap` is X11-only). Spot-check compiled `key <ACnn>` lines near row boundaries (`AC10`/`AC11`, `AB07`/`AB08`).

**"Invalid keyboard layout passed" after update:** `/usr/share/X11/xkb/symbols/us` is owned by `xkeyboard-config`; an upgrade (often via `omarchy update`) wipes the appended block. `hyprctl configerrors` is EMPTY (runtime keymap error, not Lua) — confirm with `grep -c gallium .../us` → 0 and `xkbcli compile-keymap` erroring on `us(gallium)`. Fix: re-fetch canonical file, test-append against a /tmp copy of the xkb tree first, then idempotent sudo append (backup `us.bak.<epoch>`). Verify: compile exit 0, `hyprctl reload`, `hyprctl switchxkblayout <device> 1` shows the new `active_keymap`, switch back. Recurs every upgrade — durable options: pacman hook re-appending post-transaction, or user-level `~/.config/xkb/symbols`. Agent shell needs `HYPRLAND_INSTANCE_SIGNATURE` exported; view the banner via `grim` screenshot (not in logs).

**Hyprland `kb_variant` cache gotcha:** `hyprctl reload` does NOT recompile the keymap if the config string value is unchanged — editing `symbols/us` alone leaves the stale keymap active. Force recompile: blank the variant in `input.lua`, reload, restore, reload again. (`hyprctl keyword input:kb_variant` doesn't work with the Lua parser.) Confirm live via `hyprctl switchxkblayout <real device> next` (find the physical keyboard in `hyprctl -j devices`, not virtual ones) and check `active_keymap`/`active_layout_index` (poll/retry once — a single `next` can race back to index 0).

_Migrated from: omarchy-cloned-indicator-click-does-nothing, omarchy-alt-xkb-layout-panel-plugin_
