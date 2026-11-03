---
name: omarchy-alt-xkb-layout-panel-plugin
description: "Use when adding a custom (non-stock) xkb keyboard layout variant (e.g. Gallium) to Omarchy/Hyprland, when Hyprland shows \"Invalid keyboard layout passed ... variant: ,gallium\" after an update/xkeyboard-config upgrade, or when building an Omarchy Quickshell plugin that shows a draggable overlay in reaction to the active keyboard layout. Covers appending an xkb_symbols variant to /usr/share/X11/xkb/symbols/us, restoring it after a package upgrade wipes it, verifying with xkbcli compile-keymap, detecting the active layout via hyprctl/IPC, the Hyprland kb_variant cache gotcha, and drag-without-acceleration overlays."
---

## Recovery: "Invalid keyboard layout passed" after an update (variant wiped)

Symptom: red Hyprland banner `Invalid keyboard layout passed. ( rules: , model: , variant: ,gallium, options: ..., layout: us,us )`. `hyprctl configerrors` is EMPTY (it's a runtime keymap error, not a Lua parse error) — don't conclude "config is clean".

Cause: `/usr/share/X11/xkb/symbols/us` is owned by `xkeyboard-config`; an upgrade (often via `omarchy update`) replaces it and deletes the appended custom `xkb_symbols "gallium"` block. Confirm: `grep -c gallium /usr/share/X11/xkb/symbols/us` → 0, and `pacman -Qi xkeyboard-config | grep "Install Date"` matches the time the banner appeared; `xkbcli compile-keymap --layout us,us --variant ,gallium` errors `Couldn't process include statement for 'us(gallium)'`.

Fix procedure:
1. Agent shell isn't in the Hyprland session: `export HYPRLAND_INSTANCE_SIGNATURE=$(ls -t /run/user/$(id -u)/hypr/ | head -1)` before `hyprctl`. To SEE the banner, `grim /tmp/screen.png` (with WAYLAND_DISPLAY set) and read it — the banner text is not in `hyprctl configerrors` or the log.
2. Re-fetch the canonical file: `https://raw.githubusercontent.com/GalileoBlues/Gallium/main/Linux/xkb/gallium_rowstag` (also `_colstag`, `_rowstag_angl`, `_qx` variants). Wils uses ROWSTAG (physical h/j/k/l → y/h/a/e; matches nvim gallium plugin + cheatsheet SVG keymap.svg = Gallium_Rowstag).
3. Build the block: delete the `default partial` header line, replace `xkb_symbols "basic" {` with `partial alphanumeric_keys\nxkb_symbols "gallium" {`.
4. Test WITHOUT sudo first: copy `/usr/share/X11/xkb` to /tmp/xkbtest, append block to its `symbols/us`, run `xkbcli compile-keymap --include /tmp/xkbtest --include-defaults --layout us,us --variant ,gallium --options caps:backspace,grp:alts_toggle` (exit 0).
5. Install with sudo (needs fingerprint → run via bash `pty: true`, see sudo-interactive-tty-via-hub): an idempotent script that skips if `xkb_symbols "gallium"` already present, backs up `us` to `us.bak.<epoch>`, then `cat block >> us`.
6. Verify: system `xkbcli compile-keymap` exit 0; `hyprctl reload`; `hyprctl configerrors` empty; `hyprctl switchxkblayout at-translated-set-2-keyboard 1` → `active_keymap` = `English (US, Gallium v2 rowstag)`; switch back to 0. Tell user to toggle layout / reload to clear the stale banner.

Recurs on every xkeyboard-config upgrade. Durable alternatives to offer (not yet set up): a pacman hook in /etc/pacman.d/hooks that re-appends the block (PostTransaction, Target = xkeyboard-config), or a user-level layout under ~/.config/xkb/symbols (package can't overwrite).

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
   Wayland; setxkbmap under Xwayland prints a misleading success). Check the compiled output's `key <ACnn> { symbols[1]=[...
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
