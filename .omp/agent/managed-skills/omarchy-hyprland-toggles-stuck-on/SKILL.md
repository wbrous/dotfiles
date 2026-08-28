---
name: omarchy-hyprland-toggles-stuck-on
description: "Use when an Omarchy/Hyprland system suddenly shows an unexpected global look-and-feel change (e.g. 0px window gaps, no window rounding, borders gone) after the user hit an unknown/accidental keyboard shortcut — check ~/.local/state/omarchy/toggles/hypr/ for a stray toggle file rather than editing looknfeel.lua."
---

## Symptom

User reports a sudden, unexplained global Hyprland visual/behavior change after
pressing some keyboard shortcut — e.g. "windows are 0px apart and no rounding",
touchpad/touchscreen disabled, etc. — with no corresponding edit made to
`~/.config/hypr/looknfeel.lua` or other user config files.

## Root cause

Omarchy implements toggleable feature flags via generated Lua files dropped in
`~/.local/state/omarchy/toggles/hypr/*.lua`. These are loaded at Hyprland config
reload time by `default.hypr.toggles` (required from `hyprland.lua`), which calls
`hl.config({...})` to override settings on top of the user's normal config. A
bound key (e.g. via `omarchy hyprland window gaps toggle`) flips one of these
files into existence/deletion.

Example: `window-no-gaps.lua` sets `gaps_out=0`, `gaps_in=0`, `border_size=0`,
`decoration.rounding=0` — exactly matching "0px apart, no curving" symptoms.

## Fix

1. List `~/.local/state/omarchy/toggles/hypr/` to see which toggle file appeared
   (or check timestamps — the newest one is the culprit).
2. Read its content to confirm what it changes and infer the command name from
   its filename (e.g. `window-no-gaps.lua` → gaps toggle).
3. Cross-check via `omarchy commands --json | grep -i gap` (or relevant keyword)
   to find the exact matching command route, e.g.
   `omarchy hyprland window gaps toggle`.
4. Re-run that same toggle command — it flips state back and removes the
   override file, restoring the user's normal `looknfeel.lua` settings.

Do NOT hand-edit `looknfeel.lua` or manually delete the toggle file for this —
the paired `omarchy ... toggle` command is the supported, idempotent way to
flip it back and keeps `~/.local/state/omarchy/toggles/hypr/` in sync with
whatever other state the toggle script manages.
