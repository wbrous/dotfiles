---
name: biobuzz-bozoauto-add-pose-or-path
description: "Adding a new pose, bezier control point, or path/state branch to Biobuzz BozoAuto (AutoConfig, BlueAuto, RedAuto) and compile-checking it, including post-merge compile errors."
---

Files (TeamCode/src/main/java/org/firstinspires/ftc/teamcode/auto/): AutoConfig.java, BlueAuto.java, RedAuto.java, BozoAuto.java. BlueCloseAuto/RedCloseAuto are empty subclasses, no change needed.

Procedure for each new pose:
1. AutoConfig: add public field + constructor param + assignment (constructor is positional; only BlueAuto/RedAuto call it). All params are `Pose`, so a wrong order compiles and silently swaps poses: keep field order, constructor order, assignment order, and both `buildConfig()` calls identical, in PATH ORDER (start, shoot, refuel, tipped, flower 1, flower 2, park last).
2. BlueAuto and RedAuto: add `public static Pose X` (@Configurable, tunable in Panels) and pass it in buildConfig() in the same order. Group poses with a short heading comment; mark untuned groups once with `DUMMY coords, replace with tuned values`. Keep comments sparse (names + AutoConfig javadoc already explain); don't restate per line. Red mirrors Blue: x -> 144 - x, heading 0<->180, 90<->270.
3. BozoAuto: add Path field, build in buildPaths() (`curve(start, control..., end).linear(start, end)` or `line(a, b).linear(a, b)`; control heading is ignored), add State enum entries, add switch cases in autoUpdate(), call `follower.follow(path)` + `setState(...)` at the transition. Update the class javadoc Sequence.
4. Tipped-hive branch lives in `TRAVEL_TO_SHOOT` (limelight botpose tag count vs Tunables.tagThreshold); untipped = failure (TEMP_FAILED). Tipped sequence: TRAVEL_TO_TIPPED_SHOOT -> SPEED_UP_SECOND_SHOOT -> FEED_SECOND_SHOOT -> flower 1 (TRAVEL_TO_FLOWER_INTERMEDIATE -> TRAVEL_TO_FLOWER -> COLLECT_FLOWER -> TRAVEL_TO_SHOOT_2 -> SPEED_UP_SHOOT_2 -> FEED_SHOOT_2) -> flower 2 (same with _2 / _3 suffixes) -> TRAVEL_TO_PARK -> DONE. All flower shots reuse tippedShootPose. Flywheel keeps spinning between shots; only the last FEED calls shutOff().

Flower leg pattern: shoot pose -> *IntermediatePose at full speed (flower 1 = line, flower 2 = curve with 1 control point), then intermediate -> flower as a line with `.with(Constants.foresightConfig.maxPathSpeed.at(FLOWER_APPROACH_SPEED))` (0.3, constant in BozoAuto, not a Tunable). Collect state reuses Tunables.refuelDurationMillis; travel-into-flower timeout reuses Tunables.maxTravelToRefuelTime.

Multiple control points: Pedro 3.0 `Paths.curve(Pose...)` is varargs, so extra control points just go between start and end (cubic bezier with 2). Tipped path uses tippedControlPose1/tippedControlPose2.

Conventions / user preferences:
- Tipped (scoring-side) shoot pose = untipped shootPose with same x and y -> 144 - y (mirror over y=72); heading flipped (270<->90).
- Pose API in this Pedro version uses `x()`, `y()`, `heading()` — NOT getX()/getY().
- If the user says a leg "doesn't need a control point", convert curve->line and remove the pose from AutoConfig, Blue, Red, BozoAuto, and javadoc (grep to confirm zero leftovers).

Verify: `cd <repo> && JAVA_HOME=/usr/lib/jvm/java-21-openjdk ./gradlew -q :TeamCode:compileDebugJavaWithJavac > /tmp/build.log 2>&1; echo $?` (check the real Gradle exit code, not a grep pipe's).
- System default Java may be 27, which breaks the build script ("Unsupported class file major version 71"): always force JDK 21 via JAVA_HOME.
- After merging a branch, deps may be bumped (e.g. com.pedropathing:revhub) and `--offline` fails to resolve; rerun without --offline.
- After merges, compile errors like "cannot resolve method X in Robot" usually mean the other branch renamed it (e.g. Robot.updateLaunch() -> Robot.update()); grep Robot.java and the TeleOp caller for the new name.

Edit-tool gotchas:
- Anchored ranges must match what was displayed; the batch aborts on the first rejected file, so issue one file per call and retry the identical edit once.
- PUT n.=m: replaces lines n..m INCLUSIVE: if your replacement body includes the closing brace/`*/`, the range must include it too, otherwise old trailing lines are left duplicated (happened with AutoConfig). Re-read after any multi-block edit.
- For small files (Blue/Red/AutoConfig) a whole-file `write` is simpler, but preserve the user's tuned numbers and tell them to check the diff.
