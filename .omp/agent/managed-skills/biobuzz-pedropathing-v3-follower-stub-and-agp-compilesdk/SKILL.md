---
name: biobuzz-pedropathing-v3-follower-stub-and-agp-compilesdk
description: "Use when the St-Marks-Robotics-FTC/Biobuzz repo's Gradle build fails/hangs, the Driver Station shows the Control Hub disconnected/blinking blue (RC app crash loop) despite good Wi-Fi, or auto/teleop OpModes NPE on startup after calling Constants.create(hardwareMap) for the PedroPathing Follower — covers verifying gradle/AGP config against the sibling ../2026Testing repo (ground truth) instead of trusting git-log archaeology or prior \"fixed my builds\" commits, the stale compileSdkVersion 30 vs compileSdk 34 trap, why Biobuzz's pedro/ package (PedroPathing 3.0.0 revhub API: Follower.follow(Path)/.pose()/.manual(), com.pedropathing.api.Paths) must NOT be reverted to 2026Testing's classic ftc:2.1.2 pedroPathing/ package (different robot, incompatible API, 73 compile errors), why Constants.create() returning null is a missing-hardware-calibration issue (not a build/tooling bug — do not fabricate PinpointConfig offsets/directions), the orphaned com.pedropathing:ftc:2.1.2 dependency that causes a real on-robot RC-app crash loop (Control Hub blinking blue = keep-alive timeout, NOT a Wi-Fi problem) via a silent Gradle transitive version bump (core:2.1.2 - 3.0.0) that bundles binary-incompatible ftc-2.1.2 bytecode into the same dex as core-3.0.0, verified/fixed by checking ./gradlew :TeamCode:dependencies --configuration debugRuntimeClasspath | grep pedropathing for a - version-bump arrow and deleting the unused implementation 'com.pedropathing:ftc:2.1.2' line once confirmed zero com.pedropathing.ftc.* imports exist in source, and the standalone SimpleMecanumTeleOp fallback OpMode (raw hardwareMap DcMotor mecanum drive, zero Follower/odometry dependency, motor names+directions sourced from pedro/Constants.java's driveConfig) used to get the robot driving before the Follower/localizer stack is calibrated."
---

## REV Control Hub blinking blue + Driver Station disconnected despite good Wi-Fi

Blinking blue (per REV's official LED blink code docs) = "keep alive has timed out" — the
Robot Controller app stopped responding, NOT a Wi-Fi/network problem. If Wi-Fi is confirmed fine,
suspect an RC app crash loop caused by the app code itself, not networking.

### Root cause found in this repo: orphaned `com.pedropathing:ftc:2.1.2` dependency

Biobuzz's `build.dependencies.gradle` kept `implementation 'com.pedropathing:ftc:2.1.2'` from
before the team migrated `BozoAuto`/`BozoTeleOp`/the Tuner OpModes to the newer PedroPathing v3
API (`com.pedropathing:revhub:3.0.0` + `com.pedropathing:tuning:1.0.0`, using
`com.pedropathing.api.Paths`, `Follower.follow(Path)`, `.pose()`, `.manual()`). No source file
imports `com.pedropathing.ftc.*` anymore.

`ftc:2.1.2` transitively pulls `com.pedropathing:core:2.1.2`. Gradle's default "highest version
wins" resolution silently bumps this to `3.0.0` (since `revhub`/`tuning` need it) — but the
already-compiled `ftc-2.1.2.aar` bytecode was built against `core-2.1.2`'s API shape, a completely
different major version (different `Follower` constructor, no `com.pedropathing.api` package,
different `FollowerBuilder`/`FollowerConstants`/`MecanumConstants` types that don't exist in 3.0.0).
Both class sets land in the same dex. The FTC SDK's OpMode annotation scanner (plus
`dev.frozenmilk.sinister`'s scanner, pulled in by `tuning`) walks and verifies every class in the
dex at boot to find `@TeleOp`/`@Autonomous` classes — this forces ART to verify the orphaned
`ftc-2.1.2` classes against the real `core-3.0.0` runtime jar, throwing `VerifyError`/
`NoSuchMethodError` → RC app crashes → restarts → crash loop → DS keep-alive times out → blinking
blue. This happens even in a "successful" local Gradle build, because Gradle only resolves one
`core` version for compilation/dexing — it never checks binary compatibility between artifacts
compiled against different major versions of a shared transitive dependency.

**Diagnose:**
```
./gradlew :TeamCode:dependencies --configuration debugRuntimeClasspath | grep pedropathing
```
Look for a `->` arrow on any `pedropathing:core` line (e.g. `core:2.1.2 -> 3.0.0`) — that arrow is
the smoking gun for a silent transitive version conflict.

**Fix:** grep source for `import com.pedropathing.ftc.` first to confirm the artifact is truly
unused, then delete the `implementation 'com.pedropathing:ftc:2.1.2'` line from
`build.dependencies.gradle`. Verify the fix by re-running the dependency-tree grep (no more `->`
arrows on `core`) and rebuilding (`BUILD SUCCESSFUL` alone doesn't prove the fix — the arrow's
absence is the actual proof of a single consistent `core` version in the final dex).

## Ground truth for gradle/AGP pairing

`../2026Testing` (sibling repo, same org, same machine) is the authoritative source for stock
Gradle/AGP/build-file config — NOT git-log archaeology of Biobuzz's own history (prior "fixed my
builds" commits are unreliable; don't trust a managed skill built from git-log alone over a diff
against this reference repo). Diff every top-level build file
(`build.gradle`, `gradle.properties`, `settings.gradle`, `build.common.gradle`, `gradlew`/
`gradlew.bat`, `gradle/wrapper/gradle-wrapper.properties`, manifests) against `2026Testing`'s copy
before touching any of them.

`FtcRobotController/build.gradle`'s `compileSdkVersion 30` (a stale leftover from years of
copy-pasted FIRST SDK version bumps, never updated alongside AGP 8.13.2) is a confirmed, safe fix:
replace with `2026Testing`'s `compileSdk 34`.

