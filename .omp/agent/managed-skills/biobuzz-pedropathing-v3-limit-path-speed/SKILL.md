---
name: biobuzz-pedropathing-v3-limit-path-speed
description: "When capping or slowing speed during a Pedro Pathing v3 path in Biobuzz autos (incl. \"manual drive at 0.3\"); read the user-preference warning before adding any speed limiter."
---

# Limiting path speed in Pedro Pathing v3 (Biobuzz)

## User preference (read first)
In BozoAuto the user has rejected EVERY speed-limiting attempt:
1. a linear slowdown helper and a one-shot cap, both editing `Constants.foresightConfig.maxPathSpeed` ("none of this constants editing stuff", KISS);
2. later, when asked for "manual drive, scale speed to .3 on the intermediate-to-refuel path", an implementation replacing the path with `follower.manual(...)` + a `manualDriveToRefuel()` helper + 3 new Tunables (`refuelDriveScale`, `refuelArrivalDistance`, `refuelHeadingGain`). User replied "nono. undo that go back" and it was fully reverted.

Final state each time: NO slowdown, original `follower.follow(intermediateToRefuelPath)`. Do not add helpers, new Tunables, or per-loop limiters unprompted. Even when the user's request names a mechanism ("manual drive"), ask what they envision (e.g. a one-line scale on existing manual powers vs. replacing the path) before writing a multi-function implementation; keep any change to a few lines.

## Verified API facts (core 3.0.0/3.0.1, from javap)
- `Follower` has no `setMaxPower`. It has `follow`, `hold`, `manual(DrivePowers)`, `manual(double fwd, double strafe, double turn)`, `isBusy`, `manual()` (bool), `remainingDistance()`, `pose()`.
- `follow(Path)` resets mode to FOLLOW (clears manual state), so switching manual -> path is clean.
- `ManualDrive.fieldCentric(fwd, strafe, turn, heading)` rotates by -(heading) via Vector2D; BozoTeleOp uses it with `follower.manual(powers)`.
- Speed limits live in `ForesightConfig` (shared static `Constants.foresightConfig`): `maxPathSpeed`, `maxVelocityConstraint` are `ConfigVar<Double>`, default `Constraint.NONE` (Infinity), validated positive (0 rejected). Shared static: persists across OpModes unless reset.
- `maxPathSpeed` read in `Foresight.coast`, appears to be a fraction. Never run on a robot; unconfirmed.

## Other lessons
- The working tree may hold the user's uncommitted edits (e.g. `Tunables.shootRPM = 4300`, `RedAuto.refuelPose`) and even half-written lines in BozoAuto (a stray `shootToIntermediatePath.modifiers.set()` appeared). Diff against HEAD before assuming a clean baseline; when reverting, restore only your own changes.
- With multi-op edits, line numbers shift; re-read the file after each batch.
- Don't run filesystem-wide `find` in bash; it backgrounds for 300s. Gradle jars: `~/.gradle/caches/modules-2/files-2.1/com.pedropathing/core/<ver>/`.
- Compile check: `./gradlew :TeamCode:compileDebugJavaWithJavac --offline -q`.
