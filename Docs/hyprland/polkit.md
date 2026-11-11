# Polkit on Omarchy

Why the auth popup looks ugly/unthemed, and the one-line fix. Omarchy ships its own themed polkit agent; a competing service stealing the slot is the cause.

## Ugly polkit popup = competing agent

**Symptom:** the polkit/fingerprint auth popup looks like a plain ugly Qt widget instead of the themed dialog (greyed scrim, rounded corners, fingerprint glyph, password fallback).

**Cause:** Omarchy ships its OWN polkit agent as a first-party Quickshell plugin: `omarchy.polkit` (`/usr/share/omarchy/shell/plugins/polkit/PolkitAgent.qml` + `manifest.json`). It is theme-aware and always-on unless listed in `shell.json` `disabledPlugins[]`. The ugly Qt popup appears when a SECOND agent — `hyprpolkitagent` (Arch `extra/hyprpolkitagent`, old Qt/QML frontend), enabled as a `systemctl --user` service — wins the DBus registration race. Omarchy's plugin logs the conflict:

```
omarchy-shell: WARN: omarchy polkit agent is not registered; another agent may be running
```

The `hyprpolkitagent` journal error `ERROR: QQuickStyle::setStyle() must be called before loading QML that imports Qt Quick Controls 2.` merely confirms the old Qt frontend is the one wrongly running — a symptom, not the thing to fix. The old "upstream rewrote Qt→hyprtoolkit after v0.1.3 so the package is stale" framing is TRUE but irrelevant on Omarchy: Omarchy doesn't want hyprpolkitagent at all. This is NOT a theming config you are missing and NOT an upstream packaging gap.

**Fix:**

```sh
systemctl --user disable --now hyprpolkitagent.service
omarchy restart shell
```

Verify (must show `omarchy polkit agent registered`):

```sh
journalctl --user -n 60 --no-pager | grep -iE 'polkit|registered'
```

Diagnostic shortcuts: `systemctl --user is-enabled hyprpolkitagent.service` → `enabled` means it is competing. `grep -o 'disabledPlugins[^]]*]' ~/.config/omarchy/shell.json` → confirm `omarchy.polkit` is NOT listed. `pgrep -a quickshell` → shell running (its PID owns the native agent). `pacman -Qi hyprpolkitagent | grep Depends` → `qt6-declarative`/`hyprland-qt-support` = old Qt frontend.

Notes: Omarchy's native agent handles fingerprint + password fallback itself by reading `/etc/pam.d/polkit-1` and running `omarchy-hw-laptop-closed` to skip fingerprint when the lid is shut — no config needed. Separate from the GPG signing fingerprint gate (`~/.local/bin/pinentry-fprintd` + pkexec), which is unaffected. `omarchy restart shell` refuses while the session is locked (protects the lock screen). Do NOT: reinstall Kvantum (Omarchy dropped it deliberately), hand-build hyprtoolkit + hyprpolkitagent from `main` into `/usr` (pacman-integrity damage, reverted on next `-Syu`, wrong agent), or install `quillpolkit-git` (a third competing agent).

_Migrated from: omarchy-polkit-agent-vs-hyprpolkitagent, hyprpolkitagent-ugly-popup-no-omarchy-theming, hyprpolkitagent-ugly-qt-popup_