## Do NOT blindly port 2026Testing's application code

`2026Testing` is a **different robot** running PedroPathing's classic `ftc:2.1.2` API
(`FollowerBuilder`, `FollowerConstants`, `MecanumConstants`, `PinpointConstants`, package
`org.firstinspires.ftc.teamcode.pedroPathing`). Biobuzz's `pedro/` package and app code (`BozoAuto`,
`BozoTeleOp`) were deliberately written against the newer `revhub`/`tuning` v3 API. Deleting
Biobuzz's `pedro/` package and reverting `build.dependencies.gradle` to `2026Testing`'s dependency
list produces 73 compile errors (`follower.follow(Path)`, `follower.pose()`, `follower.manual(...)`,
`com.pedropathing.api.Paths` all vanish). Only port infrastructure/tooling config
(gradle wrapper, AGP version, compileSdk) from `2026Testing`, never feature/API-level source code,
without first confirming the two repos target the same PedroPathing major version.

## `Constants.create()` returning null — missing hardware calibration, not a bug to code around

`pedro/Constants.java`'s `create(HardwareMap)` is a stub (`return null;`) — a real NPE waiting to
happen the instant any OpMode calls it. The real fix requires constructing
`new Follower(localizer, drivetrain, algorithm)` via `PinpointLocalizer` + `Mecanum` + `Foresight`
(decompiled from `core-3.0.0.jar`/`revhub-3.0.0.aar` — no sources jar published for `core:3.0.0`,
use `javap -c` to check `ConfigVar.required()` vs `.of()` bytecode calls to know which fields need
real values). `PinpointConfig`'s `name`, `xPodOffset`, `yPodOffset`, `xPodDirection`,
`yPodDirection` are ALL `ConfigVar.required()` with zero library defaults, and this repo has no
calibration data for them anywhere — they only come from physically running the already-existing
`PinpointTuner`/`ForesightTuner` OpModes (`pedro/procedures/`) on the robot. Do not fabricate these
numbers to make the stub "compile clean" — wrong calibration data drives the robot incorrectly
while looking like it works. State the missing hardware prerequisite instead.

## Fallback: SimpleMecanumTeleOp (no odometry, four wheels only)

For "just make the robot drive, no Follower/Pedro at all" requests: a standalone `@TeleOp` OpMode
that skips `Follower`/`Constants`/`Robot`/odometry entirely — grabs `frontLeft`/`frontRight`/
`backLeft`/`backRight` directly via `hardwareMap.get(DcMotor.class, name)`, sets directions to match
the actual wiring (left side `REVERSE`, right side `FORWARD` — pulled from `pedro/Constants.java`'s
`driveConfig`, the one already-verified source of truth for this robot's physical motor wiring, not
guessed), and does standard robot-centric mecanum mixing (`y + x + rx` / `y - x + rx` / `y - x - rx`
/ `y + x - rx`, normalized to max 1.0, left-trigger slow mode). This is the right scope boundary
when a full Follower-based drive isn't ready yet (e.g. blocked on physical odometry calibration) —
ship the OpMode that only needs the four drive motors' hardware config names, nothing else.
