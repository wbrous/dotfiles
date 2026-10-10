---
name: biobuzz-pedropathing-v3-bezier-curve-path
description: Add a curved (bezier) path with control points to Biobuzz BozoAuto using Pedro Pathing v3 Paths API; extra auto states like park.
---

## Pedro Pathing v3 curves (Biobuzz)

Verified via `javap` on `~/.gradle/caches/modules-2/files-2.1/com.pedropathing/core/3.0.0/*/core-3.0.0.jar` (class `com.pedropathing.api.Paths`, already `import static com.pedropathing.api.Paths.*` in BozoAuto).

- `curve(Pose... )` = bezier: first = start, last = end, everything between = control points (pulled toward, never driven through). Also `curve(Vector2D...)`, `through(Pose...)` (passes through points), `line(Pose, Pose)`.
- Heading methods on `Path`: `.linear(startPose, endPose)`, `.constant(..)`, `.tangent()`, `.reverseTangent()`, `.facingPoint(..)`, `.heading(Interpolator)`, `.with(Modifier...)`.
- Control point heading is ignored; only x/y matter.

## Workflow used in BozoAuto
1. Add the pose to `AutoConfig` (constructor arg + field), and a `public static Pose` in both `BlueAuto` and `RedAuto` (`@Configurable`, so tunable in Panels). Only Red/Blue construct `AutoConfig`.
2. Build the path in `BozoAuto.buildPaths()`, e.g. `curve(shootPose, config.parkControlPose, config.parkPose).linear(shootPose, config.parkPose)`.
3. Add a `State` enum entry (e.g. `TRAVEL_TO_PARK`) before `DONE`; start with `follower.follow(path)` in the previous state, advance when `!follower.isBusy()`. Update the class javadoc sequence.
4. Red is the mirror of Blue: x -> 144 - x, heading 180 <-> 0. Check Red's pose values are actually mirrored (RedAuto.parkPose was once copied from Blue).
5. Compile: `./gradlew --offline :TeamCode:compileDebugJavaWithJavac -q` (~5s).

Edit tip: anchored line ranges must match what was displayed; re-read if the edit tool rejects them.
