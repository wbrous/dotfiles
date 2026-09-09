---
name: pedropathing-ivy-scheduler-missing-dependency
description: "Use when an FTC TeamCode project's ExampleAuto (or similar) copied from the Pedro Pathing \"Example Auto\" docs (pedropathing.com/docs/pathing/examples/auto) shows unresolved symbols like \"Cannot resolve symbol 'ivy'\", \"Cannot resolve symbol 'Scheduler'\", \"Cannot resolve method 'sequential'/'follow'\" for com.pedropathing.ivy.* imports (Scheduler, Command, PedroCommands, Groups) — the pedropathing:ftc core dependency does not include Ivy, the separate command library, which must be added explicitly. If the user does not want the extra Ivy dependency, refactor to the docs' Finite State Machine (FSM) alternative instead."
---

## Root cause

The official Pedro Pathing "Example Auto" docs (pedropathing.com/docs/pathing/examples/auto) show autonomous code built on **Ivy**, a separate command-based control-flow library, via:

```java
import com.pedropathing.ivy.Command;
import com.pedropathing.ivy.Scheduler;
import static com.pedropathing.ivy.Scheduler.*;
import static com.pedropathing.ivy.pedro.PedroCommands.*;
import static com.pedropathing.ivy.groups.Groups.*;
```

`com.pedropathing:ftc` (the core pathing dependency, e.g. `2.1.2`) does **not** bundle Ivy. If a project's `build.dependencies.gradle` only has:

```groovy
implementation 'com.pedropathing:ftc:2.1.2'
```

then `com.pedropathing.ivy.*` symbols (`Scheduler`, `Command`, `PedroCommands`, `Groups`, and the static `sequential`/`follow` methods) are all unresolved.

## Option A: add Ivy (if the team wants command-based autos)

In `build.dependencies.gradle`:

```groovy
implementation 'com.pedropathing:ivy:1.0.0'
```

Verified published on Maven Central (`https://repo1.maven.org/maven2/com/pedropathing/ivy/1.0.0/ivy-1.0.0.pom` → HTTP 200). Then the docs' imports above resolve as written, plus `import com.pedropathing.ivy.Command;` (needed for `autoRoutine()`'s return type — the docs snippet includes it, don't drop it).

## Option B (preferred when the team wants to avoid the extra dependency): refactor to the FSM alternative

The same docs page has a no-Ivy alternative using a manual finite state machine. No extra Gradle dependency needed — only `com.pedropathing.util.Timer` from the existing `com.pedropathing:ftc` artifact.

Key structural changes vs. the Ivy version:
- Drop all `com.pedropathing.ivy.*` imports and the `Command`-returning `autoRoutine()` method.
- Add `private Timer pathTimer, opmodeTimer;` and `private int pathState;` fields.
- Replace the command composition with `autonomousPathUpdate()`: a `switch (pathState)` where each case calls `follower.followPath(chain[, holdEnd])` once, then on `!follower.isBusy()` advances to the next case via `setPathState(n)`. Final case sets `setPathState(-1)` to stop.
- Add a `setPathState(int pState)` helper that sets `pathState` and calls `pathTimer.resetTimer()`.
- In `runOpMode()`: construct `pathTimer`/`opmodeTimer`, reset `opmodeTimer` before `waitForStart()`, after `waitForStart()` reset it again and call `setPathState(0)`, then in the loop call `follower.update(); autonomousPathUpdate();` (no `Scheduler.execute()`) and add `telemetry.addData("path state", pathState)`.

This mirrors the Ivy version's `follow(follower, chain, true)` calls exactly — the `true` argument in `follower.followPath(chain, true)` is the FSM equivalent of Ivy's hold-end-point behavior.

## Verifying either fix

This repo's Gradle/AGP toolchain may not compile locally if the only JDK installed is newer than Gradle supports (e.g. JDK 26 → "Unsupported class file major version 70" on Gradle 9.1.0). That's an unrelated environment issue — verify dependency existence via `curl -sI` against Maven Central instead of a full local build, and note that Android Studio's bundled JDK (17/21) will build fine.
