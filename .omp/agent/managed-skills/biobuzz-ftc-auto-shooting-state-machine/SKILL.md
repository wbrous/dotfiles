---
name: biobuzz-ftc-auto-shooting-state-machine
description: "Porting/adapting shooting sequences into BozoAuto.java (flywheel spin-up, margin gate, transfer/intake feed timing); not teleop aiming."
---

## Context

This repo's autonomous OpModes extend `TeamCode/.../auto/BozoAuto.java`, a Pedro Pathing state-machine `OpMode`. The robot here is simpler than the upstream `St-Marks-Robotics-FTC/Decode` reference repo: only `Robot.flywheel` (subsys/Flywheel.java), `Robot.intake` (subsys/Intake.java), `Robot.transfer` (subsys/Transfer.java) exist — no turret, no vision-based artifact pattern, no `LaunchSetpoints`. Do not copy turret/vision/pattern logic from the reference repo; it doesn't apply here.

## Reference source

`St-Marks-Robotics-FTC/Decode` repo, `TeamCode/.../auto/BozoAuto.java` has a much more elaborate FSM (START, TRAVEL_TO_LAUNCH, START_LAUNCH_1/2, LAUNCH, TRAVEL_TO_BALLS, RELOAD, GO_TO_TURN, TURN, GO_TO_CLEAR, CLEAR, GO_TO_END, END) built around a `Vision`-detected ball pattern and turret. The reusable *idea* to steal is the spin-up/margin-gate/feed-timer sequencing, not the literal states.

## Pattern that maps onto this simpler robot

1. Set `robot.flywheel.setRPM(Tunables.shootRPM)` as soon as you start driving toward the shoot pose — spin up during travel, not after arriving.
2. Add `Flywheel.isWithinMargin()`: `targetRPM > 0 && Math.abs(getRPM() - targetRPM) <= Tunables.flywheelRPMMargin`. Guard against `targetRPM == 0` so an idle flywheel never reports "within margin".
3. Once `!follower.isBusy()` at the shoot pose, wait in a dedicated `SPIN_UP` state until `isWithinMargin()` — don't feed early.
4. On margin achieved: `robot.transfer.open()` + `robot.intake.forward()`, transition to `FEED`, and gate on `stateTimer.get(TimeUnit.MILLISECONDS) >= Tunables.feedDurationMillis` (there's no ball-count sensor in this hardware, so timing is the only gate available — don't invent a sensor that doesn't exist).
5. After feed timeout: `robot.transfer.close()`, `robot.intake.off()`, `robot.flywheel.setRPM(0)`, increment a `shotsCompleted` counter, then branch to either the refuel leg or the end pose based on a `TOTAL_SHOTS` constant.
6. Refuel leg: drive to refuel pose, run intake forward for `Tunables.refuelDurationMillis`, then drive back and re-spin the flywheel on the way.
7. `Robot` has no aggregate `update()`/`launch()` convenience methods — call `robot.flywheel.update()` explicitly every `loop()` (it wasn't being called before this change, which silently meant the flywheel PIDF never applied power).

## Tunables added

`Tunables.java`: `shootRPM`, `flywheelRPMMargin`, `feedDurationMillis`, `refuelDurationMillis` (all `public static`, no `@Configurable` per-field annotation needed — the class itself is `@Configurable`).

## Verification

No physical hardware available in this environment — verification is `./gradlew :TeamCode:compileDebugJavaWithJavac -q` only. That confirms API/type correctness, not on-robot timing or RPM tuning; flag that gap explicitly rather than claiming a smoke test that didn't happen.
