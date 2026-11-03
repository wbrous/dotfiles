---
name: hyprctl-from-agent-shell-instance-signature
description: "hyprctl says HYPRLAND_INSTANCE_SIGNATURE not set from agent shell; diagnosing Hyprland config errors, reload, log triage."
---

# hyprctl from an agent shell

Agent bash is not inside the Hyprland session, so `hyprctl` fails with `HYPRLAND_INSTANCE_SIGNATURE not set!` even though Hyprland is running.

## Recipe
```bash
export HYPRLAND_INSTANCE_SIGNATURE=$(ls -t /run/user/$(id -u)/hypr/ | head -1)
hyprctl reload
hyprctl configerrors      # empty output = config parses clean
LOG=/run/user/$(id -u)/hypr/$HYPRLAND_INSTANCE_SIGNATURE/hyprland.log
```
Export must be repeated in each bash call (state does not persist reliably).

## Triage notes
- Empty `configerrors` after a fresh `hyprctl reload` means the config is fine now; the user's error may have been transient (overlay clears once a saved fix loads). Ask what the error text says / where it appears instead of guessing.
- The log is dominated by libinput DEBUG lines; filter them: `grep -aE "^(ERR|WARN)" "$LOG" | grep -av libinput | tail -40`.
- `ERR from aquamarine` lines (nested Wayland backend failing, `eglQueryDevicesEXT EGL_BAD_ALLOC`, `getCurrentCRTC: No CRTC 0`, `Cannot commit when a page-flip is awaiting`) are backend startup noise, not config errors.
- Check `ls -lt ~/.config/hypr/` for recently edited files (bindings.lua, monitors.lua, ...) as suspects.
- Omarchy uses Lua config (`~/.config/hypr/*.lua`); see the `omarchy` skill for edit/validation rules.
