---
name: biobuzz-pedropathing-v3-limit-path-speed
description: When capping or slowing speed during a Pedro Pathing v3 path in Biobuzz autos; read the user-preference warning and the manual-drive recipe before adding any speed limiter.
---

# Limiting path speed in Pedro Pathing v3 (Biobuzz)

## User preference (read first)
In BozoAuto the user rejected every config-based speed limiter: a linear slowdown helper, then a one-shot cap, both editing `Constants.foresightConfig.maxPathSpeed`. They want it SIMPLE, "none of this constants editing stuff", KISS. Do not re-add global-config edits, helper functions, or per-loop limiters unprompted.

What the user later explicitly asked for instead: "using manual drive, scale the speed to .3" on the intermediate -> refuel leg. Implemented (compiled, not robot-tested; user acceptance not yet confirmed) as the recipe below. If asked to slow a path leg again, prefer this over editing config.

## Manual-drive recipe (core 3.0.1)
- In the state for that leg, call every loop (after `follower.update()`): compute dx, dy to target pose, distance = hypot; if within an arrival tolerance call `follower.manual(0,0,0)` and advance state.
- Otherwise `ManualDrive.fieldCentric(dx/d*scale, dy/d*scale, turn*scale, pose.heading())` then `follower.manual(powers)`. turn = wrapped (atan2(sin,cos)) heading error * gain, clamped to [-1,1].
- Do NOT call `follower.follow(...)` for that leg; transition into it when the previous path's `!follower.isBusy()`.
- `follower.follow(path)` calls `clearState()` and sets mode FOLLOW, so following a path after manual drive is clean.
- Tunables added in Tunables.java: `refuelDriveScale=0.3`, `refuelArrivalDistance=2` (in), `refuelHeadingGain=1.0`. Open-loop: no path correction, drift possible; values are guesses.

## Verified API facts (core 3.0.x, from javap)
- `Follower` has no `setMaxPower`. It has `follow`, `hold`, `manual(DrivePowers)`, `manual(double fwd, double strafe, double turn)`, `manual()` (is-manual), `isBusy`, `remainingDistance()`, `pose()`.
- `ManualDrive.fieldCentric(fwd, strafe, turn, heading)` rotates the (forward,strafe) vector by -heading; used the same way in BozoTeleOp.
- Speed limits via config live in `ForesightConfig` (shared static `Constants.foresightConfig`): `maxPathSpeed`, `maxVelocityConstraint` are `ConfigVar<Double>`, default Infinity, 0 rejected. Static, so changes persist across OpModes.
- Jars: ~/.gradle/caches/modules-2/files-2.1/com.pedropathing/core/3.0.x/**/core-3.0.x.jar (use `javap -c -cp`).

## Other lessons
- `HEAD` may already contain earlier edits (formatter commit); diff against HEAD before assuming a clean baseline.
- With multi-op edits, line numbers shift; re-read after each batch. Edit anchors require the lines to have been displayed.
- Compile check: `./gradlew :TeamCode:compileDebugJavaWithJavac --offline -q` (fast).
- Don't run filesystem-wide `find` in bash; it backgrounds for 300s.
