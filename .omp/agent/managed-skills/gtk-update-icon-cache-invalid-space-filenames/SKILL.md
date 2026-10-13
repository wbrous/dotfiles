---
name: gtk-update-icon-cache-invalid-space-filenames
description: "gtk-update-icon-cache says \"The generated cache was invalid\" for ~/.local/share/icons/hicolor (e.g. from tern register or app installers); Omarchy webapp icons with spaces in filenames."
---

# gtk-update-icon-cache: "The generated cache was invalid"

## Symptom
Installers/registrars (e.g. `tern register`, stencil_platform) warn:
`gtk-update-icon-cache: The generated cache was invalid.` The tool itself still works; only the user icon cache is stale.

## Known cause (observed)
Icon files with **spaces in their names** under `~/.local/share/icons/hicolor/<size>/apps/`
(e.g. `Disk Usage.png`, `Google Maps.png`). Omarchy webapp installers create these alongside matching `.desktop` files (`Disk Usage.desktop`). Missing `index.theme` in the user hicolor dir was NOT the cause (adding it did not help).

## Diagnose without touching the real dir
Copy to a scratch dir and bisect:
```sh
T=$(mktemp -d); cp -r ~/.local/share/icons/hicolor $T/h; cd $T/h; rm -f .icon-theme.cache
gtk-update-icon-cache -f .                 # fails
find . -name '* *' -delete; gtk-update-icon-cache -f .   # succeeds => spaces are the cause
```
List offenders: `find ~/.local/share/icons/hicolor -name '* *'`.
(`strace` may not be installed; bisecting is faster anyway.)

## Fix
Rename to dash names AND update `Icon=` in the matching `.desktop` files, then rebuild:
```sh
cd ~/.local/share/icons/hicolor/48x48/apps
for f in *\ *.png; do mv "$f" "${f// /-}"; done
gtk-update-icon-cache -f ~/.local/share/icons/hicolor
```
Caveat: the Omarchy webapp installer may recreate spaced names on next run. Ask the user before renaming their files.
