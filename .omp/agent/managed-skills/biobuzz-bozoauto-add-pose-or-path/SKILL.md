---
name: biobuzz-bozoauto-add-pose-or-path
description: "Adding a new pose, bezier control point, or path/state branch to Biobuzz BozoAuto (AutoConfig, BlueAuto, RedAuto) and compile-checking it, including post-merge compile errors."
---

Files (TeamCode/src/main/java/org/firstinspires/ftc/teamcode/auto/): AutoConfig.java, BlueAuto.java, RedAuto.java, BozoAuto.java. BlueCloseAuto/RedCloseAuto are empty subclasses, no change needed.

Procedure for each new pose:
1. AutoConfig: add public field + constructor param + assignment (constructor is positional; only BlueAuto/RedAuto call it). Update class javadoc.
2. BlueAuto and RedAuto: add `public static Pose X` (@Configurable, so tunable in Panels) and pass it in buildConfig() in the same order. Mark untuned values `DUMMY coords, replace with tuned values`. Red is a mirror of Blue (x -> 144 - x, heading 0<->180, 90<->270).
3. BozoAuto: add Path field, build in buildPaths() (`curve(start, control..., end).linear(start, end)`; control heading is ignored), add State enum entries, add switch cases in autoUpdate(), call `follower.follow(path)` + `setState(...)` at the transition. Update the class javadoc Sequence.
4. Tipped-hive branch lives in `TRAVEL_TO_SHOOT` (limelight botpose tag count vs Tunables.tagThreshold); untipped = failure (TEMP_FAILED). Tipped chain: TRAVEL_TO_TIPPED_SHOOT -> SPEED_UP_SECOND_SHOOT -> FEED_SECOND_SHOOT -> flower 1 (line out/back, SHOOT_2) -> flower 2 (curve out, line back, SHOOT_3) -> TRAVEL_TO_PARK (curve from tippedShootPose). Repeating pattern per extra shot: TRAVEL_TO_X -> COLLECT_X (timer Tunables.refuelDurationMillis; travel timeout Tunables.maxTravelToRefuelTime) -> TRAVEL_TO_SHOOT_N -> SPEED_UP_SHOOT_N -> FEED_SHOOT_N. Only the LAST feed state calls shutOff(); earlier ones keep flywheel spinning and call robot.intake.forward() before driving off.

Multiple control points: Pedro 3.0 `Paths.curve(Pose...)` is varargs, so extra control points just go between start and end (cubic bezier with 2). Tipped path uses tippedControlPose1/tippedControlPose2 (Red mirrors Blue's x about 72).

Conventions / user preferences:
- Tipped (scoring-side) shoot pose = untipped shootPose with same x and y -> 144 - y (mirror over y=72); heading flipped (270<->90).
- Pose API in this Pedro version uses `x()`, `y()`, `heading()` — NOT getX()/getY().

Verify: `cd <repo> && JAVA_HOME=/usr/lib/jvm/java-21-openjdk ./gradlew -q :TeamCode:compileDebugJavaWithJavac > /tmp/build.log 2>&1; echo $?` (check the real Gradle exit code, not a grep pipe's).
- System default Java may be 27, which breaks the build script ("Unsupported class file major version 71"): always force JDK 21 via JAVA_HOME.
- After merging a branch, deps may be bumped (e.g. com.pedropathing:revhub) and `--offline` fails to resolve; rerun without --offline.
- After merges, compile errors like "cannot resolve method X in Robot" usually mean the other branch renamed it (e.g. Robot.updateLaunch() -> Robot.update()); grep Robot.java and the TeleOp caller for the new name.

Edit-tool gotchas:
- Anchored edit rejects multi-line anchors on lines not displayed; re-read and retry.
- `PUT a.=b:` replaces exactly lines a..b. If the range stops short of the real end of a block (e.g. replacing only the javadoc + part of a class), the old remainder is left duplicated below. Always cover the full block, and re-read the file afterward; remove leftovers with `CUT`.
- When making several PUTs in one edit, use ranges from the same displayed snapshot (they apply against original line numbers).
