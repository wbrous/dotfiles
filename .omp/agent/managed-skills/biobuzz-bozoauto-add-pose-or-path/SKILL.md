---
name: biobuzz-bozoauto-add-pose-or-path
description: "Adding a new pose, bezier control point, or path/state branch to Biobuzz BozoAuto (AutoConfig, BlueAuto, RedAuto) and compile-checking it."
---

Files (TeamCode/src/main/java/org/firstinspires/ftc/teamcode/auto/): AutoConfig.java, BlueAuto.java, RedAuto.java, BozoAuto.java. BlueCloseAuto/RedCloseAuto are empty subclasses, no change needed.

Procedure for each new pose:
1. AutoConfig: add public field + constructor param + assignment (constructor is positional; only BlueAuto/RedAuto call it).
2. BlueAuto and RedAuto: add `public static Pose X` (@Configurable, so tunable in Panels) and pass it in buildConfig() in the same order. Mark untuned values `DUMMY coords, replace with tuned values`. Red is a mirror of Blue (heading +/-180, mirrored x/y).
3. BozoAuto: add Path field, build in buildPaths() (`curve(start, control, end).linear(start, end)`; control heading is ignored), add State enum entries, add switch cases in autoUpdate(), call `follower.follow(path)` + `setState(...)` at the transition.
4. Tipped-hive branch lives in `TRAVEL_TO_SHOOT` (limelight botpose tag count vs Tunables.tagThreshold); untipped = UNTIPPED_* states, tipped = TIPPED_* states, both converge on TRAVEL_TO_PARK.

Verify: `cd <repo> && ./gradlew --offline -q :TeamCode:compileDebugJavaWithJavac` (~6s; the "source value 8 obsolete" warnings are normal).

Gotcha: edit tool rejects multi-line anchors on lines not displayed; just retry the identical edit once after confirming the content matches.
