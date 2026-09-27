---
name: biobuzz-bozoteleop-regression-patterns
description: "Use when Biobuzz robot drivetrain stops moving or flywheel target RPM changes but actual RPM doesn't follow in BozoTeleOp.java; not general FTC teleop."
---

## Scope
`TeamCode/src/main/java/org/firstinspires/ftc/teamcode/teleop/BozoTeleOp.java`. Two recurring regressions seen during edits to this file's `loop()`.

## Bug 1: drivetrain stops moving — inverted slow-mode multiplier
`slowModeMultiplier` gates every drive axis (`forward`, `strafe`, `turn`). It must evaluate to **full power (1.0) at rest** and reduce only while the slow-mode trigger is held. A common mistake is writing it as `gamepad1.left_trigger * 0.3`, which is `0` at rest (trigger unpressed) — this silently zeroes all drive output and the robot appears completely dead, even though telemetry/loop still runs fine.

Correct form:
```java
double slowModeMultiplier = 1.0 - (gamepad1.left_trigger * 0.7); // 1.0 normally, down to 0.3 while held
```
Verify: comment stating "1.0 by default, minimum at full trigger" — if you ever see `left_trigger * <scale>` with no `1.0 -` in front, that's the bug.

## Bug 2: flywheel target RPM changes but actual RPM never follows
`robot.flywheel.update()` runs the PID (`pidf.calc` + `motor.setPower`). If `update()` is only called inside the gamepad button-press blocks (`bWasPressed`, `dpadUpWasPressed`, `dpadDownWasPressed`) alongside `setRPM(...)`, the PID computes power **once per keypress** instead of continuously. Symptom: dpad-adjusted target RPM telemetry updates correctly every press, but actual RPM telemetry stays flat/never converges, because nothing re-runs the PID loop between presses.

Fix: strip `update()` calls out of the individual button blocks (leave only `setRPM`/`isRunning` mutation there) and call `robot.flywheel.update();` unconditionally once per `loop()` iteration, right after the button-handling block and before the drivetrain code. This matches the documented live-reload pattern in `subsys/Flywheel.java`'s own `update()` (which re-reads `Tunables.flywheel{P,I,D,F}` every tick) — the *caller* must also invoke it every tick, not just on state changes.

## Verification
`./gradlew :TeamCode:compileDebugJavaWithJavac -q` after edits. No on-robot test harness in this repo; report the fix as a bench-test recommendation since these are runtime-hardware bugs, not compile errors — the compiler won't catch either regression.
