---
name: zen-browser-set-space-theme-color
description: "Set Zen Browser workspace (space) theme to specific colors, e.g. match Catppuccin or the tab bar color, by editing zen-sessions.jsonlz4."
---

## When
User wants Zen Browser spaces (workspaces) themed with exact colors (Catppuccin accent, tab bar color, etc.). To only clear themes, see `zen-browser-clear-space-themes`.

## Facts (verified on Zen 1.23.x, Linux)
- Space themes live in `~/.config/zen/<profile>/zen-sessions.jsonlz4` (mozlz4: 8-byte magic `mozLz40\0` + lz4 block with size header). Top-level key `spaces[]`, each with `name`, `uuid`, `icon`, `containerTabId`, `theme`.
- Active profile = the `Default=` path under `[Install...]` in `~/.config/zen/profiles.ini`.
- Zen rewrites the file on shutdown, so MUST confirm `pgrep -af zen-bin` is empty before editing, else edits are overwritten.
- Also patch `zen-sessions-backup/clean.jsonlz4` and `recovery.baklz4` (same format), or a restore brings old themes back. Leave dated hourly backups alone.
- No lz4 python module installed; use `uv run --with lz4 python`. `omni.ja` is not a normal zip (python zipfile and unzip fail); `strings omni.ja` reveals the source (ZenGradientGenerator, getTheme).

## Theme shape
`{"type":"gradient","gradientColors":[ENTRY,...],"opacity":0.25,"texture":0.0625}`
Empty `gradientColors` = no theme (new-space default, opacity 0.5, texture 0).
ENTRY (non-custom):
`{"c":[r,g,b],"isCustom":false,"algorithm":"floating","isPrimary":true,"lightness":"50","type":"explicit-lightness","position":{"x":..,"y":..}}`
Only one entry should have `isPrimary: true`. `position` mirrors the picker dot: with `h,l,s = colorsys.rgb_to_hls(r/255,g/255,b/255)`, `x=round(190+190*s*cos(h*2π))`, `y=round(190+190*s*sin(h*2π))`.

## Procedure
1. Check Zen not running; copy zen-sessions.jsonlz4 to /tmp as a backup.
2. Decode, assert tabs unchanged after edit (compare json of `d["tabs"]`), set each space's theme, re-encode with `lz4.block.compress(..., store_size=True)`, prefix magic.
3. Apply to the live file and the two fallback copies; read back and print names, colors, tab count.
4. Tell the user it is unverified visually until Zen is restarted.

## Catppuccin Mocha reference
Tab bar (`#TabsToolbar` in the theme's userChrome.css) = Mantle `#181825`; Mauve `#cba6f7`; Blue `#89b4fa`. When user says "the tab bar color", read it from chrome/userChrome.css rather than guessing. Mantle is near-black so opacity 0.25 gives a subtle tint.
