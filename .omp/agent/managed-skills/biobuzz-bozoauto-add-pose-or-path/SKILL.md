---
name: biobuzz-bozoauto-add-pose-or-path
description: "Adding a new pose, bezier control point, or path/state branch to Biobuzz BozoAuto (AutoConfig, BlueAuto, RedAuto), mirroring Blue from Red, and compile-checking it, including post-merge compile errors."
---

Files (Biobuzz/TeamCode/src/main/java/org/firstinspires/ftc/teamcode/auto/ under ~/Projects/Robotics): AutoConfig.java, BlueAuto.java, RedAuto.java, BozoAuto.java. BlueCloseAuto/RedCloseAuto are empty subclasses, no change needed. ~/Projects/Robotics/Decode has same-named files but is an old repo (Feb); Biobuzz is the active one.

Procedure for each new pose:
1. AutoConfig: add public field + constructor param + assignment (constructor is POSITIONAL and every param is a Pose, so a wrong order compiles and silently swaps poses; only BlueAuto/RedAuto call it). Keep field order, constructor order and buildConfig() order identical, in path order (start, shoot, refuel, tipped, flower 1, flower 2, park).
2. BlueAuto and RedAuto: add `public static Pose X` (@Configurable, so tunable in Panels) and pass it in buildConfig() in the same order. Mark untuned values `DUMMY coords, replace with tuned values` once per group. Keep comments minimal: group headings only; pose names + AutoConfig javadoc carry the rest.
   MIRROR RULE (confirmed by user: "make blueauto positions mirror redauto ... and rotation"): the two sides are related by POINT REFLECTION through field centre, `(x, y, θ) -> (144-x, 144-y, θ+180°)` (e.g. heading 90<->270, 180<->0, 210<->30). Red is the tuned source of truth; when asked to mirror, copy Red into Blue with this rule (positions AND headings). `tippedShootPose` is computed from shootPose so it already follows. Verify mechanically instead of by eye: regex all `Pose name = new Pose(x, y, Math.toRadians(h))` in both files and assert blue == (144-x, 144-y, (h+180)%360) for every name (13 poses, 0 mismatches last time).
3. BozoAuto: add Path field, build in buildPaths() (`curve(start, control..., end).linear(start, end)` or `line(a, b).linear(a, b)`; control heading is ignored), add State enum entries, add switch cases in autoUpdate(), call `follower.follow(path)` + `setState(...)` at the transition. Update the class javadoc sequence AND prose, plus path-field comments (they go stale easily).
4. Tipped-hive branch lives in `TRAVEL_TO_SHOOT` (limelight botpose tag count vs Tunables.tagThreshold); not tipped = TEMP_FAILED. Tipped sequence: TRAVEL_TO_TIPPED_SHOOT -> SPEED_UP_SECOND_SHOOT -> FEED_SECOND_SHOOT -> per flower [TRAVEL_TO_FLOWER(_2)_INTERMEDIATE -> TRAVEL_TO_FLOWER(_2) -> COLLECT_FLOWER(_2) -> TRAVEL_FROM_FLOWER(_2)_TO_INTERMEDIATE -> TRAVEL_TO_SHOOT_2/3 -> SPEED_UP_SHOOT_2/3 -> FEED_SHOOT_2/3] -> TRAVEL_TO_PARK. Flywheel stays on until FEED_SHOOT_3 (shutOff() only there). Flower legs: approach to intermediate at full speed (flower 1 line, flower 2 curve w/ 1 control pt), intermediate->flower line capped via `Constants.foresightConfig.maxPathSpeed.at(FLOWER_APPROACH_SPEED=0.3)`, then back out to intermediate, then line to tippedShootPose. Collect timing reuses Tunables.refuelDurationMillis / maxTravelToRefuelTime. User added robot.flower.goDown()/goUp() calls in these states; preserve them.

Multiple control points: Pedro 3.0 `Paths.curve(Pose...)` is varargs, so extra control points just go between start and end (cubic bezier with 2).

Conventions / user preferences:
- Tipped (scoring-side) shoot pose = untipped shootPose with same x and y -> 144 - y (mirror over y=72); heading flipped (270<->90).
- Pose API in this Pedro version uses `x()`, `y()`, `heading()` — NOT getX()/getY().
- When a user says "in between X and Y" for multi-instance legs (two flowers), apply to all instances and state that assumption.
- Edits to Blue/Red are left uncommitted in the working tree unless asked.

Verify: `cd <repo> && JAVA_HOME=/usr/lib/jvm/java-21-openjdk ./gradlew -q :TeamCode:compileDebugJavaWithJavac > /tmp/build.log 2>&1; echo $?` (check the real Gradle exit code, not a grep pipe's). No hardware here: say on-robot behavior is untested.
- System default Java may be 27, which breaks the build script ("Unsupported class file major version 71"): always force JDK 21 via JAVA_HOME.
- After merging a branch, deps may be bumped (e.g. com.pedropathing:revhub) and `--offline` fails to resolve; rerun without --offline.
- After merges, compile errors like "cannot resolve method X in Robot" usually mean the other branch renamed it (e.g. Robot.updateLaunch() -> Robot.update()); grep Robot.java and the TeleOp caller for the new name.

Tooling notes: the `find` tool's judge may be down (401); use `bash find ... -name` with `timeout`, scoped to ~/Projects/Robotics (a /home/wils-wide find times out at 60s).

Edit-tool gotchas:
- Anchors must be lines that were displayed; re-read the range and retry. Batched multi-file edits abort on the first failure, so issue one file per call.
- A PUT range that ends short leaves the old body behind (duplicate class); re-read the file after large PUTs. Ranges must include the closing brace if the body does.
- For small files (BlueAuto/RedAuto/AutoConfig) a whole-file `write` is simpler for reorders, but it overwrites user tuning edits made meanwhile, so re-read first; prefer targeted PUT for single-field changes.
