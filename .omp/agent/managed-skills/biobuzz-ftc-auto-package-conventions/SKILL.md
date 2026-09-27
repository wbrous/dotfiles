---
name: biobuzz-ftc-auto-package-conventions
description: "Use for teamcode/auto OpModes: BozoAuto, Blue/RedAuto, Close, AutoConfig, PedroPathing, NPEs; not TeleOp."
---

## AutoConfig contract (current)

`AutoConfig` (org.firstinspires.ftc.teamcode.auto) holds exactly these `Pose` fields, in this
constructor order:

```
AutoConfig(Pose startPose, Pose shootRightPose, Pose refuelPose, Pose endPose)
```

- Only **one** shoot pose exists: `shootRightPose`. Do not reintroduce `shootLeftPose` or
  flower-pickup poses (`flowerLeftPose`/`flowerRightPose`) — those were removed when the auto
  was simplified to a shoot → refuel → shoot → end cycle.
- "Refuel" means drive to `refuelPose` to pick up game elements, then return to `shootRightPose`
  to score. It replaced the old two-flower/two-pickup routine.

## BozoAuto state machine (base class)

`BozoAuto` (abstract OpMode all color autos extend) drives a 4-state cycle:

```
START → SHOOTING (shoot) → REFUELING (refuel) → SHOOTING (shoot) → END
```

Paths: `path1` start→shootRight, `path2` shootRight→refuel, `path3` refuel→shootRight,
`path4` shootRight→end. `pastState` disambiguates which branch of `SHOOTING` to take
(came from START vs came from REFUELING).

## Color auto subclasses (BlueAuto / RedAuto)

Each color subclass (`BlueAuto`, `RedAuto`) is a `@Configurable` abstract class exposing
public static `Pose` fields matching the `AutoConfig` contract exactly:
`startPose`, `shootRightPose`, `refuelPose`, `endPose`, and a `buildConfig()` override
constructing `new AutoConfig(startPose, shootRightPose, refuelPose, endPose)`.

Concrete OpModes (`BlueCloseAuto`, `RedCloseAuto`, etc.) extend the color class and only
override `getStartPose()` — they never touch the pose fields above.

When adding/repairing a color auto: mirror poses about field center `(72, 72)` with a
180° heading offset if the exact real-world value isn't specified (`(x,y,θ) →
(144-x, 144-y, θ+180°)`). Flag any such derived value as `[INFERENCE]` — it needs on-field
verification, not just "makes sense" reasoning.

## Common breakage pattern to watch for

Older/red-side files in this package have historically had: missing semicolons, stale field
names left over from the two-flower design, and constructor argument order mismatches with
`AutoConfig`. When touching any `*Auto.java` in this package, read `AutoConfig.java` first to
confirm the current field set/order before assuming the file compiles.
