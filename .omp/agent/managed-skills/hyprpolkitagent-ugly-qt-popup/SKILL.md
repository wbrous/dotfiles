---
name: hyprpolkitagent-ugly-qt-popup
description: "Use when the Omarchy polkit/fingerprint auth popup looks like a plain/ugly Qt widget instead of the themed dialog. On Omarchy the root cause is a competing hyprpolkitagent.service winning the polkit registration race over Omarchy's own omarchy.polkit Quickshell plugin — see omarchy-polkit-agent-vs-hyprpolkitagent. Also covers why NOT to reinstall Kvantum or hand-build hyprpolkitagent from source."
---

# Ugly Qt polkit popup on Omarchy → competing agent (not an upstream gap)

**On Omarchy, do NOT chase the upstream-rewrite / Kvantum / hand-build path.** The
ugly popup is almost always `hyprpolkitagent.service` (a separate Qt/QML agent)
winning the polkit DBus registration race over Omarchy's own themed `omarchy.polkit`
Quickshell plugin.

See **`omarchy-polkit-agent-vs-hyprpolkitagent`** for the fix:

```sh
systemctl --user disable --now hyprpolkitagent.service
omarchy restart shell
```

Verify: `journalctl --user -n 60 --no-pager | grep -iE 'polkit|registered'` must
show `omarchy polkit agent registered`.

## Why the old "upstream rewrite" framing is a red herring here

The historical detail (upstream `hyprwm/hyprpolkitagent` rewrote Qt→hyprtoolkit after
tag v0.1.3, so packaged builds are "stale") is TRUE but irrelevant on Omarchy: Omarchy
doesn't want hyprpolkitagent at all — it ships its own agent. Diagnosing the ugly
popup as "the package is just stale, wait for a release or build from main" is wrong
on Omarchy and wastes time hand-building / installing quillpolkit / reinstalling
Kvantum, none of which fix the actual competing-agent problem.

`ERROR: QQuickStyle::setStyle() must be called before loading QML that imports Qt
Quick Controls 2.` in the hyprpolkitagent journal merely confirms the old Qt frontend
is the one that's (wrongly) running — it's a symptom, not the thing to fix.

## Don't do (Omarchy)

- Reinstall Kvantum (Omarchy dropped it).
- Hand-build hyprtoolkit + hyprpolkitagent from `main` into `/usr` (destroys pacman
  integrity, gets reverted on next `-Syu`, and is the wrong agent anyway).
- Install `quillpolkit-git` (a third agent — still not Omarchy's themed one).
