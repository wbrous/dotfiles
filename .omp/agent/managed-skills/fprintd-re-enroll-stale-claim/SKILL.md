---
name: fprintd-re-enroll-stale-claim
description: "Use when re-enrolling a fingerprint with fprintd (fprintd-enroll/fprintd-delete) because verify-match confidence dropped, or when fprintd-delete fails with \"failed to claim device: GDBus.Error:net.reactivated.Fprint.Error.AlreadyInUse: Device was already claimed\"."
---

## Problem
Old/worn fingerprint enrollment still verify-matches but with degraded confidence. Want to re-enroll same finger name. `fprintd-delete $USER` often fails:

```
failed to claim device: GDBus.Error:net.reactivated.Fprint.Error.AlreadyInUse: Device was already claimed
```

This is a stale claim on the fprintd device (no separate process actually holding it in a way you can easily kill) — don't chase it.

## Fix
Skip delete entirely. `fprintd-enroll -f <finger-name>` (e.g. `right-index-finger`) overwrites the existing enrollment for that finger name directly — no need to delete first.

```
fprintd-enroll -f right-index-finger
```

Run interactively (needs a real pty — use `hub start` with `pty: true`, not plain bash, since it prompts for finger swipes across multiple stages). Watch for `Enroll result: enroll-completed`. Intermediate `enroll-stage-passed`, occasional `enroll-finger-not-centered` / `enroll-retry-scan` are normal — user just needs to swipe again.

Verify afterward with `fprintd-verify` (plain bash is fine, it's non-interactive enough — one swipe) and confirm `Verify result: verify-match (done)`.

No sudo needed for either fprintd-delete or fprintd-enroll when enrolling for the invoking user's own account.
