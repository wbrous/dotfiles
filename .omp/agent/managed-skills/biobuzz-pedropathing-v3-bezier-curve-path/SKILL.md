---
name: biobuzz-pedropathing-v3-bezier-curve-path
description: Add a curved (bezier) path with control points to Biobuzz BozoAuto using Pedro Pathing v3 Paths API; convert plainLine to curve; extra auto states like park.
---

## Pedro Pathing v3 curves (Biobuzz)

Verified via `javap` on `~/.gradle/caches/modules-2/files-2.1/com.pedropathing/core/3.0.0/*/core-3.0.0.jar` (class `com.pedropathing.api.Paths`, already `import static com.pedropathing.api.Paths.*` in BozoAuto).

- `curve(Pose... )` = bezier: first = start, last = end, everything between = control points (pulled toward, never driven through). Also `curve(Vector2D...)`, `through(Pose...)` (passes through points), `line(Pose, Pose)`.
- Heading methods on `Path`: `.linear(startPose, endPose)`, `.constant(..)`, `.tangent()`, `.reverseTangent()`, `.facingPoint(..)`, `.heading(Interpolator)`, `.with(Modifier...)`.
- Control point heading is ignored; only x/y matter.

## Workflow used in BozoAuto
1. Add the pose to `AutoConfig` (constructor arg + field + javadoc), and a `public static Pose` in both `BlueAuto` and `RedAuto` (`@Configurable`, so tunable in Panels). Only Red/Blue construct `AutoConfig`; add the arg to BOTH `buildConfig()` calls in the same position as the constructor.
2. Build the path in `BozoAuto.buildPaths()`, e.g. `curve(shootPose, config.parkControlPose, config.parkPose).linear(shootPose, config.parkPose)`.
3. Add a `State` enum entry (e.g. `TRAVEL_TO_PARK`) before `DONE`; start with `follower.follow(path)` in the previous state, advance when `!follower.isBusy()`. Update the class javadoc sequence.
4. Red is Blue rotated 180 degrees about field centre (72,72): x -> 144 - x AND y -> 144 - y, heading +180. (e.g. Blue checkpoint 132,132 <-> Red 12,12; Blue shoot 84,134 <-> Red 60,10.) Derive Red control points this way; check Red's values aren't copied unmirrored (RedAuto.parkPose was once copied from Blue).
5. Converting an existing `plainLine(a, b)` to a curve: replace with `curve(a, ctrl, b).linear(a, b)` (keeps heading behaviour) and add the control pose per step 1. plainLine = `line(from,to).linear(from,to)`.
6. Compile: `./gradlew --offline :TeamCode:compileDebugJavaWithJavac -q` (~5-20s).

Edit tip: anchored line ranges must match what was displayed; re-read if the edit tool rejects them.
