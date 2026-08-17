---
name: omarchy-colemak-dh-setup
description: "Use when switching an Omarchy/Hyprland system keyboard layout to Colemak-DH (or adding a second/alt layout with a switch hotkey), toggling/disabling it temporarily, or when hjkl-style navigation in Neovim needs to keep working after such a layout change."
---

Config file location (this machine): `~/.config/hypr/input.lua`, NOT `input.conf` — despite what filename you'd expect, Omarchy's Hyprland config here is Lua-based (`hl.config({ input = { ... } })`), not the classic `.conf` ini-style. Always `glob ~/.config/hypr/*.conf` first if unsure; `input.conf` may not exist even though `hyprlock.conf`/`hypridle.conf` do.

Two-layout Colemak-DH setup pattern in `input.lua`:
```lua
kb_layout = "us,us",
kb_variant = "colemak_dh,",
kb_options = "caps:backspace,grp:alts_toggle",
```
- `grp:alts_toggle` binds Left Alt + Right Alt to switch between the two layout slots.
- Second `us` slot + `colemak_dh,` variant (note trailing comma, second slot has no variant) gives you US-QWERTY on slot 1, Colemak-DH on slot 2.

To temporarily disable Colemak-DH (revert to plain single-layout US) without losing the setup for later restoration: comment out the three multi-layout lines with `--` and replace with plain single-layout equivalents directly below:
```lua
-- kb_layout = "us,us",
-- kb_variant = "colemak_dh,",
-- kb_options = "caps:backspace,grp:alts_toggle",
kb_layout = "us",
kb_options = "caps:backspace",
```
Drop `kb_variant` entirely (US has none) and drop `grp:alts_toggle` from `kb_options` (no second layout to toggle to). Restore later by deleting the two plain lines and uncommenting the three original ones.

Apply changes live with `hyprctl reload` (no logout/relogin needed).

Also see: `nvim/lua/colemak-dh/init.lua` remaps hjkl-style nav for when Colemak-DH is the active system layout — irrelevant while Colemak-DH is disabled, no need to touch it for a layout toggle.
