# Hyprland Troubleshooting

hyprctl from agent shells, XWayland oversized UI, and Omarchy toggle flags stuck on.

## hyprctl from an agent shell

**Symptom:** `hyprctl` fails with `HYPRLAND_INSTANCE_SIGNATURE not set!` even though Hyprland is running — agent bash is not inside the Hyprland session.

**Cause:** the signature env var is only set in GUI-shell sessions.

**Fix:**

```bash
export HYPRLAND_INSTANCE_SIGNATURE=$(ls -t /run/user/$(id -u)/hypr/ | head -1)
hyprctl reload
hyprctl configerrors      # empty output = config parses clean
LOG=/run/user/$(id -u)/hypr/$HYPRLAND_INSTANCE_SIGNATURE/hyprland.log
```

Export must be repeated in each bash call (state does not persist reliably). Empty `configerrors` after a fresh reload means the config is fine now; the user's error may have been transient — ask what the error text says instead of guessing. The log is dominated by libinput DEBUG lines; filter: `grep -aE "^(ERR|WARN)" "$LOG" | grep -av libinput | tail -40`. `ERR from aquamarine` lines (nested Wayland backend failing, `eglQueryDevicesEXT EGL_BAD_ALLOC`, `getCurrentCRTC: No CRTC 0`, `Cannot commit when a page-flip is awaiting`) are backend startup noise, not config errors. Check `ls -lt ~/.config/hypr/` for recently edited files (bindings.lua, monitors.lua, ...) as suspects. Omarchy uses Lua config (`~/.config/hypr/*.lua`).

_Migrated from: hyprctl-from-agent-shell-instance-signature_

## Oversized UI for an XWayland app (fractional monitor scale)

**Symptom:** app UI too zoomed/large on fractional monitor scale; asked for a "window rule for 0.5x zoom".

**Cause:** Hyprland window rules (`o.window` / `hl.window_rule`) have NO per-window scale/zoom effect. Don't write one; fix the app's own scale.

**Fix:**

1. Diagnose: `hyprctl clients -j | jq` → class, pid, `xwayland` flag; `hyprctl monitors -j | jq '.[].scale'`. Check `/proc/<pid>/environ` and `/proc/<pid>/exe`; `pacman -Qo` the binary; read `/usr/share/applications/<id>.desktop`. Check the app's own config for a scale key (e.g. PhotoCraft `~/.config/photocraft/preferences.json` has `uiScale: "auto"`, accepted values undocumented — don't guess).
2. winit/egui apps on XWayland: `WINIT_X11_SCALE_FACTOR=<float>` overrides DPI (winit string: "invalid; DPI factors must be floats > 0 or `randr`").
3. User-level fix (never edit /usr/share): copy the system `.desktop` to `~/.local/share/applications/<same-id>.desktop` and change only `Exec=env WINIT_X11_SCALE_FACTOR=1.25 <app> %F`. Run `desktop-file-validate`. Applies only to menu/file-association launches; terminal launches need the env var or an alias.
4. Verify by screenshot comparison: launch a throwaway instance with an isolated config dir (e.g. `PHOTOCRAFT_CONFIG_DIR=/tmp/x`) so it doesn't single-instance onto the running window; `cmd > log 2>&1 &` in the foreground shell worked (`setsid ... &` with subshell form silently failed). `grim -g "X,Y WxH"` the new client's region (from `hyprctl clients -j`), confirm the client class first. Launch via `gtk-launch <desktop-id>` to prove the override is used, check the env var in the new pid's environ, then kill only the test pid and rm temp dirs. Scale 1 gave ~half the original on a 1.25 monitor; user chose 1.25 — offer other values rather than assuming the factor.

_Migrated from: hyprland-xwayland-app-ui-too-large-scale-override_

## Accidental look-and-feel change = stray Omarchy toggle

**Symptom:** sudden global visual/behavior change after an unknown shortcut — e.g. 0px window gaps, no rounding, borders gone, touchpad/touchscreen disabled — with no edit to `~/.config/hypr/looknfeel.lua`.

**Cause:** Omarchy implements toggleable flags via generated Lua files in `~/.local/state/omarchy/toggles/hypr/*.lua`, loaded at reload by `default.hypr.toggles` (required from `hyprland.lua`), which calls `hl.config({...})` on top of user config. A bound key (e.g. via `omarchy hyprland window gaps toggle`) flips one of these files into existence/deletion. Example: `window-no-gaps.lua` sets `gaps_out=0`, `gaps_in=0`, `border_size=0`, `decoration.rounding=0`.

**Fix:**

1. List `~/.local/state/omarchy/toggles/hypr/` — the newest file is the culprit; read it to confirm.
2. Infer the command from the filename (`window-no-gaps.lua` → gaps toggle); cross-check via `omarchy commands --json | grep -i gap`.
3. Re-run that same toggle command (e.g. `omarchy hyprland window gaps toggle`) — it flips state back and removes the override file.

Do NOT hand-edit `looknfeel.lua` or manually delete the toggle file — the paired `omarchy ... toggle` command is the supported idempotent flip.

_Migrated from: omarchy-hyprland-toggles-stuck-on_
