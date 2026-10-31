---
name: omarchy-screensaver-unsupported-default-terminal
description: "Omarchy screensaver problems: old omarchy-dev needed a kitty override for unsupported default terminal (tern); omarchy-dev 4.x is native layer-shell and the override must be deleted (\"Failed to launch child: omarchy-screensaver\")."
---

# Omarchy screensaver with a non-standard default terminal (e.g. tern)

## Check the omarchy-dev version first
`pacman -Qi omarchy-dev`, and `cat /usr/bin/omarchy-launch-screensaver`.

### omarchy-dev >= 4.0 (native Wayland layer-shell screensaver): NO override needed
`/usr/bin/omarchy-launch-screensaver` is a 2-line wrapper: `exec /usr/lib/omarchy-screensaver/omarchy-screensaver "$@"`.
No terminal, no `omarchy-screensaver` child command. Any terminal-based local override is obsolete.

**Symptom of a stale override:** a terminal window reading `Failed to launch child: omarchy-screensaver / With error: No such
file or directory / Press Enter or Esc to exit` (the old override runs `kitty -e omarchy-screensaver`, which no longer exists).

**Fix:** `rm ~/.local/bin/omarchy-launch-screensaver; hash -r`. The user confirmed the stock wrapper then shows the overlay.

### omarchy-dev 3.x (terminal-based screensaver): override needed for tern
`/usr/bin/omarchy-launch-screensaver` runs `xdg-terminal-exec --print-id` and bails with the `screensaver.terminalOnly`
notification unless the id matches Alacritty/ghostty/foot/kitty. User's default is tern.
1. `cp /usr/bin/omarchy-launch-screensaver ~/.local/bin/ && chmod +x` it.
2. Replace the terminal detection and bail-out with `terminal=kitty` plus a `command -v kitty` guard.
3. Mark it a LOCAL OVERRIDE; **after every omarchy update, diff against the packaged script and delete the override if the
   package changed architecture** (this is exactly what broke on 4.0).

## Testing gotchas (4.x)
- The binary is single-instance (lock `$XDG_RUNTIME_DIR/omarchy-screensaver.lock` holding a PID). If one is already showing,
  every further launch exits 0 immediately with no layer: this looks like a failure but isn't. Check `pgrep -af omarchy-screensaver`
  and the screen before concluding it is broken. Don't spam repeated test launches; the user may be looking at the overlay.
- Agent shells lack Hyprland env: export `XDG_RUNTIME_DIR=/run/user/1000`, `WAYLAND_DISPLAY=wayland-1`,
  `HYPRLAND_INSTANCE_SIGNATURE=$(ls /run/user/1000/hypr/ | head -1)`.
- Layer check: `hyprctl layers | grep org.omarchy.screensaver`. Clean up with `pkill -f 'omarchy-screensaver/omarchy-screensaver'`.
- Custom text: `~/.config/omarchy/branding/screensaver.txt`.
