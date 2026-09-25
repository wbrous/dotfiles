---
name: biobuzz-ftc-subsys-package-conventions
description: "Adding new FTC subsystem classes under teamcode/subsys (motors/servos); shows style, PIDF reuse, and how to keep tunables live-editable via Tunables.java."
---

## Scope
Applies to `TeamCode/src/main/java/org/firstinspires/ftc/teamcode/subsys/` and any magic numbers governing robot *behavior* (gains, deadbands, slew rates, thresholds, positions, ranges) anywhere in `teamcode/`.

## Core rule: all behavior-tuning constants live in `Tunables.java`
`TeamCode/src/main/java/org/firstinspires/ftc/teamcode/Tunables.java` is `@Configurable` (byLazar Panels) and is the single source of truth for any constant a mentor/driver might want to adjust without recompiling. This includes, but is not limited to:
- PIDF gains (flywheel, heading/aim controllers, etc.)
- deadbands, slew rates, multipliers
- servo open/closed positions
- shoot-range / angle-acceptance thresholds (`field/GoalTargeting.java` reads these via `import static org.firstinspires.ftc.teamcode.Tunables.*;`)
- drive-shaping constants (slow-mode scale, stopped threshold) even in "standalone" OpModes like `WilsTeleOp`

Fields **must** be `public static` (non-final) — Panels can't edit `final` fields or instance fields.

### What does NOT belong in Tunables
- Physical hardware specs that are facts about the part, not tuning choices (e.g. `Flywheel.TICKS_PER_REV` — a motor's encoder resolution). Changing these live would just produce wrong math.
- Fixed field geometry from the game manual (e.g. `FieldConstants.Goal` positions/facings) — not something adjusted during a match, and restructuring the `Goal` object into flat primitives buys nothing.
- Constants internal to vendored/adapted PedroPathing AutoTune procedures under `pedro/procedures/` (e.g. `ForesightTuner`'s `POWER`/`RUNTIME`/`SAMPLES`) — these are calibration-wizard internals, not team robot-behavior tuning.

## Live-reload pattern (not just init-time read)
Reading a Tunables field once in a constructor only picks up the *startup* value. To make a value truly live-editable mid-match, re-apply it every loop/update call, following `Flywheel.update()`'s pattern:
```java
public void update() {
    pidf.updateTerms(flywheelP, flywheelI, flywheelD, flywheelF); // re-read every tick
    motor.setPower(pidf.calc(targetRPM, getRPM()));
}
```
Same pattern applied to `BozoTeleOp.aimTurnPower()`: `headingPID.updateTerms(Tunables.headingP, Tunables.headingI, Tunables.headingD, Tunables.headingF);` is called at the top of the method (called every loop while aiming), not just once in a field initializer.

Simple per-tick reads (no persistent-state object to update) just reference `Tunables.xxx` directly at point of use — no extra plumbing needed (e.g. `Tunables.aimHeadingDeadbandDeg`, `Tunables.slowModeMinScale`).

## Standard subsystem class shape
```java
package org.firstinspires.ftc.teamcode.subsys;

import static org.firstinspires.ftc.teamcode.Tunables.*;

public class Foo {
    public enum State {OFF, FORWARD, REVERSE} // or OPEN/CLOSED for servos

    private final DcMotor motor; // or Servo
    private State state = State.OFF;

    public Foo(HardwareMap hw) {
        motor = hw.get(DcMotor.class, "lowercasename"); // hardware map name matches README's config
    }

    public State getState() { return state; }

    public void forward() { state = State.FORWARD; motor.setPower(1.0); } // setter mutates state AND commands hardware
}
```
- Minimal one-line comments; no large block comments.
- Constructor takes `HardwareMap hw`, looks up device by exact lowercase name.
- Setter methods are verbs (`forward()/reverse()/off()`, `open()/close()`), not JavaBean-style, and always do state+hardware together.

## Verification
No automated tests exist in this repo. Verify with `./gradlew :TeamCode:compileDebugJavaWithJavac -q` after any Tunables/subsys change.
