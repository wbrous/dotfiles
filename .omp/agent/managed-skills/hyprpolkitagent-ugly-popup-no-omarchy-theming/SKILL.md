---
name: hyprpolkitagent-ugly-popup-no-omarchy-theming
description: "Use when the Omarchy polkit/fingerprint auth popup looks ugly/unthemed or \"used to look nice\". On Omarchy the root cause is a competing hyprpolkitagent.service beating Omarchy's own omarchy.polkit Quickshell plugin in the polkit registration race — see omarchy-polkit-agent-vs-hyprpolkitagent. Also covers why NOT to hand-build from source or install quillpolkit/Kvantum."
---

# Ugly polkit popup on Omarchy → competing agent (see omarchy-polkit-agent-vs-hyprpolkitagent)

**On Omarchy this is NOT an upstream packaging gap and NOT a theming config you're
missing.** Omarchy ships its own themed polkit agent (`omarchy.polkit`, a Quickshell
plugin) that produces the greyed-scrim / rounded-corner / fingerprint-glyph /
password-fallback dialog. If the popup is ugly, a separate `hyprpolkitagent.service`
is winning the DBus registration race.

Fix (see `omarchy-polkit-agent-vs-hyprpolkitagent` for full detail):

```sh
systemctl --user disable --now hyprpolkitagent.service
omarchy restart shell
```

## Why the old content was wrong for Omarchy

The prior version of this skill framed the problem as "upstream hyprpolkitagent
rewrote Qt→hyprtoolkit after v0.1.3, so no package ships the nice UI yet — wait, or
hand-build from main." That is true of hyprpolkitagent upstream, but it's the wrong
diagnosis on Omarchy, where the correct answer is "you shouldn't be running
hyprpolkitagent at all; Omarchy has its own agent."

- Omarchy's theme system DOES cover polkit — through its own `omarchy.polkit`
  plugin, not through hyprpolkitagent theming. The earlier claim that "Omarchy has
  no polkit theming hook" was wrong: the hook exists as a first-party shell plugin.
- The fingerprint + password fallback behavior is implemented natively in
  `PolkitAgent.qml` (reads `/etc/pam.d/polkit-1` for `pam_fprintd`, runs
  `omarchy-hw-laptop-closed` to skip the sensor when the lid is shut). No config.

## Do NOT do (Omarchy)

- Hand-build hyprtoolkit + hyprpolkitagent from `main` into `/usr` (pacman-integrity
  damage, wrong agent, reverted on next `-Syu`).
- Install `quillpolkit-git` (a third competing agent).
- Reinstall Kvantum (Omarchy dropped it deliberately).
