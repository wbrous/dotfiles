---
name: biobuzz-bozoauto-add-pose-or-path
description: "Adding a new pose, bezier control point, or path/state branch to Biobuzz BozoAuto (AutoConfig, BlueAuto, RedAuto) and compile-checking it, including post-merge compile errors."
---

Files (TeamCode/src/main/java/org/firstinspires/ftc/teamcode/auto/): AutoConfig.java, BlueAuto.java, RedAuto.java, BozoAuto.java. BlueCloseAuto/RedCloseAuto are empty subclasses, no change needed.

Procedure for each new pose:
1. AutoConfig: add public field + constructor param + assignment (constructor is POSITIONAL and every param is a Pose, so a wrong order compiles and silently swaps poses; only BlueAuto/RedAuto call it). Keep field order, constructor order and buildConfig() order identical, in path order (start, shoot, refuel, tipped, flower 1, flower 2, park).
2. BlueAuto and RedAuto: add `public static Pose X` (@Configurable, so tunable in Panels) and pass it in buildConfig() in the same order. Mark untuned values `DUMMY coords, replace with tuned values` once per group. Red is a mirror of Blue (x -> 144 - x, heading +/-180, 270<->90). Keep comments minimal: group headings only; pose names + AutoConfig javadoc carry the rest.
3. BozoAuto: add Path field, build in buildPaths() (`curve(start, control..., end).linear(start, end)` or `line(a, b).linear(a, b)`; control heading is ignored), add State enum entries, add switch cases in autoUpdate(), call `follower.follow(path)` + `setState(...)` at the transition. Update the class javadoc sequence AND prose, plus path-field comments (they go stale easily).
4. Tipped-hive branch lives in `TRAVEL_TO_SHOOT` (limelight botpose tag count vs Tunables.tagThreshold); not tipped = TEMP_FAILED. Tipped sequence: TRAVEL_TO_TIPPED_SHOOT -> SPEED_UP_SECOND_SHOOT -> FEED_SECOND_SHOOT -> per flower [TRAVEL_TO_FLOWER(_2)_INTERMEDIATE -> TRAVEL_TO_FLOWER(_2) -> COLLECT_FLOWER(_2) -> TRAVEL_FROM_FLOWER(_2)_TO_INTERMEDIATE -> TRAVEL_TO_SHOOT_2/3 -> SPEED_UP_SHOOT_2/3 -> FEED_SHOOT_2/3] -> TRAVEL_TO_PARK. Flywheel stays on until FEED_SHOOT_3 (shutOff() only there). Flower legs: approach to intermediate at full speed (flower 1 line, flower 2 curve w/ 1 control pt), intermediate->flower line capped via `Constants.foresightConfig.maxPathSpeed.at(FLOWER_APPROACH_SPEED=0.3)`, then back out to intermediate, then line to tippedShootPose. Collect timing reuses Tunables.refuelDurationMillis / maxTravelToRefuelTime. User added robot.flower.goDown()/goUp() calls in these states; preserve them.

Multiple control points: Pedro 3.0 `Paths.curve(Pose...)` is varargs, so extra control points just go between start and end (cubic bezier with 2). Tipped path uses tippedControlPose1/tippedControlPose2 (Red mirrors Blue's x about 72).

Conventions / user preferences:
- Tipped (scoring-side) shoot pose = untipped shootPose with same x and y -> 144 - y (mirror over y=72); heading flipped (270<->90).
- Pose API in this Pedro version uses `x()`, `y()`, `heading()` — NOT getX()/getY().
- When a user says "in between X and Y" for multi-instance legs (two flowers), apply to all instances and state that assumption.

Verify: `cd <repo> && JAVA_HOME=/usr/lib/jvm/java-21-openjdk ./gradlew -q :TeamCode:compileDebugJavaWithJavac > /tmp/build.log 2>&1; echo $?` (check the real Gradle exit code, not a grep pipe's). No hardware here: say on-robot behavior is untested.
- System default Java may be 27, which breaks the build script ("Unsupported class file major version 71"): always force JDK 21 via JAVA_HOME.
- After merging a branch, deps may be bumped (e.g. com.pedropathing:revhub) and `--offline` fails to resolve; rerun without --offline.
- After merges, compile errors like "cannot resolve method X in Robot" usually mean the other branch renamed it (e.g. Robot.updateLaunch() -> Robot.update()); grep Robot.java and the TeleOp caller for the new name.

Edit-tool gotchas:
- Anchors must be lines that were displayed; re-read the range and retry. Batched multi-file edits abort on the first failure, so issue one file per call.
- A PUT range that ends short leaves the old body behind (duplicate class); re-read the file after large PUTs. Ranges must include the closing brace if the body does.
- For small files (BlueAuto/RedAuto/AutoConfig) a whole-file `write` is simpler for reorders, but it overwrites user tuning edits made meanwhile, so re-read first; prefer targeted CUT/PUT for single-field removals.
