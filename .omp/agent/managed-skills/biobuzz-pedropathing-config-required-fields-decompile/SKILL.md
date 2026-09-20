---
name: biobuzz-pedropathing-config-required-fields-decompile
description: "Use when a PedroPathing v3 (com.pedropathing:revhub/core 3.0.0) config object — PinpointConfig, MecanumConfig, ForesightConfig, or similar — throws a runtime IllegalStateException \"Config variable has not been set\" in the St-Marks-Robotics-FTC/Biobuzz repo (or any project on this pinned library version), especially when running an AutoTune @Tuner procedure (e.g. ForesightTuner) that constructs a Localizer/Drivetrain from Constants.java. Also covers the general technique of decompiling PedroPathing's actual resolved jar (not the sources jar, which may be a stale cached version) via javap to find which ConfigVar fields are ConfigVar.required(...) (must call .set() or it throws at read-time) vs ConfigVar.of(default, ...) (has a safe default) — and the related follower.manual(...) full-overwrite-not-merge bytecode confirmation."
---

## Symptom
Runtime crash: `java.lang.IllegalStateException: Config variable has not been set`, thrown while running a PedroPathing v3 AutoTune `@Tuner` procedure (e.g. `Tuning.foresightTuner()`), or any code path that constructs a `PinpointLocalizer`/`Mecanum`/`Foresight` from a `Constants.java` config object.

## Root cause pattern
PedroPathing's config classes (`PinpointConfig`, `MecanumConfig`, `ForesightConfig`, etc., in `com.pedropathing.config.ConfigVar<T>`) declare each field as either:
- `ConfigVar.required(...)` — no default; if you never call `.set(...)` on it in your `Constants.java` lambda, reading it later throws exactly this message.
- `ConfigVar.of(defaultValue, ...)` — has a safe default, fine to leave unset.

The error message string lives in `com.pedropathing.config.ConfigVar.class` (`get()`/similar accessor). You cannot tell required-vs-default from the public field list or javadoc alone — you must inspect the constructor bytecode.

## How to find which fields are required, ground-truth
1. **Find the actually-resolved jar version**, not just whatever `-sources.jar` happens to be cached — check the real resolved version via the dependency's `.pom` (e.g. `~/.gradle/caches/modules-2/files-2.1/com.pedropathing/revhub/3.0.0/*/revhub-3.0.0.pom`, grep for `<artifactId>core</artifactId>` to see which `core` version it transitively pulls — it can differ from what's cached as `core-*-sources.jar`).
2. Extract the real class file (not sources): `unzip -o` the resolved `.jar`/`.aar`'s `classes.jar` for the specific class, e.g. `com/pedropathing/algorithm/ForesightConfig.class`, `com/pedropathing/revhub/localizers/PinpointConfig.class`, `com/pedropathing/revhub/drivetrains/MecanumConfig.class`.
3. `javap -p -c -constants ClassName.class` and scan the constructor body: every `putfield` preceded by `ConfigVar.required(...)` is a field you MUST `.set()` in your `Constants.java`; every one preceded by `ConfigVar.of(...)` has a safe default.

Example confirmed for PedroPathing core 3.0.0:
- `PinpointConfig` required: `name`, `xPodDirection`, `yPodDirection`, `xPodOffset`, `yPodOffset` (podType/offsetUnits/globalDistanceUnit/ticksPerUnit/resetMode/encoderResolutionUnit all have defaults).
- `MecanumConfig` required: all 4 motor names + all 4 motor directions (manualBrakeMode/powerThreshold have defaults).
- `ForesightConfig` required: `headingFeedback`, `forwardTranslational`, `strafeTranslational`, `brake`, `coast`, `linearBrakeCoefficients`, `quadraticBrakeCoefficients`, `headingBrakeCoefficients`, `maxAchievableForwardVelocity`, `maxAchievableStrafeVelocity`, `naturalForwardDeceleration`, `naturalStrafeDeceleration` (everything else — constraints, tolerances, scaling factors — has a numeric/boolean default).

If you've confirmed via this technique that a given `Constants.java` config block already sets every required field for the config classes actually involved, and the crash still reproduces on the real robot, the unset field is somewhere else in the call chain — check every config object actually constructed along that path (e.g. an AutoTune tuner may build `Localizer`+`Drivetrain` directly from `Constants.localizerConfig`/`driveConfig` without ever touching `Constants.foresightConfig`, so an incomplete `ForesightConfig` is not the cause of a crash inside a tuner that never builds a `Foresight`).

## Related: `Follower.manual(...)` overwrite semantics (confirmed via same decompile technique)
Decompiling `com.pedropathing.follower.Follower.manual(double,double,double)` in core 3.0.0 shows it constructs a new `DrivePowers` and calls `manual(DrivePowers)`, which does `this.manualPowers = powers` — a full field overwrite, not a merge. Calling `follower.manual(...)` twice in the same loop tick (e.g. once for translation, once later to "just update turn") silently discards whatever the first call set. Any teleop/auto code composing translation from one source and rotation from another must compute `forward`/`strafe`/`turn` as three locals first and call `follower.manual(...)` exactly once per tick. `ManualDrive.fieldCentric(forward, strafe, turn, heading)` is safe to compose with this — bytecode confirms it only rotates the forward/strafe vector by heading and passes `turn` through unchanged, so a computed override turn value (e.g. from a heading-lock PID) can be passed straight into `fieldCentric(...)`.
