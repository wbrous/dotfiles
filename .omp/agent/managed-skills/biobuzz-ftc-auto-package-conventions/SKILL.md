---
name: biobuzz-ftc-auto-package-conventions
description: "Use when adding or modifying autonomous OpModes in the St-Marks-Robotics-FTC/Biobuzz repo's TeamCode/src/main/java/org/firstinspires/ftc/teamcode/auto/ package (BozoAuto, BlueAuto/RedAuto, BlueCloseAuto/RedCloseAuto, AutoConfig) — covers the alliance-pair symmetry convention, how to check whether a commit's changes are already applied before assuming work remains, and diagnosing PedroPathing \"line length != 0\" crashes caused by zero-length line() paths."
---

## Alliance-pair symmetry convention

BlueAuto/RedAuto (and BlueCloseAuto/RedCloseAuto) are meant to mirror each other's waypoints across the field's symmetry axis. When adding/adjusting a waypoint in one alliance's auto file, apply the mirrored value to its pair, not a copy of the same numbers.

Before assuming work remains on a commit/PR, diff the actual current file contents against what the commit claims to add — changes may already be applied.

## PedroPathing "line length != 0" crash

`BozoAuto.buildPaths()` builds paths via `static com.pedropathing.api.Paths.line(poseA, poseB).linear(poseA, poseB)`. PedroPathing's `line()`/`linear()` asserts the two endpoint `Pose`s are not identical — a zero-length line has undefined direction.

Root cause is almost always: waypoint `Pose` fields (`startPose`, `shootLeftPose`, `shootRightPose`, `flowerLeftPose`, `flowerRightPose`, `endPose`) in `BlueAuto.java`/`RedAuto.java` all left at their scaffold default `new Pose(0, 0, ...)`, or (as seen in `RedAuto.java`) all derived from the same `startX/startY/startAngle` fields instead of separate per-waypoint fields.

Fix: give each waypoint distinct, real field coordinates in inches:

```java
public static Pose startPose      = new Pose(x1, y1, Math.toRadians(h1));
public static Pose shootLeftPose  = new Pose(x2, y2, Math.toRadians(h2));
// ... etc, one Pose(x, y, heading) per waypoint, NOT all sharing one x/y source
```

Every adjacent pair actually used in `buildPaths()` (start→shootLeft, shootLeft→flowerLeft, flowerLeft→shootRight, shootRight→flowerRight, flowerRight→shootRight, shootRight→end) must differ in x or y.

`Pose` constructor syntax: `new Pose(x, y, headingRadians)` — heading via `Math.toRadians(degrees)`, x/y in inches on the field coordinate system.
