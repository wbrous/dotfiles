---
name: biobuzz-pedropathing-v3-limit-path-speed
description: When capping speed during Pedro Pathing v3 path without setMaxPower; read user-preference warning first.
---

# Limiting path speed in Pedro Pathing v3 (core 3.0.0)

## User preference (Biobuzz, learned 2026-10-04)
User asked to "slow down linearly approaching refuel" in BozoAuto. Both attempts were rejected and reverted:
1. Per-loop linear ramp via `Constants.foresightConfig.maxPathSpeed.set(...)` with helper + tunables: rejected as overbuilt.
2. One-shot cap before the refuel leg + reset after: also rejected ("none of this constants editing stuff"); user chose to leave the auto with no slowdown.

Do NOT reach for `Constants.foresightConfig` mutation or tunable-heavy ramps here. If asked again, propose the simplest option first and ask; the unexplored alternative is `follower.manual(DrivePowers)` scaled by `follower.remainingDistance()` during the leg.

## Facts (from javap of core-3.0.0.jar, never verified on a robot)
- Follower has no `setMaxPower`. Follower API: `follow`, `hold`, `manual(DrivePowers)`, `isBusy`, `remainingDistance()`, `pose()`.
- `ForesightConfig.maxPathSpeed` (`ConfigVar<Double>`, default `Constraint.NONE` = Infinity, validator positive) is read in `Foresight.coast` and is used as a fraction of current speed bound (`min(v, maxPathSpeed * x)`); `maxVelocityConstraint` is an absolute bound.
- `Constants.foresightConfig` is a shared static, so any set() leaks across OpModes unless reset in init()/stop().
- `Path.with(Modifier...)` plus `ConfigVar.at(value)` gives a per-path scoped modifier (apply/revert), avoiding global mutation; untested.
- Offline compile check: `./gradlew --offline :TeamCode:compileDebugJavaWithJavac -q` (about 2s). BozoAuto cannot be loaded in plain java (needs FTC SDK).
- Pitfall: `git diff` baseline may already contain experimental code if the user's `style:` commit swept it in; check `git diff HEAD`.
