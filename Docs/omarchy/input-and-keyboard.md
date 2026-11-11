# Input and keyboard

Omarchy/Hyprland input: CJK input methods via fcitx5, and custom XKB layouts (Colemak-DH, Gallium).

## CJK (Japanese/Korean/Chinese) typing

**Symptom:** Need kanji/hangul/pinyin typing; adding an XKB layout doesn't work.

**Cause:** CJK input is NOT an XKB layout. Do not edit `kb_layout` in `~/.config/hypr/input.lua`. Omarchy layers fcitx5 input methods on top of the XKB layout; `grp:alts_toggle` keeps toggling XKB groups independently.

**Fix:**
1. Inspect state:
```sh
cat ~/.config/fcitx5/profile   # only keyboard-us = nothing added
pacman -Qs fcitx5               # fcitx5-mozc may already be installed
pgrep -a fcitx5
```
2. Run `omarchy setup input mozc` (others: `hangul`, `pinyin`, `chewing`, `cangjie5`). It installs the package via omarchy-pkg-add only if missing (sudo only then), adds the engine to the live fcitx group/profile, and writes `~/.config/fontconfig/conf.d/50-omarchy-input-method.conf` (Noto CJK JP fallback). If unsure, read `$(which omarchy-setup-input)` and `/usr/share/omarchy/default/input-methods/typing_setup.py` first.
3. Verify: `omarchy-input-method cycle` (same path as SUPER+I) and `fcitx5-remote -n`; `hyprctl configerrors` must be empty (set HYPRLAND_INSTANCE_SIGNATURE from `ls -t /run/user/$UID/hypr | head -1` in an agent shell). Reset with `fcitx5-remote -s keyboard-us` afterwards.
   - `fcitx5-remote -s mozc` from an agent shell only changes the focused input context; the shell's InputMethodState reader does NOT see it. Test with `omarchy-input-method cycle` instead.

**Keys:** SUPER+I / SUPER+SHIFT+I cycle input methods (ring: each XKB group as `keyboard-us@idx`, then each engine). Henkan/Muhenkan/Zenkaku_Hankaku are in `~/.config/fcitx5/config`. Mozc: type romaji, Space converts to kanji, Enter commits.

**Caveats:**
- The bar's layout widget reads Hyprland's XKB layout, so it won't show JA when Mozc is active.
- `fc-match sans:lang=ja` may still say Liberation Sans; the fontconfig alias handles fallback.
- Dotfiles repo is bare (`git --git-dir=$HOME/.dotfiles --work-tree=$HOME`); stage only touched files.

_Migrated from: omarchy-add-japanese-kanji-input_

## Custom XKB layouts (Colemak-DH, Gallium)

**Symptom:** Setting up or debugging an alternative layout not shipped by the OS.

**Cause:** Layouts like Gallium are NOT in `/usr/share/X11/xkb/symbols/`; `localectl list-x11-keymap-variants us` won't list them. Config here is Lua: `~/.config/hypr/input.lua` (`hl.config({ input = { ... } })`), not `input.conf`.

**Fix — two-layout alt-toggle pattern in `input.lua`:**
```lua
kb_layout = "us,us",
kb_variant = "<slot1-variant>,<slot2-variant>",
kb_options = "caps:backspace,grp:alts_toggle",
```
- `grp:alts_toggle` = Left Alt + Right Alt switches slots. Empty variant = plain QWERTY in that slot (e.g. `kb_variant = ",gallium"`).
- Apply live with `hyprctl reload` — but see the caching gotcha below.
- To temporarily disable: comment the three lines with `--` and add plain single-layout equivalents below (`kb_layout = "us"`, `kb_options = "caps:backspace"`).

**Fix — adding a custom XKB variant:**
1. In `/usr/share/X11/xkb/symbols/us`, look at an existing block (e.g. `xkb_symbols "de_se_fi"`) for syntax, then append `xkb_symbols "<name>"` that does `include "us(basic)"` and overrides only differing keys using XKB physical key codes. Standard US ANSI names in this file:
   - Top: `AD01`-`AD10` (QWERTY Q..P), `AD11`/`AD12` = `[`/`]`.
   - Home: `AC01`-`AC09`, then `AC10` = `;`/`:`, `AC11` = `'`/`"` (11-key row — defining only AC01-AC10 silently shifts everything).
   - Bottom: `AB01`-`AB07` (Z X C V B N M), then `AB08` = `,`, `AB09` = `.`, `AB10` = `/` with shift-pair names (`comma/less`, `period/greater`, `slash/question`, `apostrophe/quotedbl`, `semicolon/colon`).
   - End with `include "level3(ralt_switch)"`.
