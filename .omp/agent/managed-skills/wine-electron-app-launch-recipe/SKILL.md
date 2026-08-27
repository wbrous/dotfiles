---
name: wine-electron-app-launch-recipe
description: "Use when packaging a standalone Windows Electron app (unpacked .exe, no installer) to run under Wine on Linux and it either shows no window/silently self-terminates ~15-17s after launch, or shows a window with no text rendering and/or small black boxes for icons. Covers GE-Proton vs plain system wine selection, the WinRT UISettings stub-loop crash, and the empty-Fonts-folder tofu/blank-text symptom."
---

## Symptom cluster & fixes for standalone Electron .exe under Wine

### 1. Window never appears / process self-terminates ~15-17s after launch, no coredump, no signal
Root cause: the wine build's Chromium/Electron mojo IPC handshake between main process and child processes (gpu-process, renderer, network utility) never completes. Browser process hits `ChildThreadImpl::EnsureConnected()` timeout (Chromium's fixed 15s connection timeout) and quits silently.

Diagnosis:
- Track exact process count over time: `ps -eo cmd | grep -c "[A]ppName.exe"` polled every 1s for 20-25s. If it stays flat then drops to 0 around t=15-17s with no coredump (`coredumpctl list`) and no fatal wine error at the log tail, this is it.
- Confirm via `ELECTRON_ENABLE_LOGGING=1 wine app.exe --enable-logging=stderr --v=1`: look for `[PID:.../child_thread_impl.cc:909] ChildThreadImpl::EnsureConnected()` appearing ~15s after a prior log line — that's the smoking gun.

**Fix that actually works:** try plain system `wine` (whatever `pacman -Q wine` gives, e.g. wine-11.15) instead of GE-Proton's staging wine build. GE-Proton11-5's wine-11.0-staging was observed to reliably break this specific IPC handshake for a plain (non-gaming) Electron app, while system wine handled it fine with a full 4-process tree (main/gpu-process/network-utility/renderer) staying alive and a real window (`class: appname.exe`) mapped.
- `--no-sandbox` (via `app.commandLine.appendSwitch("no-sandbox")` if you can patch `resources/app/main.js`, since these apps often intercept unrecognized CLI args as file-open attempts rather than passing them to Chromium) had **zero effect** on this specific failure — don't waste time on it for this symptom.
- `--single-process --in-process-gpu` made it *worse* (crashed even faster, ~2s) — do not use as a workaround for this IPC issue.
- GE-Proton is still the right call for apps needing real DirectX/Direct3D/anticheat compat (see wine-webview2-* skills); for a plain Electron/Chromium app with no D3D dependency, prefer plain wine first and only reach for GE-Proton if plain wine fails differently.

### 2. Window shows but no text renders anywhere, plus small black box(es) for icons (e.g. header hamburger menu)
Root cause: a fresh Wine prefix's `drive_c/windows/Fonts` folder is completely empty (`find "$WINEPREFIX/drive_c/windows/Fonts" -maxdepth 1 | wc -l` → 1, i.e. just the dir itself). Chromium/Skia has zero fonts to render glyphs with — all text is invisible, and icon-font glyphs (many web-UI toolbars use icon fonts, not SVG) render as tofu/black boxes instead of icons.

Fix: `WINEPREFIX="$PFX" winetricks -q corefonts` (installs ~32 font files: Arial, Verdana, Times New Roman, Webdings, etc., can take 60-120s, several `wineserver -w` waits internally — background it with `hub` and poll rather than blocking foreground). This is a one-time asset persisted inside the prefix directory itself — no launch-script changes needed once installed.

### 3. WinRT UISettings stub recursion crash (separate, cosmetically similar to #1 but distinct root cause)
Wine's `windows.ui.dll` implements `IUISettings2::get_TextScaleFactor` as a stub that some Electron/Chromium builds call in a loop, recursing until stack overflow (`err:virtual:virtual_setup_exception stack overflow ... addr 0x70XXXXXX`) and killing whichever thread hit it. Fix: `export WINEDLLOVERRIDES="windows.ui=d"` before launching — forces `RoGetActivationFactory` to fail cleanly for that WinRT class instead of returning a stub that spins. Cheap, harmless, worth including by default in any Electron-under-wine launch script alongside the corefonts fix.

## Diagnosis toolbox recap
- `hyprctl clients` — check `mapped`/`visible`/`class`/`title` for the real app window; watch out for coincidentally-same-titled unrelated windows (e.g. a Nautilus window browsing a folder named after the app) giving false positives.
- `grim -g "$(hyprctl clients -j | python3 -c '...')" out.png` then `read` the png — fastest way to visually verify a Wine GUI app's actual rendered state instead of guessing from logs.
- `coredumpctl list` — rules in/out a real SIGSEGV/SIGABRT vs. a clean self-exit.
- `find "$WINEPREFIX/drive_c/windows/Fonts" -maxdepth 1 | wc -l` — quick empty-fonts check before assuming a rendering bug is something exotic.
