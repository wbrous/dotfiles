---
name: biobuzz-pedropathing-v3-spin-in-place
description: "Spin or turn the robot in place in Pedro Pathing v3 auto (no follower.turnTo); full rotations, heading wrap, BozoAuto state machine"
---

# Spinning / turning in place in Pedro Pathing v3 (Biobuzz)

`follower.turnTo()` no longer exists. BozoTeleOp does it as:
`follower.hold(new Pose(x, y, targetHeading))` and exits when
`|pose.heading() - target| < Tunables.shootHeadingMargin`.

## Multi-rotation spin (e.g. TEMP_FAILED state in BozoAuto)
- A single `hold` target cannot express >180 deg; use steps of 120 deg (3 rotations = 9 steps).
- Anchor each target to the heading at spin start (`startPose.heading() + (n+1)*step`), NOT the measured heading, so error does not accumulate.
- Wrap target with `atan2(sin, cos)` and compare with a wrap-aware `headingError` (mod 2PI into [-PI, PI]) — the teleop's plain subtraction breaks across the +-180 boundary.
- Keep x/y from the pose captured at spin start so the robot stays in place.
- Entering state: `shutOff()`, reset step counter, capture start pose, hold first target, `setState(...)`. Each loop in the state: if within margin, count++, then next hold or `setState(DONE)`.

## Editing note
BozoAuto edits: `edit` needs the exact line ranges to have been displayed by `read` first; read the ranges, then apply bottom-up in one batch.
Verify with `./gradlew :TeamCode:compileDebugJavaWithJavac --offline -q`.
