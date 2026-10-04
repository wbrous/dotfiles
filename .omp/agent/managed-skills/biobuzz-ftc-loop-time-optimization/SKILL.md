---
name: biobuzz-ftc-loop-time-optimization
description: "Biobuzz FTC OpMode loop time too high (BozoAuto/BozoTeleOp 20ms): reduce hub reads/writes, telemetry cost, flywheel velocity caching."
---

# Biobuzz FTC loop-time reduction

Context: TeamCode in `org.firstinspires.ftc.teamcode`; `Robot` already sets both hubs to `BulkCachingMode.AUTO`; Pedro drive uses `powerThreshold`. Don't redo those.

## Recipe (applied to BozoAuto, 2026-10)
1. **Throttle telemetry**: it is the likeliest culprit (Panels + driver station). Gate `telemetryM.update(telemetry)` behind a `Timer` and `Tunables.telemetryIntervalMillis` (100). Also `Tunables.isDebugging` defaults true.
2. **Flywheel (`subsys/Flywheel.java`)**: `update(rpm)` reads `launchMotor.getVelocity()` once into `cachedVelocityTPS`; `getRPM()/getTPS()` return the cache (so they are only fresh after `update()`). Dedupe `setPower` via `writePower` (skip if |delta| < 0.005; always send changed exact 0/1).
3. **Pose**: call `follower.pose()` once per telemetry push; don't write `HandoffState.pose` every loop, only in `stop()`.
4. **Loop-time metric**: read the timer *before* reset so it includes telemetry cost; reset in `start()` so init time isn't reported.
5. If still slow, profile `follower.update()` (Pinpoint I2C) separately; not yet measured.

## Verify
`./gradlew :TeamCode:compileDebugJavaWithJavac --offline -q` (~3s). On-robot timing must be checked by the user.

## Tool gotcha
Multi-range `PUT a.=b` edits with the edit tool can duplicate adjacent lines when ranges don't match exactly; re-read and `CUT` duplicates.
