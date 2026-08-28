---
name: omarchy-colemak-dh-setup
description: "Use when setting up, switching, or debugging alternative keyboard layouts (Colemak-DH, Gallium, or similar non-stock layouts) on this Omarchy/Hyprland machine — covers the input.lua multi-layout/alts_toggle pattern, adding a custom XKB variant for layouts not shipped in /usr/share/X11/xkb (like Gallium), and reprogramming the physical-hjkl-navigation nvim plugin (colemak-dh/gallium) to match a new layout's letter permutation."
---

## Config file location (this machine)
`~/.config/hypr/input.lua`, NOT `input.conf` — Omarchy's Hyprland config here is Lua-based (`hl.config({ input = { ... } })`). Always `glob ~/.config/hypr/*.conf` first if unsure.

## Two-layout alt-toggle pattern in `input.lua`
```lua
kb_layout = "us,us",
kb_variant = "<slot1-variant>,<slot2-variant>",
kb_options = "caps:backspace,grp:alts_toggle",
```
- `grp:alts_toggle` binds Left Alt + Right Alt to switch between the two layout slots.
- Empty variant string for a slot = plain QWERTY in that slot. E.g. QWERTY default + Gallium on toggle: `kb_variant = ",gallium"`.
- Apply live with `hyprctl reload` (no logout/relogin needed).

To temporarily disable a multi-layout setup: comment out the three multi-layout lines with `--` and add plain single-layout equivalents (`kb_layout = "us"`, `kb_options = "caps:backspace"` — no `kb_variant`, no `grp:alts_toggle`) directly below, so it's easy to restore later.

## Adding a custom XKB variant not shipped by the OS (e.g. Gallium)
Gallium (and many alt layouts) are NOT in `/usr/share/X11/xkb/symbols/`. `localectl list-x11-keymap-variants us` won't list them. You must add a variant block yourself:

1. Find the OS's `us` symbols file: `/usr/share/X11/xkb/symbols/us`. Look at existing variant blocks (e.g. `xkb_symbols "de_se_fi"`) for the exact syntax/convention.
2. Append a new `xkb_symbols "<name>"` block that `include "us(basic)"` then overrides only the keys that differ, using XKB physical key codes:
   - Top row: `AD01`-`AD10` (QWERTY Q W E R T Y U I O P)
   - Home row: `AC01`-`AC10` (QWERTY A S D F G H J K L ;)
   - Bottom row: `AB01`-`AB10` (QWERTY Z X C V B N M , . /)
   - Letter keys: `key <ADnn> {[ letter, LETTER ]};`
   - Punctuation keys need proper shift-pair symbol names, e.g. `comma/less`, `period/greater`, `slash/question`, `apostrophe/quotedbl`.
   - End with `include "level3(ralt_switch)"`.
3. Editing `/usr/share/X11/xkb/symbols/us` needs root — use the `sudo-interactive-tty-via-hub` skill (`hub op=start application=sudo args=["sh","-c","cat /tmp/variant.txt >> /usr/share/X11/xkb/symbols/us"] pty=true`) rather than plain bash `sudo`.
4. **No XML registration needed.** `/usr/share/X11/xkb/rules/evdev.xml` is only for GUI layout pickers (GNOME Settings etc.); Hyprland/libinput/xkbcommon resolve `kb_layout`+`kb_variant` via the generic rule in `/usr/share/X11/xkb/rules/evdev` (plain text, `%l(%v)` pattern), which finds your new `xkb_symbols` block directly. Adding the block to `symbols/us` is sufficient.
5. **Validate on Wayland/Hyprland** with `xkbcli compile-keymap --layout us,us --variant ,<name> --options grp:alts_toggle` (from `libxkbcommon-tools`) — this is the exact resolution path Hyprland uses. Don't bother with `setxkbmap`/`xkbcomp` (X11-only, won't work under Wayland and gives confusing "syntax error" noise even when the symbols file itself is fine). Check the compiled output's `key <ACnn> { symbols[1]=[...qwerty...], symbols[2]=[...new-layout...] }` lines to confirm the right characters landed on the right physical keys.

## Deriving key-to-key mapping for a new layout
When told to switch to a named alt-layout (e.g. Gallium), the physical-key → letter grid is usually published as three rows of 10 characters matching QWERTY's AD/AC/AB row positions 1:1 (row-staggered ANSI). Web-search `"<layout name>" keyboard layout row-staggered angle mod` or the layout's GitHub repo for the exact letter grid before writing the XKB block — don't guess.

## Reprogramming the physical-hjkl-navigation nvim plugin for a new layout
This machine has a small nvim plugin (was `colemak-dh`, migrated to `gallium`) at `~/.config/nvim/lua/<name>/init.lua`, loaded via `require("<name>").setup()` in `~/.config/nvim/lua/config/keymaps.lua`. It restores hjkl motion on the physical h/j/k/l keys under an alt-layout by bidirectionally swapping vim keymaps: `M.default_pairs = { {"h", <char physical-h-key now sends>}, {"j", <char physical-j-key sends>}, {"k", ...}, {"l", ...} }`.

- Look up the target layout's letters at the physical h/j/k/l column positions (right-hand home row, columns 6-9 in the AC01-10 grid) to get the four sent-characters.
- `set_pair(a,b)` does `keymap.set(a,b)` AND `keymap.set(b,a)` — a full symmetric swap of vim command bindings for those two letters, not a physical-key remap. If the target layout's character set overlaps with `{h,j,k,l}` themselves (e.g. Gallium: physical-j sends "h"), pairs processed in list order will overwrite each other's bindings for the shared letter — this is expected and, for a layout arising from a single cyclic permutation of the 4 keys, resolves correctly by construction (each physical key's *sent character* binding, which is what actually matters, is set exactly once and never re-touched). Trace it by hand if the four target characters overlap with `{h,j,k,l}` to be sure, but don't assume overlap is broken — verify via the final assignment table before rewriting the logic.
- When migrating (renaming) this plugin: rename the directory, module doc comments, `descriptions` table (which describes each **letter's own default vim meaning**, for the `:XHelp` cheatsheet — update to match what the new displaced letters actually do), user commands (`XToggle`/`XHelp`), augroup name, `vim.notify` message prefixes, and the `require(...)` call in `keymaps.lua`. Do a full `grep -rin "<oldname>" ~/.config/nvim` pass to catch every reference — don't rely on memory of what you touched.
