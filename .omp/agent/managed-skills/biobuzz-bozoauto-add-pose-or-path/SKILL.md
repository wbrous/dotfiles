---
name: biobuzz-bozoauto-add-pose-or-path
description: "Adding a new pose, bezier control point, or path/state branch to Biobuzz BozoAuto (AutoConfig, BlueAuto, RedAuto) and compile-checking it, including post-merge compile errors."
---

Files (TeamCode/src/main/java/org/firstinspires/ftc/teamcode/auto/): AutoConfig.java, BlueAuto.java, RedAuto.java, BozoAuto.java. BlueCloseAuto/RedCloseAuto are empty subclasses, no change needed.

Procedure for each new pose:
1. AutoConfig: add public field + constructor param + assignment (constructor is positional; only BlueAuto/RedAuto call it).
2. BlueAuto and RedAuto: add `public static Pose X` (@Configurable, so tunable in Panels) and pass it in buildConfig() in the same order. Mark untuned values `DUMMY coords, replace with tuned values`. Red is a mirror of Blue (x -> 144 - x, heading +/-180).
3. BozoAuto: add Path field, build in buildPaths() (`curve(start, control..., end).linear(start, end)`; control heading is ignored), add State enum entries, add switch cases in autoUpdate(), call `follower.follow(path)` + `setState(...)` at the transition. Update the class javadoc "Sequence:" too.
4. Tipped-hive branch lives in `TRAVEL_TO_SHOOT` (limelight botpose tag count vs Tunables.tagThreshold); untipped = failure (TEMP_FAILED), tipped = TRAVEL_TO_TIPPED_SHOOT chain, ending in TRAVEL_TO_PARK.

Current tipped chain (after FEED_SECOND_SHOOT, all from/to tippedShootPose): per flower = full-speed curve to *IntermediatePose (bent by *ControlPose) -> slow linear into flower (`.with(Constants.foresightConfig.maxPathSpeed.at(FLOWER_APPROACH_SPEED))`, 0.3) -> COLLECT (Tunables.refuelDurationMillis; travel timeout Tunables.maxTravelToRefuelTime) -> linear back -> SPEED_UP_SHOOT_n -> FEED_SHOOT_n. Flower 1 then flower 2, shoot 3, then curve to park via parkControlPose. Only the last feed calls shutOff(); earlier ones keep intake/flywheel on. Speed caps: `.with(...maxPathSpeed.at(x))` on a Path; a plain full-speed leg just omits it.

Multiple control points: Pedro 3.0 `Paths.curve(Pose...)` is varargs, so extra control points just go between start and end (cubic bezier with 2). Tipped path uses tippedControlPose1/tippedControlPose2.

Conventions / user preferences:
- Tipped (scoring-side) shoot pose = untipped shootPose with same x and y -> 144 - y (mirror over y=72); heading flipped (270<->90).
- Pose API in this Pedro version uses `x()`, `y()`, `heading()` — NOT getX()/getY().
- Intermediate-before-target poses: place short of the target along the approach axis so the last leg is a straight line.

Verify: `cd <repo> && JAVA_HOME=/usr/lib/jvm/java-21-openjdk ./gradlew -q :TeamCode:compileDebugJavaWithJavac > /tmp/build.log 2>&1; echo $?` (check the real Gradle exit code, not a grep pipe's).
- System default Java may be 27, which breaks the build script ("Unsupported class file major version 71"): always force JDK 21 via JAVA_HOME.
- After merging a branch, deps may be bumped (e.g. com.pedropathing:revhub) and `--offline` fails to resolve; rerun without --offline.
- After merges, compile errors like "cannot resolve method X in Robot" usually mean the other branch renamed it (e.g. Robot.updateLaunch() -> Robot.update()); grep Robot.java and the TeleOp caller for the new name.

Edit-tool pitfalls:
- Anchored edits rejected on lines not displayed: re-read the range and retry.
- `PUT a.=b:` replaces exactly lines a..b. If the range is shorter than the block you are rewriting (e.g. a whole class), the old body is left duplicated below; count the original lines (read the file first) and re-read after the edit. When doing several PUTs in one edit, apply them bottom-to-top so line numbers stay valid.
- Don't trust the compile alone for a doc range; re-read javadoc after editing.
