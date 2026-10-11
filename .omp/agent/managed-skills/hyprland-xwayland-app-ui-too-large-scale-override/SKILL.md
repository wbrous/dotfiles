---
name: hyprland-xwayland-app-ui-too-large-scale-override
description: App UI too zoomed/large on Hyprland fractional monitor scale; user asks for window rule zoom/scale; XWayland winit/egui apps (e.g. PhotoCraft).
---

# Oversized UI for an XWayland app on Hyprland (fractional monitor scale)

## Key fact
Hyprland window rules (`o.window` / `hl.window_rule`) have NO per-window scale/zoom effect. If asked for a "window rule for 0.5x zoom", don't write one; fix the app's own scale instead and tell the user why.

## Diagnosis
1. `hyprctl clients -j | jq` -> find class, pid, `xwayland` flag; `hyprctl monitors -j | jq '.[].scale'`.
2. `/proc/<pid>/environ` and `/proc/<pid>/exe`; `pacman -Qo` the binary; read `/usr/share/applications/<id>.desktop`.
3. Check the app's own config for a scale key (e.g. PhotoCraft `~/.config/photocraft/preferences.json` has `uiScale: "auto"`, but accepted values are undocumented; don't guess).
4. winit/egui apps on XWayland: `WINIT_X11_SCALE_FACTOR=<float>` overrides DPI (winit string: "invalid; DPI factors must be floats > 0 or `randr`").

## Fix (user-level, never edit /usr/share)
Copy the system `.desktop` to `~/.local/share/applications/<same-id>.desktop` and change only:
`Exec=env WINIT_X11_SCALE_FACTOR=1.25 <app> %F`
Run `desktop-file-validate`. Applies only to menu/file-association launches; terminal launches need the env var or an alias.
When editing with the line-hash edit tool, re-read afterwards: a PUT replacing lines can duplicate the old Exec line or drop neighbours (Comment=).

## Verification (screenshot comparison)
- Launch a throwaway instance with `PHOTOCRAFT_CONFIG_DIR=/tmp/x` (or equivalent) so it doesn't single-instance onto the running window and doesn't touch real prefs.
- `setsid ... &` with the subshell form silently failed; `cmd > log 2>&1 &` in the foreground shell worked.
- `grim -g "X,Y WxH" out.png` on the new client's region (from `hyprctl clients -j`), then read the image. Confirm the client class before trusting the shot.
- Launch via `gtk-launch <desktop-id>` to prove the override is used, check `WINIT_X11_SCALE_FACTOR` in the new pid's environ, then kill only the test pid (keep the user's original pid) and rm temp dirs.
- Scale 1 gave ~half the original size on a 1.25 monitor; user ultimately chose 1.25 (which still looked far smaller than the original). Ask/offer other values rather than assuming the factor.
