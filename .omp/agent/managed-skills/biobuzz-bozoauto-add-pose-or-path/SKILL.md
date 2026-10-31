---
name: biobuzz-bozoauto-add-pose-or-path
description: "Adding a new pose, bezier control point, or path/state branch to Biobuzz BozoAuto (AutoConfig, BlueAuto, RedAuto) and compile-checking it, including post-merge compile errors."
---

Files (TeamCode/src/main/java/org/firstinspires/ftc/teamcode/auto/): AutoConfig.java, BlueAuto.java, RedAuto.java, BozoAuto.java. BlueCloseAuto/RedCloseAuto are empty subclasses, no change needed.

Procedure for each new pose:
1. AutoConfig: add public field + constructor param + assignment. Constructor is positional and every param is a `Pose`, so a wrong order compiles silently. Keep fields, params, assignments, and the Blue/Red `buildConfig()` call in the SAME path order (start, shoot, refuel intermediate/refuel, tipped control1/2/shoot, flower control/intermediate/flower, flower2 ..., park control/park). Only BlueAuto/RedAuto call it.
2. BlueAuto and RedAuto: add `public static Pose X` (@Configurable, tunable in Panels) in the same order and pass it in buildConfig(). Mark untuned values with one group-level `DUMMY coords, replace with tuned values` comment. Red is a mirror of Blue (x -> 144 - x, heading 0<->180, 90<->270). Keep comments minimal: group headings only, no per-line restatements.
3. BozoAuto: add Path field, build in buildPaths() (`curve(start, control..., end).linear(start, end)` or `line(a, b).linear(a, b)`; control heading is ignored), add State enum entries, add switch cases in autoUpdate(), call `follower.follow(path)` + `setState(...)` at the transition. Update the class javadoc Sequence.
4. Tipped-hive branch lives in `TRAVEL_TO_SHOOT` (limelight botpose tag count vs Tunables.tagThreshold); not tipped -> TEMP_FAILED. Tipped sequence now: tipped shoot -> flower1 (curve to flowerIntermediate full speed, then line at FLOWER_APPROACH_SPEED=0.3 via `.with(Constants.foresightConfig.maxPathSpeed.at(x))`) -> collect (Tunables.refuelDurationMillis, timeout Tunables.maxTravelToRefuelTime) -> line back to tippedShootPose -> shoot -> same for flower2 -> shoot 3 -> shutOff() -> curve (parkControlPose) to park. Flywheel/intake stay on between shots; only the last FEED state calls shutOff().

Multiple control points: Pedro 3.0 `Paths.curve(Pose...)` is varargs, extra control points go between start and end (cubic bezier with 2).

Conventions / user preferences:
- Tipped (scoring-side) shoot pose = shootPose x, y -> 144 - y; heading flipped (270<->90).
- Pose API uses `x()`, `y()`, `heading()` — NOT getX()/getY().
- User wants path-order layout and stale comments removed in AutoConfig/Blue/Red.

Verify: `cd <repo> && JAVA_HOME=/usr/lib/jvm/java-21-openjdk ./gradlew -q :TeamCode:compileDebugJavaWithJavac > /tmp/build.log 2>&1; echo $?` (check the real Gradle exit code). No on-robot smoke test is possible here; say so.
- System default Java may be 27 and breaks the build ("Unsupported class file major version 71"): force JDK 21 via JAVA_HOME.
- After merging a branch, deps may be bumped and `--offline` fails; rerun without --offline.
- After merges, "cannot resolve method X in Robot" usually means a rename (e.g. Robot.updateLaunch() -> Robot.update()); grep Robot.java and the TeleOp caller.

Edit-tool gotchas: anchored ranges must match lines previously displayed; a multi-file `edit` batch aborts at the first rejected file, and PUT ranges must not include the closing brace if your body repeats it. For small files being fully reordered (Blue/Red/AutoConfig), use `write` for the whole file, then re-check tuned numbers are unchanged. When replacing a class-level block, re-read afterwards: an under-wide range leaves a duplicate stale copy.
