---
name: omarchy-alt-xkb-layout-panel-plugin
description: "Use when adding a custom (non-stock) xkb keyboard layout variant to an Omarchy/Hyprland system and/or building an Omarchy Quickshell plugin that shows/hides a draggable overlay window in reaction to the active keyboard layout — e.g. \"pop up a cheat-sheet image when layout X is active\". Covers appending an xkb_symbols variant to /usr/share/X11/xkb/symbols/us (no evdev.xml registration needed — generic rules already resolve layout(variant) directly), verifying it with xkbcli compile-keymap (works headless, unlike setxkbmap which needs X11), detecting the active layout via hyprctl -j devices .active_keymap + Hyprland activelayout/configreloaded IPC events (mirroring the stock KeyboardLayout bar widget's UNTYPED_KEYBOARDS filter), and the Omarchy plugin \"panel\" kind: PanelWindow shown/hidden via a bool, dragged by mutating anchors.left/top margins from a MouseArea (not native window drag, since layer-shell has no decorations), position persisted via PersistentProperties, and enabling it by adding {\"id\": \"...\"} to shell.json's top-level plugins[] array (required — panel-kind plugins are NOT auto-enabled just by existing under ~/.config/omarchy/plugins/, unlike bar-widgets which enable via bar.layout)."
---

## Adding a custom xkb layout variant (e.g. a layout not shipped in stock xkb, like "Gallium")

1. Compute the letter grid: map each physical QWERTY key position (AD01-10 top
   row, AC01-10 home row, AB01-10 bottom row) to the target layout's letter at
   that same physical position. Get the letter grid from the layout's own
   spec/GitHub repo (web search "<layout name> keyboard layout" + look for an
   ASCII grid like `b l d c v | j y o u ,`), not from a rendering site (many,
   e.g. keyboard-design.com, block scraping).

2. Append an `xkb_symbols "variantname" { include "us(basic)"; key <AD01>
   {[ b, B ]}; ... }` block to `/usr/share/X11/xkb/symbols/us` (system file,
   needs sudo — use the `sudo-interactive-tty-via-hub` skill's `hub start`
   pattern if `sudo -n` fails). No entry in `rules/evdev.xml` is needed: the
   generic xkb rule `* = +%l(%v)` resolves `kb_layout=us,us` +
   `kb_variant=,variantname` straight to this file/section.

3. Verify headlessly with `xkbcli compile-keymap --layout us,us --variant
   ,variantname --options grp:alts_toggle` — compiles cleanly if correct.
   `setxkbmap ... -print | xkbcomp -` does NOT work here since there's no X11
   server on a Wayland/Hyprland session; don't use it to validate.

4. Wire into `~/.config/hypr/input.lua`:
   ```lua
   kb_layout = "us,us",
   kb_variant = ",variantname",   -- empty first slot = plain QWERTY default
   kb_options = "caps:backspace,grp:alts_toggle",
   ```

5. To confirm live end-to-end without physically pressing Alt+Alt: find the
   real physical keyboard's device name (`hyprctl -j devices`, NOT
   `hl-virtual-keyboard-fcitx5` or other pseudo-devices — see filter below),
   then `hyprctl switchxkblayout <name> next` toggles it and updates
   `active_keymap` in `hyprctl -j devices` output immediately — this is a
   reliable synthetic trigger for any reactive tooling keyed off layout state.

## Detecting the active layout from Quickshell/Hyprland IPC

Reference implementation already in the shell:
`/usr/share/omarchy/shell/plugins/bar/widgets/KeyboardLayout.qml` +
`KeyboardLayoutModel.js`. Key points to reuse:

- Poll `hyprctl -j devices`, read `.keyboards[].active_keymap` (a human
  description string, e.g. `"English (US, Gallium)"` — set via
  `name[Group1] = "..."` in the xkb symbols block).
- Filter out non-typed pseudo-keyboards before matching:
  `/^(hl-virtual-keyboard|power-button|sleep-button|lid-switch|video-bus)/`
  — these report layout changes too but nobody types on them.
- Refresh on Hyprland IPC events, not a poll timer: `Connections { target:
  Hyprland; function onRawEvent(event) { if (event.name.indexOf("activelayout")
  !== -1 || event.name === "configreloaded") refresh() } }` (needs `import
  Quickshell.Hyprland`).

## Omarchy "panel" kind plugin for a reactive draggable overlay

- `manifest.json`: `"kinds": ["panel"]`, `"keepLoaded": true`,
  `"entryPoints": { "panel": "Whatever.qml" }`.
- **Must** add `{"id": "your.plugin.id"}` to the top-level `plugins[]` array
  in `~/.config/omarchy/shell.json` — panel/overlay/menu/service kinds are
  gated on `isEnabled()`, which for non-first-party plugins checks
  `plugins[]` membership (see `PluginRegistry.qml`'s `isEnabled`). Bar-widget
  kind plugins enable differently (via `bar.layout` entries) — don't confuse
  the two. Forgetting this step means the plugin file is correct but never
  loads.
- Root QML is a plain `Item` containing a `PanelWindow` (`import
  Quickshell.Wayland`) whose `visible` is bound to your detection boolean.
  `WlrLayershell.layer: WlrLayer.Overlay`, `keyboardFocus: WlrKeyboardFocus.None`,
  `exclusionMode: ExclusionMode.Ignore`.
- For an SVG asset, just point a QML `Image { source: "assets/foo.svg" }` at
  it directly — Qt's SVG image plugin renders it, no PNG conversion needed;
  set `sourceSize.width/height` for crisp scaling.
- **Dragging**: layer-shell surfaces have no WM decorations/native drag, so
  implement it manually: `anchors { left: true; top: true }`,
  `margins.left`/`margins.top` bound to persisted x/y properties, and a
  `MouseArea` over the card that on `onPositionChanged` (while `pressed`)
  adds the mouse delta to those x/y properties. Persist position across shell
  reloads with `PersistentProperties { reloadableId: "..."; property real x;
  property real y }` (same pattern the notifications plugin uses for DND
  state).
- After editing, `omarchy-shell shell rescanPlugins` (or just save — it
  hot-reloads) picks it up; verify the surface actually mapped via `hyprctl
  layers | grep <your WlrLayershell.namespace>` and/or `grim -g "x,y wxh"
  /tmp/check.png` + read the PNG.
