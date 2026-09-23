---
name: biobuzz-ftc-auto-package-conventions
description: "Use when adding or modifying autonomous OpModes in the St-Marks-Robotics-FTC/Biobuzz repo's TeamCode/src/main/java/org/firstinspires/ftc/teamcode/auto/ package (BozoAuto, BlueAuto/RedAuto, BlueCloseAuto/RedCloseAuto, AutoConfig) — covers the alliance-pair symmetry convention, how to check whether a commit's changes are already applied before assuming work remains, diagnosing PedroPathing \"line length != 0\" crashes caused by zero-length line() paths, exactly where each pose lives (BlueAuto/RedAuto static Pose fields vs. getStartPose() overrides in the Close leaf classes) and how to seed dummy-but-distinct placeholder coordinates so paths build without measured field data yet, and the BozoAuto.stop()/updateHandoff() unguarded-follower NullPointerException — the actual root cause when a user reports \"when I launch the auto, some poses get NPEd\". Also covers PedroPathing v3 core's Follower.manual(...) call semantics (confirmed via bytecode decompile of core-3.0.0.jar)."
---

## Alliance-pair symmetry convention

BlueAuto/RedAuto and BlueCloseAuto/RedCloseAuto mirror each other's poses. Before assuming a commit's target changes are still needed, check whether they're already applied — read the current state of the relevant Pose fields/getStartPose() overrides first, don't blindly re-patch.

## Pose ownership

- BlueAuto/RedAuto: static Pose fields (e.g. `shootLeftPose`) live directly in these classes.
- BlueCloseAuto/RedCloseAuto: leaf classes that override `getStartPose()` rather than adding new static fields.

When seeding placeholder/dummy coordinates before real field measurements exist, make them dummy-but-*distinct* (not all zeros or duplicates) so PedroPathing's path builder doesn't produce a zero-length `line()` and crash with "line length != 0" at runtime.

## `BozoAuto.stop()`/`updateHandoff()` unguarded-`follower` NPE — THE bug behind "poses get NPEd" on auto launch

```java
// BozoAuto.java
public void stop() {
    updateHandoff();
}
public void updateHandoff() {
    HandoffState.pose = follower.pose();   // follower dereferenced unconditionally
}
```

`follower` is assigned partway through `init()` (`follower = Constants.create(hardwareMap);`), *after* `config = buildConfig()` and `robot = new Robot(hardwareMap)` already ran. If anything earlier in `init()` throws — most commonly `Constants.create(hardwareMap)` failing because a hardware-map device name doesn't match (`"odo"`, `"frontLeft"`, `"frontRight"`, `"backLeft"`, `"backRight"` in `pedro/Constants.java`), or a `PinpointConfig`/`MecanumConfig` required field being unset (see `biobuzz-pedropathing-config-required-fields-decompile`) — the FTC SDK still calls `stop()` as part of its cleanup path even though `init()` never completed. `follower` is still `null` at that point, so `updateHandoff()` throws a **second**, misleading `NullPointerException` on `follower.pose()` while assigning `HandoffState.pose`. This second NPE (on a line that's literally about a `Pose`) is what shows up on the Driver Station and masks the real init failure underneath it — exactly matching the symptom "when I launch the auto, some poses get NPEd".

**Fix:** guard the handoff so the real init exception surfaces instead:
```java
public void updateHandoff() {
    if (follower != null) {
        HandoffState.pose = follower.pose();
    }
}
```

Diagnosis approach when this is reported: don't assume the NPE trace points at the true root cause — check whether `init()` could have thrown *before* line 147 (`follower = Constants.create(...)`), since `stop()` runs regardless of whether `init()` completed.

## Known but currently-inert logic bugs in the same files (not crashes, but landmines)

- `BlueAuto.buildConfig()`/`RedAuto.buildConfig()` pass the class's static default `startPose` field into `AutoConfig`, NOT the actual robot start pose returned by the leaf class's `getStartPose()` override. `config.startPose` is unused today (buildPaths() correctly uses `BozoAuto`'s private `startPose` instance field, which IS set from `getStartPose()`), so this is silently wrong but harmless — until something (dashboard/telemetry) starts reading `config.startPose` expecting the real starting position.
- In `BozoAuto.autoPathUpdate()`, the `GO_TO_RIGHT_FLOWER` case never updates `pastState` (every other transition does `pastState = state;` before moving on). Currently harmless because `SECOND_PICKUP` doesn't gate on `pastState`, but inconsistent with the rest of the state machine.

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

## Locating the actual PedroPathing jar for decompilation

`Constants.java` pulls in `com.pedropathing:revhub:3.0.0`, which transitively resolves `com.pedropathing:core`. Multiple `core` versions can be cached side by side; find the one actually in use via:
```
find /home/wils/.gradle/caches/modules-2/files-2.1/com.pedropathing/core -iname "*.jar"
```
then `unzip` and `javap -p -c` the relevant classes (`com.pedropathing.api.Paths`, `com.pedropathing.paths.Path`, `com.pedropathing.math.Pose`, `com.pedropathing.follower.Follower`) rather than guessing API behavior from memory — this repo has pinned/transitively-resolved versions that don't always match upstream docs.
