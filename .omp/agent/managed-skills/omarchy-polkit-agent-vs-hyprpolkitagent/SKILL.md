---
name: omarchy-polkit-agent-vs-hyprpolkitagent
description: "Use when the Omarchy polkit/fingerprint auth popup looks like an ugly/unthemed Qt widget instead of the themed dialog (greyed scrim, rounded corners, fingerprint glyph, password fallback). Root cause is usually a competing standalone agent (hyprpolkitagent.service) winning the polkit registration race over Omarchy's own omarchy.polkit Quickshell plugin."
---

# Omarchy polkit popup is ugly → competing agent is stealing the slot

## The real cause (not upstream, not Kvantum, not theming)

Omarchy ships its **own** polkit authentication agent as a first-party Quickshell plugin: `omarchy.polkit`
(`/usr/share/omarchy/shell/plugins/polkit/PolkitAgent.qml` + `manifest.json`). It is theme-aware and always-on
unless listed in `shell.json` `disabledPlugins[]`. It produces the popup users remember: greyed scrim, rounded
card (from Hyprland corner radius), a fingerprint glyph when `pam_fprintd` is in `/etc/pam.d/polkit-1`, and
password fallback on scan failure.

The ugly Qt popup appears when a **second** polkit agent is running and wins the DBus registration race.
On these systems that is `hyprpolkitagent` (Arch `extra/hyprpolkitagent`, old Qt/QML frontend), enabled as a
`systemctl --user` service. Omarchy's plugin logs the conflict:

```
omarchy-shell: WARN: omarchy polkit agent is not registered; another agent may be running
```

The `hyprpolkitagent` journal also shows the legacy frontend's known init-order bug:
`ERROR: QQuickStyle::setStyle() must be called before loading QML that imports Qt Quick Controls 2.`
That error is real but irrelevant — the point is it's the wrong agent entirely, not a theming gap.

## Fix

```sh
systemctl --user disable --now hyprpolkitagent.service
omarchy restart shell
```

Verify (must show `omarchy polkit agent registered`, and no `Stopping Hyprland Polkit Authentication Agent`):

```sh
journalctl --user -n 60 --no-pager | grep -iE 'polkit|registered'
```

## Diagnostic shortcuts

- `systemctl --user is-enabled hyprpolkitagent.service` → `enabled` means it's competing.
- `grep -o 'disabledPlugins[^]]*]' ~/.config/omarchy/shell.json` → confirm `omarchy.polkit` is NOT in the list.
- `pgrep -a quickshell` → Omarchy shell running (its PID owns the native agent).
- `pacman -Qi hyprpolkitagent | grep Depends` → lists `qt6-declarative`/`hyprland-qt-support` = the old Qt frontend.

## Notes / scope boundaries

- Omarchy's native agent handles fingerprint + password fallback itself by reading `/etc/pam.d/polkit-1`
  and running `omarchy-hw-laptop-closed` to skip fingerprint when the lid is shut. No config needed.
- This is separate from the GPG signing fingerprint gate (`~/.local/bin/pinentry-fprintd` + pkexec) — that
  flow is unaffected by disabling hyprpolkitagent.
- `omarchy restart shell` refuses to restart while the session is locked (protects the lock screen).
- Do NOT chase: reinstalling Kvantum (Omarchy dropped it), hand-building hyprpolkitagent from main, or
  Omarchy theme files — none address the competing-agent root cause.
