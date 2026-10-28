---
name: omarchy-add-theme-background-fit-display
description: Add a user wallpaper to an Omarchy theme (e.g. Ristretto) and fix it being cropped on a non-16:9 display
---

## Where to put it
- System themes live in root-owned `/usr/share/omarchy/themes/<theme>/backgrounds/` (overwritten on update). Do NOT write there.
- Add user images to `~/.config/omarchy/backgrounds/<theme>/` (mkdir -p). `omarchy-theme-bg-next` and `omarchy-theme-set` scan both dirs (jpg/png/webp/etc.), so it joins the rotation.
- Current theme name: `cat ~/.local/state/omarchy/current/theme.name`.
- Apply: `omarchy theme bg next` or `omarchy-theme-bg-set <path>`.
- Copy, don't move, the file from ~/Downloads.

## Cropping problem
- The wallpaper renderer (quickshell, `/usr/share/omarchy/shell/plugins/background/Background.qml`) uses `Image.PreserveAspectCrop`: fills the screen and crops overflow. A 16:9 image on a 3:2 panel loses its SIDES (not top/bottom).
- To keep everything visible, pad rather than crop: scale to the panel width and extend height with the image's flat background colour.

## Getting the display resolution
- `hyprctl` may fail from a non-Hyprland shell (HYPRLAND_INSTANCE_SIGNATURE unset; `-j` can print binary garbage). Use `cat /sys/class/drm/card*-eDP-1/modes | head -1` (first line = preferred mode). Wils's laptop: 2880x1920 (3:2), scale 1.6 in `~/.config/hypr/monitors.lua`.

## Recipe
1. Sample the bg colour at corners/edges: `magick img.png -format "%[pixel:p{5,5}]\n" info:` (must be flat; the penguin image was srgb(40,40,40) = #282828).
2. `magick src.png -resize 2880x -background '#282828' -gravity center -extent 2880x1920 out.png`
3. Preview: `magick out.png -resize 1200x /tmp/preview.png` (run as a separate command), then read it to verify.
Only works cleanly if the source background is a flat colour; otherwise ask the user about crop vs. blur-fill.
