---
name: biobuzz-merge-master-into-dev-branch
description: "Merging master into a Biobuzz dev branch (dev-wbrous/dev-bang): stale local master, subsystem add/add conflicts, BozoAuto API port, compile check."
---

## Steps
1. `git fetch origin`; local `master` is usually stale, so merge `origin/master`, not `master`. Check with `git rev-list --left-right --count master...origin/master`.
2. Expect conflicts in `Robot`, `Tunables`, `pedro/Constants`, `subsys/{Flywheel,Intake,Transfer}`, `teleop/BozoTeleOp`, README. Dev branches and master built the same subsystems independently (add/add). Master's versions are the shared API (`Flywheel.update(double rpm)`, `Robot.startLaunch()/updateLaunch()`, `subsys/Field`, `Vision`) used by `tuner/FlywheelTuner` and master's teleop. Use `git checkout --theirs -- <file>` for those, then re-add branch-only tunables.
3. Master deleted `pedro/Tuning.java` and the `pedro/procedures` dir; the dev branch's `field/FieldConstants` and `field/GoalTargeting` are orphaned once old teleop is replaced, so `git rm` them (grep to confirm no other users).
4. Port branch-only callers (e.g. `auto/BozoAuto`) to master's Flywheel API: old `setRPM/isWithinMargin/getTargetRPM/update()` become a local `targetRPM` field plus `robot.flywheel.update(targetRPM)`. Move the auto tunables (`shootRPM`, `flywheelRPMMargin`, `feedDurationMillis`, `refuelDurationMillis`) into `Tunables`.
5. Verify: `./gradlew :TeamCode:compileDebugJavaWithJavac -q`. `--offline` fails after master dependency bumps (pedro/fullpanels not cached), so run online. JDK-8 option warnings are normal.
6. `git add -A && git commit --no-edit`. Don't push unless asked. Tell the user what their branch loses (retuned gains, offsets, old controls).
