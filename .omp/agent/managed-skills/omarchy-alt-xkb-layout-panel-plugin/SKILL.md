---
name: omarchy-alt-xkb-layout-panel-plugin
description: "Use when adding a custom (non-stock) xkb keyboard layout variant to an Omarchy/Hyprland system and/or building an Omarchy Quickshell plugin that shows/hides a draggable overlay window in reaction to the active keyboard layout — e.g. \"pop up a cheat-sheet image when layout X is active\". Covers appending an xkb_symbols variant to /usr/share/X11/xkb/symbols/us (no evdev.xml registration needed — generic rules already resolve layout(variant) directly), verifying it with xkbcli compile-keymap (works headless, unlike setxkbmap which needs X11), detecting the active layout via hyprctl -j devices .active_keymap + Hyprland activelayout/configreloaded IPC events (mirroring the stock KeyboardLayout bar widget's UNTYPED_KEYBOARDS filter), the Hyprland kb_variant cache gotcha (hyprctl reload doesn't recompile the keymap if the config *string* is unchanged — must toggle the value to force it), and dragging a layer-shell overlay card without acceleration bugs."
---

## Adding a custom xkb layout variant (e.g. a layout not shipped in stock xkb, like "Gallium")

1. Get the letter grid from the layout's **own canonical source** — its GitHub
   repo's own XKB/keymap file if one exists (e.g.
   `<maintainer>/<Layout>/Linux/xkb/<variant>`), not a rendering/description
   site (many, e.g. keyboard-design.com, block scraping or 404) and not a
   hand-derived guess from a prose description. If the repo ships its own
   Linux XKB file, use it verbatim — don't re-derive the grid yourself.

2. Map the letter grid onto the **correct XKB physical key names** for the
   base `us(basic)` layout — don't assume top/home/bottom rows are exactly
   10 keys each:
   - Top row: `AD01`-`AD10` (QWERTY Q W E R T Y U I O P)
   - Home row: `AC01`-`AC11` — 11 keys, not 10: `AC10` is the `;` position
     and `AC11` is the `'` position in the stock US layout. A custom layout
     that only defines `AC01`-`AC10` and skips `AC11` has silently shifted
     every letter after the 9th home-row key onto the wrong physical key.
   - Bottom row: `AB01`-`AB10` — `AB01`-`AB07` are the 7 letter keys (Z X C
     V B N M), `AB08`-`AB10` are the punctuation-capable keys (comma,
     period, slash by default, but the custom layout may repurpose them).
     Do not put punctuation output on `AB08`/`AB09` and expect it to land on
     the physical comma/period keys unless you've mapped it that way — those
     *are* the physical comma/period keys.
   - Letter keys: `key <ADnn> {[ letter, LETTER ]};`
   - Punctuation keys need proper shift-pair symbol names, e.g.
     `comma/less`, `period/greater`, `slash/question`, `apostrophe/quotedbl`,
     `semicolon/colon`.
   - End with `include "level3(ralt_switch)"`.

3. Append an `xkb_symbols "<name>"` block that `include "us(basic)"` then
   overrides only the keys that differ, to the OS's `us` symbols file:
   `/usr/share/X11/xkb/symbols/us` (system file, needs sudo — use the
   `sudo-interactive-tty-via-hub` skill's `hub start` pattern if `sudo -n`
   fails).

4. **No XML registration needed.** `/usr/share/X11/xkb/rules/evdev.xml` is
   only for GUI layout pickers (GNOME Settings etc.); Hyprland/libinput/
   xkbcommon resolve `kb_layout`+`kb_variant` via the generic rule in
   `/usr/share/X11/xkb/rules/evdev` (plain text, `%l(%v)` pattern), which
   finds your new `xkb_symbols` block directly. Adding the block to
   `symbols/us` is sufficient.

