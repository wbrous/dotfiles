---
name: omarchy-add-japanese-kanji-input
description: "User wants kanji/Japanese/Korean/Chinese typing in Omarchy/Hyprland language switcher; XKB can't do CJK, use fcitx5 via omarchy setup input."
---

## Rule
CJK input is NOT an XKB layout (don't edit `kb_layout` in ~/.config/hypr/input.lua). Omarchy uses fcitx5 input methods layered on top of the XKB layout; Alt+Alt (grp:alts_toggle) keeps toggling XKB groups independently.

## Procedure (verified, Japanese)
1. Inspect: `cat ~/.config/fcitx5/profile` (only `keyboard-us` = nothing added), `pacman -Qs fcitx5` (fcitx5-mozc may already be installed), `pgrep -a fcitx5`.
2. Run `omarchy setup input mozc` (others: hangul, pinyin, chewing, cangjie5). It installs the package via omarchy-pkg-add only if missing (sudo only then), adds the engine to the live fcitx group/profile, and writes `~/.config/fontconfig/conf.d/50-omarchy-input-method.conf` (Noto CJK JP fallback). Read `$(which omarchy-setup-input)` and `/usr/share/omarchy/default/input-methods/typing_setup.py` first if unsure.
3. Verify without typing: `fcitx5-remote -n` (current IM), `fcitx5-remote -s mozc`, then `omarchy-input-method cycle`; `hyprctl configerrors` empty (set HYPRLAND_INSTANCE_SIGNATURE from `ls -t /run/user/$UID/hypr | head -1` in agent shell). Reset with `fcitx5-remote -s keyboard-us` afterwards.

## Keys
SUPER+I / SUPER+SHIFT+I cycle input methods (bound in /usr/share/omarchy/default/hypr/bindings/input-method.lua). Henkan/Muhenkan/Zenkaku_Hankaku are in ~/.config/fcitx5/config. Mozc: type romaji, Space converts to kanji, Enter commits.

## Caveats
- The bar's layout widget reads Hyprland's XKB layout, so it won't show JA when Mozc is active.
- `fc-match sans:lang=ja` may still say Liberation Sans; the fontconfig alias handles fallback.
- Agent can't physically type to prove kanji output; state that limit.
