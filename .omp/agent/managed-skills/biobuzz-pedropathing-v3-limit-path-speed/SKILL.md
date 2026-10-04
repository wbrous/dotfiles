---
name: biobuzz-pedropathing-v3-limit-path-speed
description: When capping speed during Pedro Pathing v3 path without setMaxPower
---

# Limiting path speed in Pedro Pathing v3 (core 3.0.0)

`Follower` has no `setMaxPower`. Speed is limited via the shared static config in `pedro/Constants.java`:

```java
Constants.foresightConfig.maxPathSpeed.set(0.4);                          // cap
Constants.foresightConfig.maxPathSpeed.set(ForesightConfig.Constraint.NONE); // unlimited (Infinity, the default)
```

Import `com.pedropathing.algorithm.ForesightConfig`.

## Facts (from javap of core-3.0.0.jar, not observed on robot)
- `maxPathSpeed` is `ConfigVar<Double>` with a `positive` validator, so 0 is rejected; use a small positive value.
- `Foresight.coast` reads it every update and applies `min(v, maxPathSpeed * someVelocity)`, so it behaves as a fraction of max velocity, and changes mid-path should take effect. This is inferred; confirm on the field.
- It is a shared static: reset to `NONE` in `init()`, otherwise a limit leaks into the next run.
- `follower.remainingDistance()` exists if a distance-based ramp is ever wanted.

## User preference
Keep it simple: set the cap once when starting the slow leg (e.g. on entering TRAVEL_TO_REFUEL from the intermediate pose), restore `NONE` when the leg's state ends. User explicitly rejected a per-loop linear slowdown helper. Put the value in `Tunables` (e.g. `refuelMaxPathSpeed`).

## Compile check without a robot
`./gradlew --offline :TeamCode:compileDebugJavaWithJavac -q` (~2s). BozoAuto can't be loaded standalone (needs FTC SDK), so test pure math in a separate scratch class.