5. **Validate on Wayland/Hyprland** with `xkbcli compile-keymap --layout
   us,us --variant ,<name> --options grp:alts_toggle` (from
   `libxkbcommon-tools`) — this is the exact resolution path Hyprland uses.
   Don't bother with `setxkbmap`/`xkbcomp` (X11-only, won't work under
   Wayland). Check the compiled output's `key <ACnn> { symbols[1]=[...
   qwerty...], symbols[2]=[...new-layout...] }` lines to confirm the right
   characters landed on the right physical keys — spot-check specifically
   the keys near row boundaries (`AC10`/`AC11`, `AB07`/`AB08`) since those
   are where off-by-one shifts hide.

## Deriving key-to-key mapping when no canonical XKB file exists

Web-search `"<layout name>" keyboard layout` + look for an ASCII grid or the
layout's own GitHub repo. Don't guess from memory or from a single blog post
without cross-checking a second source (e.g. the repo's own SVG/PNG keymap
image, if it has `<text>`/coordinate data you can grep for row groupings).

## Hyprland `kb_variant` caching gotcha (Lua `input.lua` config)

`hyprctl reload` does **not** recompile the active keymap if the
`kb_variant`/`kb_layout` config *string value* hasn't changed — even if the
underlying XKB symbols file on disk was just edited. Editing
`/usr/share/X11/xkb/symbols/us` and running `hyprctl reload` alone leaves the
stale, pre-edit compiled keymap active; users will report the old (wrong)
key mappings persisting.

Force a recompile: temporarily blank the variant, reload, then restore it
and reload again:
```lua
kb_variant = ",",        -- edit, hyprctl reload
```
then
```lua
kb_variant = ",gallium", -- edit back, hyprctl reload
```
`hyprctl keyword input:kb_variant ...` does NOT work with Omarchy's Lua-based
non-legacy config parser (`"keyword can't work with non-legacy parsers"`) —
must edit `input.lua` directly and `hyprctl reload` twice as above.

## Confirming live end-to-end without physically pressing Alt+Alt

Find the real physical keyboard's device name (`hyprctl -j devices`, NOT
`hl-virtual-keyboard-fcitx5` or other pseudo-devices — see filter below),
then `hyprctl switchxkblayout <name> next` toggles it and updates
`active_keymap` in `hyprctl -j devices` output immediately — this is a
reliable synthetic trigger for any reactive tooling keyed off layout state.
Check `active_layout_index` too: a single `next` call can land back on index
0 if timing races with a prior toggle: poll and retry once if the index
didn't move.

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

### Dragging — correct pattern (verified; the naive approaches below are buggy)

**Do NOT** move the layer-shell surface itself to implement dragging (e.g.
`anchors {left:true;top:true}` + `margins.left`/`margins.top` bound to
persisted x/y, mutated from a MouseArea). Repositioning a real Wayland
surface round-trips through the compositor asynchronously; under fast mouse
movement the surface lags behind the cursor and the drag feels broken/laggy
no matter how carefully the delta math is written.

**Also do NOT** hand-roll the delta math even for an in-scene (non-surface)
drag, e.g. capturing `pressX`/`pressY` once on `onPressed` and then doing
`pos.x += mouse.x - pressX` on every `onPositionChanged` without rebasing —
this re-adds the *full delta from the original press point* on every move
event, and since a drag gesture fires many move events, the position
overshoots more the longer/faster you drag (feels like acceleration).

**Correct pattern**, matching every other overlay in this shell
(notifications, menu, clipboard, OSD, wifiqr, polkit, reminders, emojis,
image-picker — grep `anchors { top: true; bottom: true; left: true; right:
true }` under `/usr/share/omarchy/shell/plugins/*/`):

1. Make the `PanelWindow` itself **stationary and full-screen**:
   `anchors { top: true; bottom: true; left: true; right: true }`. It never
   moves.
2. Keep the surface click-through everywhere except the visible card:
   `mask: Region { item: card }` (needs `import Quickshell.Wayland` for
   `Region`).
3. The draggable content (`card`) is a plain `Item`/`BorderSurface` inside
   that stationary window, positioned via its own `x`/`y` — not window
   margins.
4. Drag it with Qt's **built-in** `MouseArea.drag.target` — do not write
   manual delta math:
   ```qml
   MouseArea {
     anchors.fill: parent
     drag.target: card
     drag.axis: Drag.XAndYAxis
     drag.minimumX: 0
     drag.maximumX: Math.max(0, panel.screenW - card.width)
     drag.minimumY: 0
     drag.maximumY: Math.max(0, panel.screenH - card.height)
     onReleased: { pos.x = card.x; pos.y = card.y }  // persist only on release
   }
   ```
   Qt's own pointer tracking is well-tested and immune to the compounding-
   delta bug above; `drag.minimumX/Y`/`maximumX/Y` also replaces any manual
   `clamp()` function called from `onPositionChanged`.
5. Persist position across shell reloads with `PersistentProperties {
   reloadableId: "..."; property real x; property real y }` (same pattern
   the notifications plugin uses for DND state), but only write to it in
   `onReleased`, not every move event. Apply it back to `card.x`/`card.y`
   (clamped to current screen size) in `PanelWindow.onVisibleChanged` when
   becoming visible, not as a permanent binding (a permanent `x: pos.x`
   binding would fight `drag.target`'s direct mutation of `card.x`).

After editing, `omarchy-shell shell rescanPlugins` (or just save — it
hot-reloads) picks it up; verify:
- No QML errors: `journalctl _PID=<quickshell pid> --no-pager -n 40` (or
  `quickshell log --pid <pid> -t 200`) right after the save-triggered
  reload — look for `Local plugin changed, reloading: <plugin.id>` followed
  by no warnings/errors.
- The surface actually mapped: `hyprctl layers | grep <your
  WlrLayershell.namespace>`.

### Plugin `kinds` must match what the QML actually renders

If the plugin's root QML doesn't build a `PanelWindow` at all (e.g. it's
just a background `Item` that launches an external process like `imv` and
has no visible Quickshell-owned surface), it is a `"service"`-kind plugin
(`entryPoints: { "service": "..." }`), not `"panel"`. Conversely, if it does
render a `PanelWindow`, it must stay `"panel"`. Mismatching `kinds` against
the entry point's actual content means the shell's generic loader for that
kind (`shell.qml`'s service-loading loop specifically checks
`manifest.kinds.indexOf("service")`/`.indexOf("panel")`) never instantiates
it — the plugin file is syntactically fine and hot-reloads without error,
but nothing in it ever runs, which is silent and easy to mistake for "the
logic itself is buggy" when actually the component tree was never created.
