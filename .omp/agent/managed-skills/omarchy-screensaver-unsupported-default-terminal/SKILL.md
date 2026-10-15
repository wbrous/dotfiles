---
name: omarchy-screensaver-unsupported-default-terminal
description: "Omarchy screensaver refuses to run (\"only works in Alacritty, Foot, Ghostty, or Kitty\") because the default terminal is tern or another unsupported one; force kitty."
---

# Omarchy screensaver with unsupported default terminal (e.g. tern)

## Cause
`/usr/bin/omarchy-launch-screensaver` (package omarchy-dev) runs `xdg-terminal-exec --print-id` and bails with the
`screensaver.terminalOnly` notification unless the id matches Alacritty/ghostty/foot/kitty. User's default is tern
(`~/.config/xdg-terminals.list` lists `so.stencil.tern.desktop` first), so it never runs.

## Fix (survives package updates)
`~/.local/bin` precedes `/usr/bin` on PATH, and all callers (hypridle `on-timeout`, shell idle, `omarchy-branding-screensaver`)
use the bare command name, so shadow it:

1. `cp /usr/bin/omarchy-launch-screensaver ~/.local/bin/ && chmod +x` it.
2. Replace `terminal=$(xdg-terminal-exec --print-id)` and the `case $terminal in ... terminalOnly ... esac` bail-out with
   `terminal=kitty` plus a `command -v kitty` guard. Leave the later `case $terminal` (kitty branch) intact.
3. Add a header comment marking it a LOCAL OVERRIDE; after omarchy updates, diff against the packaged script.

## Verify
Agent shells lack Hyprland env. Export `XDG_RUNTIME_DIR=/run/user/1000` and
`HYPRLAND_INSTANCE_SIGNATURE=$(ls /run/user/1000/hypr/)`, run `omarchy-launch-screensaver force`, check
`hyprctl clients -j | jq` for class `org.omarchy.screensaver` and `/proc/<pid>/cmdline` starts with kitty.
Clean up with `pkill -f '[o]rg.omarchy.screensaver'`.

## Notes
- `read` tool does not expand `~`; use absolute paths.
- Fullscreen behaviour of the kitty window wasn't confirmed when first done (Hyprland window rules live in default/hypr/apps/system.lua).
