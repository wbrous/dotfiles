---
name: omarchy-colemak-dh-setup
description: "Use when setting up, switching, or debugging alternative keyboard layouts (Colemak-DH, Gallium, or similar non-stock layouts) on this Omarchy/Hyprland machine — covers the input.lua multi-layout/alts_toggle pattern, adding a custom XKB variant for layouts not shipped in /usr/share/X11/xkb (like Gallium), sourcing/validating a layout against its authoritative upstream definition, the Hyprland keymap-recompile caching gotcha after editing the XKB symbols file in place, and reprogramming the physical-hjkl-navigation nvim plugin (colemak-dh/gallium) to match a new layout's letter permutation."
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
- Apply live with `hyprctl reload` (no logout/relogin needed) — **but see the recompile-caching gotcha below** if you only edited the underlying XKB symbols file, not `input.lua` itself.

To temporarily disable a multi-layout setup: comment out the three multi-layout lines with `--` and add plain single-layout equivalents (`kb_layout = "us"`, `kb_options = "caps:backspace"` — no `kb_variant`, no `grp:alts_toggle`) directly below, so it's easy to restore later.

## CRITICAL: Hyprland caches the compiled keymap by config *value*, not by XKB file content
If you edit `/usr/share/X11/xkb/symbols/us` (e.g. fixing a broken custom variant block) while `input.lua`'s `kb_variant` string stays literally unchanged (e.g. still `",gallium"`), `hyprctl reload` alone will **NOT** pick up the new XKB file — Hyprland only recompiles the keymap when the config value itself changes, so the stale in-memory keymap keeps being used silently. Symptom: you fix the symbols file, verify it's correct via `xkbcli compile-keymap`, but the running system still behaves like the old (wrong) layout.

Fix: force a value change to trigger recompilation —
1. Edit `input.lua`: temporarily set `kb_variant = ","` (blank both slots), `hyprctl reload`.
2. Edit `input.lua` back to the real value (e.g. `kb_variant = ",gallium"`), `hyprctl reload` again.

`hyprctl keyword input:kb_variant ...` does NOT work on this machine's non-legacy Lua config parser (errors "keyword can't work with non-legacy parsers. Use eval.") — must go through editing `input.lua` + `hyprctl reload`, not `hyprctl keyword`.

## Adding a custom XKB variant not shipped by the OS (e.g. Gallium)
Gallium (and many alt layouts) are NOT in `/usr/share/X11/xkb/symbols/`. `localectl list-x11-keymap-variants us` won't list them. You must add a variant block yourself:

1. Find the OS's `us` symbols file: `/usr/share/X11/xkb/symbols/us`. Look at existing variant blocks (e.g. `xkb_symbols "de_se_fi"`) for the exact syntax/convention.
2. Append a new `xkb_symbols "<name>"` block that `include "us(basic)"` then overrides only the keys that differ, using XKB physical key codes. **Standard US ANSI key names from `us(basic)` in this file** (verify by grepping the base block, don't assume):
   - Top row: `AD01`-`AD10` (QWERTY Q W E R T Y U I O P), plus `AD11`/`AD12` for `[`/`]`.
   - Home row: `AC01`-`AC09` (QWERTY A S D F G H J K L), then `AC10` = `;`/`:` and `AC11` = `'`/`"` — an 11-key row, not 10. A common bug is only defining `AC01`-`AC10` for 10 letters and skipping `AC11`, which silently shifts everything and drops the layout's 11th home-row symbol.
   - Bottom row: `AB01`-`AB07` (QWERTY Z X C V B N M — 7 letter keys), then `AB08` = `,`/`<`, `AB09` = `.`/`>`, `AB10` = `/`/`?`. A common bug is treating `AB08`-`AB10` as extra letter slots instead of the punctuation-capable keys they actually are.
   - Punctuation keys need proper shift-pair symbol names, e.g. `comma/less`, `period/greater`, `slash/question`, `apostrophe/quotedbl`, `semicolon/colon`.
   - End with `include "level3(ralt_switch)"`.
3. Editing `/usr/share/X11/xkb/symbols/us` needs root — use the `sudo-interactive-tty-via-hub` skill (`hub op=start application=sudo args=["python3","/path/to/script.py"] pty=true`, e.g. a small Python script that does an in-place block replace) rather than plain bash `sudo` (fingerprint auth prompt is interactive).
4. **No XML registration needed.** `/usr/share/X11/xkb/rules/evdev.xml` is only for GUI layout pickers (GNOME Settings etc.); Hyprland/libinput/xkbcommon resolve `kb_layout`+`kb_variant` via the generic rule in `/usr/share/X11/xkb/rules/evdev` (plain text, `%l(%v)` pattern), which finds your new `xkb_symbols` block directly. Adding the block to `symbols/us` is sufficient.
5. **Validate on Wayland/Hyprland** with `xkbcli compile-keymap --layout us,us --variant ,<name> --options grp:alts_toggle` (from `libxkbcommon-tools`) — this is the exact resolution path Hyprland uses. Don't bother with `setxkbmap`/`xkbcomp` (X11-only, won't work under Wayland and gives confusing "syntax error" noise even when the symbols file itself is fine). Check the compiled output's `key <ACnn> { symbols[1]=[...qwerty...], symbols[2]=[...new-layout...] }` lines to confirm the right characters landed on the right physical keys — grep the specific key codes you care about, e.g. `grep -A3 "key <AC06>"`.
6. **After validating the symbols file, still apply the Hyprland recompile-caching fix above** — a clean `xkbcli compile-keymap` result proves the file is correct, it does NOT prove the running compositor picked it up.

