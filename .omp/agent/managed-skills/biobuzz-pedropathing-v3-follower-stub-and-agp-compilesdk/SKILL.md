---
name: biobuzz-pedropathing-v3-follower-stub-and-agp-compilesdk
description: "Use when the St-Marks-Robotics-FTC/Biobuzz repo's Gradle build fails/hangs, or when auto/teleop OpModes NPE on startup after calling Constants.create(hardwareMap) for the PedroPathing Follower — covers verifying gradle/AGP config against the sibling ../2026Testing repo (ground truth) instead of trusting git-log archaeology or prior \"fixed my builds\" commits, the stale compileSdkVersion 30 vs compileSdk 34 trap, why Biobuzz's pedro/ package (PedroPathing 3.0.0 revhub API: Follower.follow(Path)/.pose()/.manual(), com.pedropathing.api.Paths) must NOT be reverted to 2026Testing's classic ftc:2.1.2 pedroPathing/ package (different robot, incompatible API, 73 compile errors), and why Constants.create() returning null is a missing-hardware-calibration issue, not a build/tooling bug."
---

## Ground truth source for gradle/build config

Biobuzz has a sibling reference repo at `../2026Testing` (same org, same FTC SDK lineage) that
represents a *known-working* build setup. When Biobuzz's Gradle build is broken, diff against
`2026Testing` file-by-file instead of trusting git log messages or archaeology of past "fix"
commits (some past commits, e.g. one literally titled "This fixed my builds", regressed things —
git history in this repo is NOT a trustworthy source of truth on its own).

Files to diff: `gradle/wrapper/gradle-wrapper.properties`, `build.gradle`, `gradle.properties`,
`settings.gradle`, `build.common.gradle`, `build.dependencies.gradle`, `gradlew`/`gradlew.bat`,
`*/build.gradle`, `*/src/main/AndroidManifest.xml`, `libs/`.

## The compileSdk trap

`FtcRobotController/build.gradle` in Biobuzz had a stale `compileSdkVersion 30`, carried forward
across years of copy-pasted FIRST SDK release merges, never bumped alongside the repo's pinned
AGP version (8.13.2, which needs a modern compileSdk). `2026Testing`'s equivalent file uses
`compileSdk 34`. Match Biobuzz's `compileSdk` to `2026Testing`'s value whenever build.gradle
divergence is suspected.

## Do NOT wholesale-copy source packages from 2026Testing

Biobuzz and 2026Testing are DIFFERENT ROBOTS running different PedroPathing major versions:

- `2026Testing` uses classic `com.pedropathing:ftc:2.1.2` API, package
  `org.firstinspires.ftc.teamcode.pedroPathing` (`Constants.java`, `Tuning.java` only — no
  Tuner OpModes), `Follower.followPath(...)`/`getPose()`-style calls.
- Biobuzz uses PedroPathing **3.0.0** (`com.pedropathing:revhub:3.0.0` +
  `com.pedropathing:tuning:1.0.0`, resolved from `maven { url
  'https://repo.dairy.foundation/releases/' }`), package
  `org.firstinspires.ftc.teamcode.pedro` (`Constants.java` + `procedures/*Tuner.java` — 8 Tuner
  OpModes for PinpointLocalizer/OTOS/OctoQuad/ThreeWheel/TwoWheel/Mecanum/Foresight tuning),
  `com.pedropathing.api.Paths`, `Follower.follow(Path)`/`.pose()`/`.manual(...)`.

Deleting Biobuzz's `pedro/` package and its `revhub`/`tuning` maven deps to "match 2026Testing"
produces ~73 compile errors (`BozoAuto.java`, `BozoTeleOp.java` call the 3.0.0-only API). If a
diff between the two repos' `build.dependencies.gradle` or `pedro*/` packages shows up, that is
expected divergence, not drift to "fix" — confirm by checking whether real OpModes
(`auto/`, `teleop/`) actually import/use the extra deps/classes before touching them.

## Constants.create() returning null is NOT a build bug

`pedro/Constants.java`'s `create(HardwareMap)` method is a stub: `return null;` (with a comment
`// return new Follower(Drivetrain, Localizer, Foresight);` showing unfinished intent). This
compiles fine and NPEs at OpMode runtime. Real construction requires:

```java
new Follower(
    new PinpointLocalizer(hardwareMap, pinpointConfig),   // com.pedropathing.revhub.localizers
    new Mecanum(hardwareMap, driveConfig),                 // com.pedropathing.revhub.drivetrains
    new Foresight(foresightConfig)                         // com.pedropathing.algorithm
);
```

`PinpointConfig` and `ForesightConfig` take a `Configuration<T>` functional interface (same
lambda pattern already used for `MecanumConfig`: `new PinpointConfig(c -> { c.name.set(...); })`).
BUT: decompiling `revhub-3.0.0.aar`'s `PinpointConfig` bytecode
(`javap -c classes/com/pedropathing/revhub/localizers/PinpointConfig.class`) shows `name`,
`xPodDirection`, `yPodDirection`, `xPodOffset`, `yPodOffset` are all `ConfigVar.required()` —
**no library defaults exist**, and this repo has zero existing calibration data for them
anywhere (verified via grep — no `pinpoint`/`odo` hardware-map references outside the Tuner
files themselves). These values can only come from physically running the already-written
`pedro/procedures/PinpointTuner.java` and `ForesightTuner.java` OpModes on the real robot.

**Do not fabricate these numbers.** Guessing plausible-looking pod offsets/directions would
compile and "look done" while silently driving the robot incorrectly — worse than leaving the
NPE, since it fails silently instead of loudly. Treat this as a genuine missing hardware
prerequisite: state it explicitly, do not synthesize calibration data, and wait for the tuner
run to produce real numbers before wiring `Constants.create()`.

## Verify recipe

`JAVA_HOME=/usr/lib/jvm/java-21-openjdk ./gradlew :TeamCode:assembleDebug` — `BUILD SUCCESSFUL`
is the deliverable proof for build/tooling fixes. This only proves compilation; it does NOT
prove `Constants.create()` won't NPE at runtime — that requires the physical-hardware
calibration step above.
