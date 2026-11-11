---
name: omarchy-add-japanese-kanji-input
description: "User wants kanji/Japanese/Korean/Chinese typing in Omarchy/Hyprland language switcher; XKB can't do CJK, use fcitx5 via omarchy setup input. Also: CJK typed on Gallium, or Gallium cheat sheet showing under CJK."
---

## Rule
CJK input is NOT an XKB layout (don't edit `kb_layout` in ~/.config/hypr/input.lua). Omarchy uses fcitx5 input methods layered on top of the XKB layout; Alt+Alt (grp:alts_toggle) keeps toggling XKB groups independently.

## Procedure (verified, Japanese)
1. Inspect: `cat ~/.config/fcitx5/profile` (only `keyboard-us` = nothing added), `pacman -Qs fcitx5` (fcitx5-mozc may already be installed), `pgrep -a fcitx5`.
2. Run `omarchy setup input mozc` (others: hangul, pinyin, chewing, cangjie5). It installs the package via omarchy-pkg-add only if missing (sudo only then), adds the engine to the live fcitx group/profile, and writes `~/.config/fontconfig/conf.d/50-omarchy-input-method.conf` (Noto CJK JP fallback). Read `$(which omarchy-setup-input)` and `/usr/share/omarchy/default/input-methods/typing_setup.py` first if unsure.
3. Verify: `omarchy-input-method cycle` (same path as SUPER+I) and `fcitx5-remote -n`; `hyprctl configerrors` empty (set HYPRLAND_INSTANCE_SIGNATURE from `ls -t /run/user/$UID/hypr | head -1` in agent shell). Reset with `fcitx5-remote -s keyboard-us` afterwards.
   - `fcitx5-remote -s mozc` from an agent shell only changes the focused input context; the shell's InputMethodState reader does NOT see it. Test with `omarchy-input-method cycle` instead.

## Keys
SUPER+I / SUPER+SHIFT+I cycle input methods (ring: each XKB group as keyboard-us@idx, then each engine). Henkan/Muhenkan/Zenkaku_Hankaku are in ~/.config/fcitx5/config. Mozc: type romaji, Space converts to kanji, Enter commits.

## Typing CJK on Gallium (user does not want this) and hiding the Gallium cheat sheet
- Mozc inherits the active Hyprland xkb group, so from Gallium it receives Gallium keys.
- Setting per-engine `Layout=us` in the fcitx profile does NOT move Hyprland's group on Wayland (tested; reverted). Don't retry.
- Working fix: in ~/.config/omarchy/plugins/wils.gallium-cheatsheet/Gallium.qml, read `InputMethodState.state.current` (from `qs.Commons`, already live in the shell). `cjkActive` = current non-empty and not starting with `keyboard-`. `onCjkActiveChanged: if (cjkActive && galliumActive) run hyprctl switchxkblayout all 0`. Panel `visible: galliumActive && !cjkActive`.
- Do NOT add a "restore Gallium on leaving CJK" step: it overrides the ring's choice and makes plain US unreachable via SUPER+I (ring becomes US>Gallium>mozc>Gallium...). With no restore the ring is US>Gallium>mozc(on US)>US.

## Plugin hot-reload is unreliable
After editing a local plugin QML, "Local plugin changed" is logged but old code can keep running (a debug Timer/console.log never fired). `omarchy restart shell` (wait ~9s; "notification service did not become ready" warning is harmless) loads the new code. Plugin `console.log` doesn't reliably reach journalctl; prove execution by a probe Process that appends to a /tmp file, then remove it.

## Caveats
- The bar's layout widget reads Hyprland's XKB layout, so it won't show JA when Mozc is active.
- `fc-match sans:lang=ja` may still say Liberation Sans; the fontconfig alias handles fallback.
- Agent can't physically type to prove kanji output; state that limit.
- Dotfiles repo is bare (`git --git-dir=$HOME/.dotfiles --work-tree=$HOME`) with many unrelated dirty files; stage only touched files.
