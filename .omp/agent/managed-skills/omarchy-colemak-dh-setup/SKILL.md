---
name: omarchy-colemak-dh-setup
description: "Use when switching an Omarchy/Hyprland system keyboard layout to Colemak-DH (or adding a second/alt layout with a switch hotkey), or when hjkl-style navigation in Neovim needs to keep working after such a layout change."
---

## Switching system layout to Colemak-DH (Hyprland/Omarchy)

Edit `~/.config/hypr/input.lua`, inside `hl.config({ input = { ... } })`:

```lua
kb_layout = "us,us",
kb_variant = "colemak_dh,",
kb_options = "caps:backspace,grp:alts_toggle",
```

- First layout/variant pair is Colemak-DH, second is plain QWERTY (empty variant).
- `grp:alts_toggle` = switch layouts with **Left Alt + Right Alt** pressed together.
  Do NOT use `grp:alt_switch` — not a valid xkb option name. Valid grp option names
  live in `/usr/share/X11/xkb/rules/base.lst` (grep `grp:`) — check there when unsure,
  e.g. `grp:toggle` = Right Alt alone, `grp:lalt_toggle` = Left Alt alone,
  `grp:alt_shift_toggle` = Alt+Shift, etc.
- Apply with `hyprctl reload`; verify with `hyprctl configerrors` (expect `ok`) and
  `hyprctl devices -j` (look at each keyboard's `active_keymap`).

## Why Neovim's hjkl breaks under Colemak-DH

Colemak-DH remaps physical key *positions*, not characters typed. The physical
h/j/k/l keys now emit different characters:
- physical h-key → types `m`
- physical j-key → types `n`
- physical k-key → types `e`
- physical l-key → types `i`

Vim motions are bound by character, not physical key, so pressing the physical
hjkl block runs vim's default `m`/`n`/`e`/`i` commands (mark/search-next/end-word/
insert) instead of moving the cursor.

Fix: bidirectionally swap each pair (`h↔m`, `j↔n`, `k↔e`, `l↔i`, + uppercase) via
`vim.keymap.set` in normal/visual/operator-pending modes. This is layout-agnostic
(works regardless of where the displaced letters physically land) and lossless —
displaced commands remain reachable via whatever key now emits their letter.

Built exactly this as a self-contained LazyVim module at
`~/.config/nvim/lua/colemak-dh/init.lua` (public `setup()`/`toggle()`/`help()` API,
`:ColemakDHToggle` and `:ColemakDHHelp` commands), wired in via a one-line
`require("colemak-dh").setup()` at the end of `~/.config/nvim/lua/config/keymaps.lua`.

**Integration gotcha**: don't fake a lazy.nvim plugin spec via
`{ dir = vim.fn.stdpath("config"), name = "...", lazy = false, config = ... }` —
lazy silently fails to register it (plugin never appears in `require("lazy.core.config").plugins`,
no error). Just `require()` the module directly from `config/keymaps.lua` (or
`config/autocmds.lua`) — always loaded, no lazy plugin-discovery pitfalls.

**Headless-testing gotcha**: `VeryLazy` fires on `UIEnter`, which never happens
under `nvim --headless` (no UI attaches). Don't test remap loading by deferring
and checking `maparg()` after startup — it'll look broken but isn't. Instead
directly `require("colemak-dh").setup()` in the headless test to validate the
module logic; trust that interactive nvim fires `VeryLazy` normally.
