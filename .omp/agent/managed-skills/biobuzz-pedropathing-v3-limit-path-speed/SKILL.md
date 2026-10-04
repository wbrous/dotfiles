---
name: biobuzz-pedropathing-v3-limit-path-speed
description: "Slow or cap robot speed during a Pedro Pathing v3 (core 3.0.0, Foresight) path in Biobuzz autos; no Follower.setMaxPower exists."
---

# Limiting follower speed in Pedro Pathing v3 (Biobuzz)

## Facts (from javap of core-3.0.0.jar; NOT yet confirmed on a real robot)
- v3 `Follower` has NO `setMaxPower`. Useful methods: `remainingDistance()`, `isBusy()`, `pose()`, `follow(Path)`.
- Speed limit = `ForesightConfig.maxPathSpeed` (`ConfigVar<Double>`, default `ForesightConfig.Constraint.NONE` = +Infinity, validator `positive()` so 0 is rejected). In `Foresight.coast` it is applied as `min(target, maxPathSpeed * <max velocity term>)`, i.e. treated as a fraction of top speed.
- Biobuzz holds the config as a shared static: `org.firstinspires.ftc.teamcode.pedro.Constants.foresightConfig`. `ConfigVar.set(...)` mutates it live; Foresight reads it each update, so set it BEFORE `follower.update()` in `loop()`.
- `Path.with(Modifier...)` / `ConfigVar.at(v)` exist for per-path scoped values, but runtime-distance-dependent slowdown needs `set()` each loop.

## Recipe (done in auto/BozoAuto.java)
1. Pure helper `speedFraction(remaining, slowdownDist, minFraction)` = `min + (1-min) * clamp(remaining/slowdownDist, 0, 1)`; throw on slowdownDist<=0 or minFraction outside (0,1].
2. `updatePathSpeedLimit()` called before `follower.update()`: in the slow state while `follower.isBusy()` set the fraction from `follower.remainingDistance()`, otherwise set `Constraint.NONE`.
3. Because the config is static, also reset to `NONE` in `init()` and `stop()` so limits don't leak into the next run / TeleOp.
4. Expose distance and min fraction in `Tunables.java`.

## Verification tips
- `./gradlew --offline :TeamCode:compileDebugJavaWithJavac -q` works (~2s incremental); check the class mtime is newer than the source.
- BozoAuto can't be loaded off-robot (needs FTC SDK classpath); test the pure helper by copying it into a standalone class.
- Don't run filesystem-wide `find /` (e.g. for android.jar): it backgrounds for minutes. Don't `wait` on it.
- Jars: ~/.gradle/caches/modules-2/files-2.1/com.pedropathing/core/3.0.0/*/core-3.0.0.jar; inspect with `javap -p -c`.