2. Needs root — use an interactive-tty sudo path (fingerprint prompt), not plain non-interactive `sudo`.
3. No XML registration needed: `/usr/share/X11/xkb/rules/evdev.xml` is only for GUI pickers; Hyprland resolves via the generic `%l(%v)` rule in `rules/evdev`.
4. Validate on Wayland with `xkbcli compile-keymap --layout us,us --variant ,<name> --options grp:alts_toggle` (from `libxkbcommon-tools`) — the exact path Hyprland uses. Don't use `setxkbmap`/`xkbcomp` (X11-only, confusing errors). Grep the output for the key codes you care about.
5. Then apply the caching fix below — clean `xkbcli` output proves the file, not that the compositor picked it up.

**Gotcha — Hyprland caches the compiled keymap by config value:** if you edit `symbols/us` while `kb_variant` in `input.lua` is literally unchanged, `hyprctl reload` does NOT pick it up. Force recompilation: set `kb_variant = ","`, `hyprctl reload`, then set it back and `hyprctl reload` again. `hyprctl keyword input:kb_variant ...` errors on the Lua parser ("use eval") — always go through editing `input.lua`.

**Source layouts authoritatively:** search for the layout's own GitHub repo (e.g. `GalileoBlues/Gallium` ships `Linux/xkb/gallium_rowstag`); cross-check ambiguous rows against repo diagrams (for SVGs, grep raw XML for `>LETTER<` and preceding `translate(x,y)` — same `y` = same physical row). Watch for sub-variant proliferation (v1/v2, Rowstag/Colstag/Angle) — a disagreeing image may be a different sub-variant.

_Migrated from: omarchy-colemak-dh-setup_

## Typing CJK while on Gallium + hiding the Gallium cheat sheet

**Symptom:** Mozc receives Gallium keys (it inherits the active Hyprland xkb group); the Gallium cheat-sheet overlay is noise during CJK input.

**Cause:** Setting per-engine `Layout=us` in the fcitx profile does NOT move Hyprland's group on Wayland (tested; reverted).

**Fix:** In `~/.config/omarchy/plugins/wils.gallium-cheatsheet/Gallium.qml`, read `InputMethodState.state.current` (from `qs.Commons`). `cjkActive` = current non-empty and not starting with `keyboard-`. `onCjkActiveChanged: if (cjkActive && galliumActive) run hyprctl switchxkblayout all 0`. Panel `visible: galliumActive && !cjkActive`. Do NOT add a "restore Gallium on leaving CJK" step — it makes plain US unreachable via SUPER+I (ring becomes US>Gallium>mozc>Gallium...). Without restore the ring is US>Gallium>mozc(on US)>US.

**Gotcha — plugin hot-reload is unreliable:** "Local plugin changed" may log while old code keeps running. `omarchy restart shell` (wait ~9s; "notification service did not become ready" is harmless) loads new code. `console.log` may not reach journalctl; prove execution with a probe Process appending to a /tmp file, then remove it.

_Migrated from: omarchy-add-japanese-kanji-input_

## nvim physical-hjkl plugin for alt-layouts

**Symptom:** hjkl navigation breaks under an alt-layout.

**Cause:** Keys send different characters.

**Fix:** This machine has a small plugin at `~/.config/nvim/lua/<name>/init.lua`, loaded via `require("<name>").setup()` in `~/.config/nvim/lua/config/keymaps.lua`. It bidirectionally swaps vim keymaps: `M.default_pairs = { {"h", <char physical-h sends>}, ... }`.
- Physical positions: `AC06`=physical-h, `AC07`=physical-j, `AC08`=physical-k, `AC09`=physical-l. Get sent-chars from the validated compiled keymap (`xkbcli compile-keymap` output), not memory.
- `set_pair(a,b)` is a full symmetric swap; overlap with `{h,j,k,l}` (e.g. Gallium physical-j sends "h") resolves correctly for single-cyclic-permutation layouts — trace the final assignment table before rewriting logic.
- Renaming the plugin: rename dir, doc comments, `descriptions` table (each letter's own default vim meaning, for `:XHelp`), `XToggle`/`XHelp` commands, augroup, `vim.notify` prefixes, and the `require` in `keymaps.lua`. Then `grep -rin "<oldname>" ~/.config/nvim`.

_Migrated from: omarchy-colemak-dh-setup_