## Sourcing an authoritative layout definition, not guessing
When told to add/fix a named alt-layout (e.g. Gallium), don't hand-derive the letter grid from a row-staggered "three rows of 10" assumption or a fuzzy web description — that produces exactly the kind of off-by-one/row-confused bugs described above. Instead:
- Search for the layout's own GitHub repo; many ship a ready-made Linux XKB file directly (e.g. `GalileoBlues/Gallium` ships `Linux/xkb/gallium_rowstag` — an actual `xkb_symbols "basic" { include "us(basic)" ... }` block you can adapt key-for-key).
- Cross-check ambiguous rows against any layout diagram/SVG the repo ships (e.g. `Images/Gallium_Rowstag.svg`) — for SVGs, grep the raw XML for `>LETTER<` text elements and their preceding `translate(x,y)` group transform; letters sharing the same `y` value are on the same physical row, which lets you confirm e.g. "P is bottom row" without rendering the image.
- Watch for **layout variant proliferation**: a single named layout (Gallium, Graphite, etc.) often has multiple published sub-variants (v1 vs v2, Rowstag vs Colstag vs Angle) with genuinely different key placements. If a downloaded reference image disagrees with the source you used, don't assume your source is wrong — check whether the image is actually a *different* sub-variant before re-deriving anything.

## Reprogramming the physical-hjkl-navigation nvim plugin for a new layout
This machine has a small nvim plugin (was `colemak-dh`, migrated to `gallium`) at `~/.config/nvim/lua/<name>/init.lua`, loaded via `require("<name>").setup()` in `~/.config/nvim/lua/config/keymaps.lua`. It restores hjkl motion on the physical h/j/k/l keys under an alt-layout by bidirectionally swapping vim keymaps: `M.default_pairs = { {"h", <char physical-h-key now sends>}, {"j", <char physical-j-key sends>}, {"k", ...}, {"l", ...} }`.

- Look up the target layout's letters at the physical h/j/k/l column positions (right-hand home row, columns 6-9 in the AC01-11 grid — i.e. `AC06`=physical-h, `AC07`=physical-j, `AC08`=physical-k, `AC09`=physical-l on standard US ANSI) to get the four sent-characters. Get these from the *validated, compiled* keymap (`xkbcli compile-keymap` output), not from memory of the XKB source you wrote — a transcription slip in one row is exactly the kind of bug that causes this plugin to go stale.
- `set_pair(a,b)` does `keymap.set(a,b)` AND `keymap.set(b,a)` — a full symmetric swap of vim command bindings for those two letters, not a physical-key remap. If the target layout's character set overlaps with `{h,j,k,l}` themselves (e.g. Gallium: physical-j sends "h"), pairs processed in list order will overwrite each other's bindings for the shared letter — this is expected and, for a layout arising from a single cyclic permutation of the 4 keys, resolves correctly by construction (each physical key's *sent character* binding, which is what actually matters, is set exactly once and never re-touched). Trace it by hand if the four target characters overlap with `{h,j,k,l}` to be sure, but don't assume overlap is broken — verify via the final assignment table before rewriting the logic.
- When only one of the four physical keys' sent-character changes (e.g. an XKB fix corrects physical-h from "p" to "y" while j/k/l stay the same), only that one pair, its doc comment, and its `:XHelp` description-table entry need updating — no need to touch the other three pairs.
- When migrating (renaming) this plugin: rename the directory, module doc comments, `descriptions` table (which describes each **letter's own default vim meaning**, for the `:XHelp` cheatsheet — update to match what the new displaced letters actually do), user commands (`XToggle`/`XHelp`), augroup name, `vim.notify` message prefixes, and the `require(...)` call in `keymaps.lua`. Do a full `grep -rin "<oldname>" ~/.config/nvim` pass to catch every reference — don't rely on memory of what you touched.
