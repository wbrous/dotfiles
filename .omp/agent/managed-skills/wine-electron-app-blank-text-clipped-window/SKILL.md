---
name: wine-electron-app-blank-text-clipped-window
description: "Use when a standalone Windows Electron app (unpacked .exe) run under Wine/GE-Proton renders no text anywhere in the UI (with icon-font glyphs showing as small black boxes/tofu), or when its window is partly off-screen / bottom toolbar buttons are clipped and unclickable. Covers GeoGebra.exe specifically but applies to any Electron app in this class."
---

## Symptom 1: no text renders anywhere, small black box(es) for icon glyphs

Root cause: the Wine prefix's `drive_c/windows/Fonts` folder is completely empty (0 files) — a fresh `wineboot --init` prefix ships with no fonts registered, even though the host system has plenty via fontconfig. Chromium/Skia (which Electron embeds) can't find ANY font to rasterize glyphs with, so all text is invisible; icon-font glyphs (e.g. hamburger menu, toolbar icons rendered via a webfont) show as tofu/black-box placeholders instead of actual glyphs.

Fix:
```bash
export WINEPREFIX="$APPDIR/.pfx"
winetricks -q corefonts
```
This is a one-time fix persisted inside `.pfx` — no launch-script changes needed. Verify via `find "$WINEPREFIX/drive_c/windows/Fonts" -maxdepth 1 | wc -l` (should go from 1 — just the dir itself — to 30+).

## Symptom 2: window off-screen / bottom toolbar clipped and unclickable

Root cause: many Electron apps persist window bounds (`x`,`y`,`width`,`height`) via `electron-store` into a `config.json` under `AppData/Roaming/<AppName>/config.json`, and blindly `Object.assign()` those saved bounds onto the `BrowserWindow` constructor options on next launch with zero validation. If a prior session saved bogus bounds (e.g. from a screen-size mismatch, a Wine DPI quirk, or a previous crashed/glitched state) — negative `y`, or `width`/`height` exceeding the actual monitor's work area — the window opens partly or mostly off-screen, clipping the bottom row of buttons out of the clickable area.

Diagnosis: read the app's `resources/app/main.js` (or equivalent unpacked entry point — these apps are often NOT asar-packed and are directly editable) and look for a `createWindow()` function doing something like:
```js
const config = new Config(); // electron-store
Object.assign(pref, config.get('winBounds'));
```
Then check the actual persisted file, e.g.:
```
find "$WINEPREFIX/drive_c/users/$USER/AppData/Roaming/<AppName>" -iname config.json
```
and inspect it — bounds like `{"y": -30, "width": 2888, "height": 1954}` against a monitor workArea of `2880x1920` confirm this exact bug.

Fix (two parts — both needed, one is immediate, one prevents recurrence):
1. Immediate: `rm` the stale `config.json` (or just the `winBounds` key) so the app falls back to its hardcoded default size.
2. Durable: patch `createWindow()` in `main.js` to clamp saved bounds to `screen.getPrimaryDisplay().workArea` before applying them, e.g.:
```js
const savedBounds = config.get('winBounds');
if (savedBounds) {
    const { screen } = require('electron');
    const area = screen.getPrimaryDisplay().workArea;
    savedBounds.width = Math.min(savedBounds.width || area.width, area.width);
    savedBounds.height = Math.min(savedBounds.height || area.height, area.height);
    savedBounds.x = Math.max(area.x, Math.min(savedBounds.x || area.x, area.x + area.width - savedBounds.width));
    savedBounds.y = Math.max(area.y, Math.min(savedBounds.y || area.y, area.y + area.height - savedBounds.height));
    Object.assign(pref, savedBounds);
}
```

## Verification technique (headless-safe, no interactive access needed)
Get the window's live geometry from the compositor, then screenshot exactly that region and read it as an image:
```bash
hyprctl clients -j | python3 -c "
import json,sys
d=json.load(sys.stdin)
for w in d:
    if w.get('class')=='<app>.exe':
        x,y=w['at']; ww,wh=w['size']
        print(f'{x},{y} {ww}x{wh}')
"
grim -g "$geom" /tmp/shot.png
```
Then use the `read` tool on the PNG — it decodes inline. This is the fastest ground-truth check for "is text rendering" / "is the bottom clipped" without guessing from logs.

## Gotcha
`grep -c` on `ps aux`/`ps -eo cmd` output for a process name is unreliable for lifecycle tracking across Electron's multi-process tree (main/gpu-process/utility/renderer all match the same binary name, and PIDs get reused fast enough that `kill -0 <stale-pid>` can return a false "alive"). Prefer `ps -eo pid,cmd | grep '[p]attern'` snapshots compared over time, or check the compositor's window list (`hyprctl clients`) directly for the actual UI-visible truth.
