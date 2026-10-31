---
name: omarchy-screensaver-unsupported-default-terminal
description: "Omarchy screensaver problems: old omarchy-dev needed a kitty override for unsupported default terminal (tern); omarchy-dev 4.x is native layer-shell and the override must be deleted (\"Failed to launch child: omarchy-screensaver\")."
---

# Omarchy screensaver with a non-standard default terminal (e.g. tern)

## Check the omarchy-dev version first
`pacman -Qi omarchy-dev`, and `cat /usr/bin/omarchy-launch-screensaver`.

### omarchy-dev >= 4.0 (native Wayland layer-shell screensaver) — NO override needed
`/usr/bin/omarchy-launch-screensaver` is a 2-line wrapper: `exec /usr/lib/omarchy-screensaver/omarchy-screensaver "$@"`.
No terminal, no `omarchy-screensaver` child command. Any terminal-based local override is obsolete.

**Symptom of a stale override:** a terminal window reading `Failed to launch child: omarchy-screensaver / With error: No such
file or directory / Press Enter or Esc to exit` (the old override runs `kitty -e omarchy-screensaver`, which no longer exists).

**Fix:** `rm ~/.local/bin/omarchy-launch-screensaver; hash -r`. Verified: stock wrapper then maps a layer with
namespace `org.omarchy.screensaver` (`hyprctl layers`) and stays up until killed.

### omarchy-dev 3.x (terminal-based screensaver) — override needed for tern
`/usr/bin/omarchy-launch-screensaver` runs `xdg-terminal-exec --print-id` and bails with the `screensaver.terminalOnly`
notification unless the id matches Alacritty/ghostty/foot/kitty. User's default is tern
(`~/.config/xdg-terminals.list` lists `so.stencil.tern.desktop` first).
1. `cp /usr/bin/omarchy-launch-screensaver ~/.local/bin/ && chmod +x` it (`~/.local/bin` precedes `/usr/bin` on PATH; hypridle,
   shell idle and `omarchy-branding-screensaver` call the bare name).
2. Replace `terminal=$(xdg-terminal-exec --print-id)` and the `case ... terminalOnly ... esac` bail-out with `terminal=kitty`
   plus a `command -v kitty` guard; keep the later kitty `case` branch.
3. Mark it a LOCAL OVERRIDE; **after every omarchy update, diff against the packaged script and delete the override if the
   package changed architecture** (this is exactly what broke on 4.0).

## Verifying from an agent shell
Agent shells lack Hyprland env: export `XDG_RUNTIME_DIR=/run/user/1000`, `WAYLAND_DISPLAY=wayland-1`,
`HYPRLAND_INSTANCE_SIGNATURE=$(ls /run/user/1000/hypr/ | head -1)`.
Backgrounded processes get reaped when the temporary shell ends, so run in the foreground: 
`( sleep 3; hyprctl layers | grep org.omarchy.screensaver ) & timeout 6 omarchy-launch-screensaver force; wait`.
Clean up with `pkill -f 'omarchy-screensaver/omarchy-screensaver'`.

## Notes
- `read` tool does not expand `~`; use absolute paths.
- Custom text: `~/.config/omarchy/branding/screensaver.txt`.
