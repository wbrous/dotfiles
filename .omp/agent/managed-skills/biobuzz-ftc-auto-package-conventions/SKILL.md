---
name: biobuzz-ftc-auto-package-conventions
description: "Use when adding or modifying autonomous OpModes in the St-Marks-Robotics-FTC/Biobuzz repo's TeamCode/src/main/java/org/firstinspires/ftc/teamcode/auto/ package (BozoAuto, BlueAuto/RedAuto, BlueCloseAuto/RedCloseAuto, AutoConfig) — covers the alliance-pair symmetry convention, how to check whether a commit's changes are already applied before assuming work remains, diagnosing PedroPathing \"line length != 0\" crashes caused by zero-length line() paths, and exactly where each pose lives (BlueAuto/RedAuto static Pose fields vs. getStartPose() overrides in the Close leaf classes) and how to seed dummy-but-distinct placeholder coordinates so paths build without measured field data yet. Also covers PedroPathing v3 core's Follower.manual(...) call semantics (confirmed via bytecode decompile of core-3.0.0.jar): it FULLY OVERWRITES the stored manualPowers DrivePowers, it does NOT merge/accumulate across calls — calling follower.manual(fwd, strafe, 0) then later in the same loop tick calling follower.manual(0, 0, turn) silently zeroes the translation set by the first call. Any teleop/auto code that wants to blend translation from one source (driver sticks) with rotation from another (e.g. a heading-lock PID aiming at a goal) must compute forward/strafe/turn as three local doubles first and call follower.manual(...) exactly once per loop tick — never call it twice expecting the second call to only patch one axis. ManualDrive.fieldCentric(forward, strafe, turn, heading) is safe to compose with this pattern: bytecode confirms it rotates only the forward/strafe vector by heading and passes turn through unchanged, so an aim-override turn value can be computed once and passed into fieldCentric() alongside stick-derived forward/strafe."
---

## Alliance-pair symmetry convention

BlueAuto/RedAuto and BlueCloseAuto/RedCloseAuto mirror each other's poses. Before assuming a commit's target changes are still needed, check whether they're already applied — read the current state of the relevant Pose fields/getStartPose() overrides first, don't blindly re-patch.

## Pose ownership

- BlueAuto/RedAuto: static Pose fields (e.g. `shootLeftPose`) live directly in these classes.
- BlueCloseAuto/RedCloseAuto: leaf classes that override `getStartPose()` rather than adding new static fields.

When seeding placeholder/dummy coordinates before real field measurements exist, make them dummy-but-*distinct* (not all zeros or duplicates) so PedroPathing's path builder doesn't produce a zero-length `line()` and crash with "line length != 0" at runtime.

## `Follower.manual(...)` overwrite semantics (PedroPathing v3 core, confirmed via bytecode)

Decompiling `core-3.0.0.jar`'s `Follower.class`:

```
public void manual(DrivePowers) {
    clearState();
    mode = Mode.MANUAL;
    manualPowers = <the argument>;   // full overwrite, not a merge
}

public void manual(double fwd, double strafe, double turn) {
    manual(new DrivePowers(fwd, strafe, turn));  // just delegates to the overload above
}
```

There is no accumulation across calls. Each call to `manual(...)` (either overload) completely replaces whatever `manualPowers` held before.

**Failure mode this causes:** code that tries to "drive normally, but let a PID override just the turn axis" by calling `follower.manual(forward, strafe, 0)` and then later in the same loop tick calling `follower.manual(0, 0, turnPower)` (e.g. inside a `driveTowardsGoal(...)` helper) will silently lose all translation the instant the second call fires — the robot only rotates, stick input does nothing, with no compile error and no obvious runtime error to point at the cause.

**Fix pattern:** compute `forward`, `strafe`, `turn` as three local `double`s first (substituting a PID-computed turn value in place of the stick-derived one when an override is active), then call `follower.manual(forward, strafe, turn)` — or build one `DrivePowers`/pass through `ManualDrive.fieldCentric(...)` — exactly once per loop tick.

**`ManualDrive.fieldCentric(forward, strafe, turn, heading)` is safe to use with this pattern.** Bytecode confirms it only rotates the `(forward, strafe)` vector by `-heading` (well, `-(heading + 0)` for the 2-arg overload) and passes `turn` straight through into the new `DrivePowers` unchanged. So a PID-computed turn override composes correctly whether you're in robot-centric or field-centric drive mode — just make sure it's still only fed through exactly one `follower.manual(...)`/`follower.manual(DrivePowers)` call per tick, same as above.
