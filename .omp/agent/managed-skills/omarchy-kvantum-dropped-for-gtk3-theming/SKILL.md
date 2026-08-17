---
name: omarchy-kvantum-dropped-for-gtk3-theming
description: "Use when Qt/QML apps on Omarchy (e.g. hyprpolkitagent's fingerprint/polkit dialog, or any Qt6 app) look plain/unstyled (\"dumb Qt popup\"), or when deciding whether to reinstall Kvantum, add a pacman hook to keep it installed, or investigate why kvantum/kvantum-qt5 disappeared after a system update."
---

## Background
Omarchy migration `1785351479.sh` (`~/.local/share/omarchy/migrations/`, or `/usr/share/omarchy/migrations/`) deliberately runs `pacman -Rns kvantum-qt5 kvantum` (+ pulls qt5-svg, qt5-x11extras with it). This is intentional, not a regression:

- Omarchy never shipped a `.kvconfig` for Kvantum to read, and `QT_STYLE_OVERRIDE` (which used to force Kvantum) is gone from the env.
- Qt apps now theme via `QT_QPA_PLATFORMTHEME=gtk3`, which tracks the live Omarchy theme; Kvantum never did.
- Migration deliberately leaves `qt5-wayland`/`qt5-declarative` alone (needed by legacy SDDM Qt5 greeters).

## Diagnosis rule
If `kvantum`/`kvantum-qt5` are missing and a Qt/QML app looks plain: **do NOT reinstall them or add a pacman hook to keep them installed.** That fights the migration — next Omarchy update (or a manual re-run of the same migration idea) removes them again, and a hook can't override an explicit `pacman -Rns` call in a script. Reinstalling was tried and reverted in a real session; it wasn't the actual fix.

## Where the real theming comes from (hyprpolkitagent case)
`hyprpolkitagent`'s fingerprint/polkit dialog is NOT styled by Kvantum. It depends on `hyprland-qt-support`, which ships custom themed QML controls at `/usr/lib/qt6/qml/org/hyprland/style/` (Button.qml, CheckBox.qml, TextField.qml, HyprlandStyle.qml) that read Hyprland/Omarchy theme colors directly. Verify it's present and current:
```sh
pacman -Qi hyprland-qt-support   # Required By: hyprpolkitagent
```
If the dialog still looks wrong with this package installed and Kvantum correctly absent, the bug is elsewhere (stale QML cache, wrong QQC2 style env var, agent needs `systemctl --user restart hyprpolkitagent.service`) — not a missing theme engine.

## Quick checks when this comes up again
```sh
grep -A5 kvantum ~/.local/share/omarchy/migrations/*.sh   # confirm intentional-removal migration exists
pacman -Qi kvantum 2>&1                                    # should report "not found" — that's correct
pacman -Qi hyprland-qt-support                              # should be installed, Required By: hyprpolkitagent
systemctl --user restart hyprpolkitagent.service            # if dialog looks stale after any pkg change
```
