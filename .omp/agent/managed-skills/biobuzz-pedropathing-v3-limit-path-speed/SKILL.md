---
name: biobuzz-pedropathing-v3-limit-path-speed
description: When capping or slowing speed during a Pedro Pathing v3 path in Biobuzz autos; read the user-preference warning before adding any speed limiter.
---

# Limiting path speed in Pedro Pathing v3 (Biobuzz)

## User preference (read first)
In BozoAuto the user rejected every speed-limiting attempt: a linear slowdown helper, then a one-shot cap, both of which edited `Constants.foresightConfig.maxPathSpeed`. Their words: make it as SIMPLE as possible, "none of this constants editing stuff", KISS. The final state was NO slowdown. Do not re-add global-config edits, helper functions, new Tunables, or per-loop limiters unprompted. If asked again, ask which approach they want before writing code, and keep it to a few lines.

## Verified API facts (core 3.0.0, from javap)
- `Follower` has no `setMaxPower`. It has `follow`, `hold`, `manual(DrivePowers)`, `isBusy`, `remainingDistance()`, `pose()`.
- Speed limits live in `ForesightConfig` (shared static `Constants.foresightConfig` in Biobuzz): `maxPathSpeed`, `maxVelocityConstraint`, etc. are `ConfigVar<Double>`, default `ForesightConfig.Constraint.NONE` (Infinity), validated positive, so 0 is rejected.
- `maxPathSpeed` is read inside `Foresight.coast`, multiplied by a velocity term (appears to be a fraction). Not run on a robot, so treat as unconfirmed.
- Because the config is a shared static, any change persists across OpModes unless reset in init/stop.

## Other lessons
- `HEAD` may already contain your earlier edits (user ran a formatter commit); diff against HEAD before assuming a clean baseline.
- When using multi-op edits, line numbers shift between ops; re-read the file after each batch.
- Don't run filesystem-wide `find` in bash; it backgrounds for 300s.
