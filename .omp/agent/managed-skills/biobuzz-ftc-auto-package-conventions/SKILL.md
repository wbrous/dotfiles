---
name: biobuzz-ftc-auto-package-conventions
description: "Use when adding or modifying autonomous OpModes in the St-Marks-Robotics-FTC/Biobuzz repo's TeamCode/src/main/java/org/firstinspires/ftc/teamcode/auto/ package (BozoAuto, BlueAuto/RedAuto, BlueCloseAuto/RedCloseAuto, AutoConfig) — covers the alliance-pair symmetry convention and how to check whether a commit's changes are already applied before assuming work remains."
---

## Package layout

`TeamCode/src/main/java/org/firstinspires/ftc/teamcode/auto/`:
- `BozoAuto.java` — shared abstract base OpMode; owns the `State` enum, `pastState`-driven `autoPathUpdate()` state machine, and `buildPaths()`. Both alliances share this file.
- `BlueAuto.java` / `RedAuto.java` — alliance-specific abstract subclasses of `BozoAuto`. They declare the `Pose` fields (`startPose`, `shootLeftPose`, `shootRightPose`, `flowerLeftPose`, `flowerRightPose`, `endPose`) and implement `buildConfig()` returning an `AutoConfig`. These two files are edited **in lockstep** — any change to one (new field, new pose, new config param) must be mirrored in the other.
- `BlueCloseAuto.java` / `RedCloseAuto.java` — concrete `@Autonomous`-annotated leaf classes, one per alliance, each extending the alliance's `*Auto` base and overriding `getStartPose()`. `group` and `preselectTeleOp` follow the alliance name (`"Blue"`/`"BlueTeleOp"` or `"Red"`/`"RedTeleOp"`).
- `AutoConfig.java` — plain data holder for the pose set passed into `buildConfig()`.

## Alliance-pair symmetry convention

Every concrete/leaf auto class comes in a Blue/Red pair with matching structure but different alliance wiring (annotation name/group/preselectTeleOp, and any alliance-specific pose values). When asked to "add" or "apply a pattern to" one alliance, first check whether the counterpart file already exists — a missing pair member (e.g. `BlueCloseAuto` existed with no `RedCloseAuto`) is the most common real gap, not a divergence in `BozoAuto`/`*Auto` base logic which is shared.

## Before assuming a commit's changes still need applying

This repo's `auto/` package has had commits (e.g. `67f06e4` "Movement Auto 1.0 Finished, Missing Pos coordinates") that touched `BlueAuto.java`, `RedAuto.java`, and `BozoAuto.java` together in one commit — meaning Blue/Red already got symmetric treatment simultaneously. If asked to "find commit X and apply it elsewhere," always diff the current file contents against the commit's post-state first (read the file, compare to the commit diff) rather than assuming untouched work remains. If everything in the commit is already present, the real gap is usually a missing sibling leaf class, not a re-application of the base pattern — ask the user to confirm the target rather than guessing a large unrelated change (e.g. don't reach for teleop/ without confirmation).
