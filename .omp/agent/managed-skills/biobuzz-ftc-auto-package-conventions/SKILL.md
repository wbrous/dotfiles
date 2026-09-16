---
name: biobuzz-ftc-auto-package-conventions
description: "Use when adding or modifying autonomous OpModes in the St-Marks-Robotics-FTC/Biobuzz repo's TeamCode/src/main/java/org/firstinspires/ftc/teamcode/auto/ package (BozoAuto, BlueAuto/RedAuto, BlueCloseAuto/RedCloseAuto, AutoConfig) — covers the alliance-pair symmetry convention, how to check whether a commit's changes are already applied before assuming work remains, diagnosing PedroPathing \"line length != 0\" crashes caused by zero-length line() paths, and exactly where each pose lives (BlueAuto/RedAuto static Pose fields vs. getStartPose() overrides in the Close leaf classes) and how to seed dummy-but-distinct placeholder coordinates so paths build without measured field data yet."
---

## Pose/path architecture in auto/

- `BozoAuto` (abstract base, extends OpMode) holds `protected abstract AutoConfig buildConfig()` and `protected abstract Pose getStartPose()`.
- `BozoAuto.buildPaths()` builds `path1..path6` via `line(poseA, poseB).linear(poseA, poseB)` calls chaining: start → shootLeft → flowerLeft → shootRight → flowerRight → shootRight → end.
- `BozoAuto.init()` sets the field used for path building via `startPose = getStartPose();` — NOT `config.startPose`. `config.startPose` (from `buildConfig()`/`AutoConfig`) is a separate value that does not feed path construction directly.
- `BlueAuto`/`RedAuto` (abstract, extend `BozoAuto`) declare all six named `Pose` fields (`startPose`, `shootLeftPose`, `shootRightPose`, `flowerLeftPose`, `flowerRightPose`, `endPose`) as `public static`, annotated `@Configurable` (bylazar Panels — live-tunable via the Panels dashboard at runtime, but those edits are NOT persisted to disk; copy final values back into source).
- `BlueCloseAuto`/`RedCloseAuto` (concrete, extend `BlueAuto`/`RedAuto`) only override `getStartPose()` — this is the pose actually used to seed path1's start point and `follower.setPose()`.

## "line length != 0" crash

Cause: PedroPathing's `line()`/`linear()` requires two distinct endpoints; a zero-length line (both poses equal, e.g. both left at default `(0,0,...)`) throws this assertion. This is a data problem, not an API/syntax problem — the `new Pose(x, y, Math.toRadians(heading))` call itself is fine.

Fix: ensure every *consecutive* pair actually used in `buildPaths()` differs in x or y:
start→shootLeft, shootLeft→flowerLeft, flowerLeft→shootRight, shootRight→flowerRight, flowerRight→shootRight, shootRight→end.

To unblock builds/sim before real field measurements exist, seed dummy-but-distinct placeholder coordinates in:
- `BlueAuto.java` / `RedAuto.java`: the 5 non-start static Pose fields (shootLeft/shootRight/flowerLeft/flowerRight/end)
- `BlueCloseAuto.java` / `RedCloseAuto.java`: the `getStartPose()` override return value

Mirror Red's placeholders roughly opposite Blue's on the field (e.g. Blue near `(0,0)` corner, Red near `(144,144)` corner) per the alliance-symmetry convention below, even for dummy data — keeps the two alliances visually/structurally consistent until real coordinates are measured.

## Alliance-pair symmetry convention

Blue and Red auto classes are meant to be mirror images of each other across the field (rotationally or axis-mirrored depending on field layout) — same shape of path, opposite alliance corner. When editing one alliance's poses, check whether the other alliance's equivalent poses need a matching mirrored update, rather than treating Blue/Red as independent.

## Before assuming work remains on a commit

Check the current state of the relevant file(s) first — a described bug or missing feature may already be fixed by a prior commit. Don't assume a git log entry describing intended work means the working tree still lacks it.
