---
name: biobuzz-pedropathing-v3-path-heading-interpolation
description: "Pedro Pathing v3 Biobuzz autos: set approach heading then rotate near end of a path, shortest-arc turns (330 vs -30), per-path .with() constants; no follower.manual."
---

# Heading control on Pedro Pathing v3 paths (Biobuzz BozoAuto)

## User preferences
- Wants behavior built as a **Path**, never `follower.manual(...)` (explicitly rejected).
- Per-path constant overrides via `.with(Constants.foresightConfig.<var>.at(x))` are fine (docs: https://pedropathing.com/docs/pathing/guide/modifiers). Global `Constants` edits are not.
- Docs to consult: https://pedropathing.com/docs/pathing/reference/interpolation, /reference/api, /reference/foresightoptions.

## Verified facts (core 3.0.1, javap + runtime smoke test)
- `Interpolator.linear(a, b)` normalizes both angles and uses `Angle.error` = `normalizeSigned(b-a)`: always the **short arc**. 330 deg and -30 deg are equivalent; 330->0 turns +30. (`longLinear` exists for the long way.)
- `Path.heading(Interpolator)` is public. Hold-then-turn on one line:
  `line(a,b).heading(Interpolator.piecewise().until(0.7, Interpolator.constant(poseA)).until(1.0, Interpolator.linear(poseA, poseB)))`
  `until(t, ...)` requires strictly increasing t, <= 1. Each segment's local t is remapped to 0..1. Also `path.linear(startH, endH, fraction)` does the same in one call.
- `Paths.line` throws IllegalArgumentException on zero length, so a pure rotate-in-place path is impossible; the turn must overlap translation.
- `isBusy()` includes a heading condition, so the path is not "done" until heading is within tolerance.
- Rotation slowness is controlled by slice length (smaller start fraction = gentler turn) plus `maxPathSpeed`; `headingDriveRatio` is also available per path.
- Mirror across x=72 for Red: heading h -> 180 - h (Blue 330/0 -> Red 210/180).

## Biobuzz specifics
- Approach heading = `intermediatePose.heading()`; final heading = `refuelPose.heading()`; no AutoConfig field needed. `BozoAuto.REFUEL_ROTATE_START` = 0.7.
- Compile: `./gradlew :TeamCode:compileDebugJavaWithJavac --offline -q`. Throwaway smoke: unzip core jar to /tmp, `javac -cp` a small main, call `path.heading(t)`.
