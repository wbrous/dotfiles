---
name: biobuzz-pedropathing-v3-follower-stub-and-agp-compilesdk
description: "Use when the St-Marks-Robotics-FTC/Biobuzz repo's Gradle build fails/hangs, the Driver Station shows the Control Hub disconnected/blinking blue (RC app crash loop) despite good Wi-Fi, or auto/teleop OpModes NPE on startup after calling Constants.create(hardwareMap) for the PedroPathing Follower — covers verifying gradle/AGP config against the sibling ../2026Testing repo (ground truth) instead of trusting git-log archaeology or prior \"fixed my builds\" commits, the stale compileSdkVersion 30 vs compileSdk 34 trap, why Biobuzz's pedro/ package (PedroPathing 3.0.0 revhub API: Follower.follow(Path)/.pose()/.manual(), com.pedropathing.api.Paths) must NOT be reverted to 2026Testing's classic ftc:2.1.2 pedroPathing/ package (different robot, incompatible API, 73 compile errors), why Constants.create() returning null is a missing-hardware-calibration issue (not a build/tooling bug — do not fabricate PinpointConfig offsets/directions), the orphaned com.pedropathing:ftc:2.1.2 dependency that causes a real on-robot RC-app crash loop (Control Hub blinking blue = keep-alive timeout, NOT a Wi-Fi problem) via a silent Gradle transitive version bump (core:2.1.2 - 3.0.0) that bundles binary-incompatible ftc-2.1.2 bytecode into the same dex as core-3.0.0, verified/fixed by checking ./gradlew :TeamCode:dependencies --configuration debugRuntimeClasspath | grep pedropathing for a - version-bump arrow and deleting the unused implementation 'com.pedropathing:ftc:2.1.2' line once confirmed zero com.pedropathing.ftc.* imports exist in source, and the standalone SimpleMecanumTeleOp fallback OpMode (raw hardwareMap DcMotor mecanum drive, zero Follower/odometry dependency, motor names+directions sourced from pedro/Constants.java's driveConfig) used to get the robot driving before the Follower/localizer stack is calibrated. Also covers: new feature/dev branches created off older history (e.g. dev-bang) commonly lack these two fixes and need them reapplied — diagnose fast via git diff branch master -- '*.gradle', which should show only (1) FtcRobotController/build.gradle compileSdkVersion 30 → compileSdk 34, and (2) build.dependencies.gradle removing the orphaned implementation 'com.pedropathing:ftc:2.1.2' line (confirm zero com.pedropathing.ftc.* source imports first, matching master/dev-wbrous exactly)."
---

## Symptom
A branch (e.g. `dev-bang`) was forked from older history and is missing the gradle/dependency fixes already present on `master` and `dev-wbrous`. Symptoms: Gradle sync fails with AGP/Gradle internal API errors, or the RC app crash-loops on-robot (Control Hub blinking blue).

## Fast diagnosis
```
git diff <branch> master -- '*.gradle' '.idea/*'
```
On this repo the *only* expected diff is exactly these two changes:

1. `FtcRobotController/build.gradle`: `compileSdkVersion 30` → `compileSdk 34`
2. `build.dependencies.gradle`: remove the line `implementation 'com.pedropathing:ftc:2.1.2'`

(`gradle-wrapper.properties` may show a cosmetic timestamp-comment diff only — not functional, ignore it.)

## Before removing the pedropathing:ftc dependency
Confirm zero `com.pedropathing.ftc.*` imports exist in source:
```
grep -r 'com\.pedropathing\.ftc' .
```
If clean, safe to delete — it's an orphaned dependency that Gradle silently transitively bumps (`core:2.1.2` → `3.0.0`), bundling binary-incompatible `ftc-2.1.2` bytecode into the same dex as `core-3.0.0`, causing the real on-robot RC-app crash loop.

## Apply
Edit both files directly to match `master`/`dev-wbrous`. Verify via `git diff` against the working tree (not branch-to-branch, since edits are uncommitted) shows exactly those two hunks.

## Why this keeps recurring
Feature/dev branches get cut from commits that predate these fixes landing on `master`. Any new branch should be diffed against `master` for `*.gradle` files early, before debugging Gradle sync or RC crash symptoms as if they were novel issues.
