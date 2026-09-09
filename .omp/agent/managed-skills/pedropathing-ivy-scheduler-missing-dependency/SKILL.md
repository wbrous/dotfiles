---
name: pedropathing-ivy-scheduler-missing-dependency
description: "Use when an FTC TeamCode project's ExampleAuto (or similar) copied from the Pedro Pathing \"Example Auto\" docs (pedropathing.com/docs/pathing/examples/auto) shows unresolved symbols like \"Cannot resolve symbol 'ivy'\", \"Cannot resolve symbol 'Scheduler'\", \"Cannot resolve method 'sequential'/'follow'\" for com.pedropathing.ivy.* imports (Scheduler, Command, PedroCommands, Groups) — the pedropathing:ftc core dependency does not include Ivy, the separate command library, which must be added explicitly."
---

## Symptom
Copying the Pedro Pathing docs example (https://pedropathing.com/docs/pathing/examples/auto) into
`TeamCode/src/main/java/.../ExampleAuto.java` gives unresolved-symbol errors for anything under
`com.pedropathing.ivy` (`Scheduler`, `Command`, static `sequential`/`follow` from `PedroCommands`/`Groups`),
even though `com.pedropathing:ftc:<version>` is already declared in `build.dependencies.gradle`.

## Root cause
Ivy (the command-based control-flow library) is a **separate Maven artifact** from Pedro Pathing core.
`com.pedropathing:ftc` does NOT transitively pull it in.

## Fix
1. In `build.dependencies.gradle`, add alongside the existing pedropathing deps:
   ```gradle
   implementation 'com.pedropathing:ivy:1.0.0'
   ```
   (verify current version at https://pedropathing.com/docs/ivy — install page always has the latest).
2. In the auto OpMode file, add the missing import (the docs list it but it's easy to drop when
   copy-pasting piecemeal):
   ```java
   import com.pedropathing.ivy.Command;
   import com.pedropathing.ivy.Scheduler;
   import static com.pedropathing.ivy.Scheduler.*;
   import static com.pedropathing.ivy.pedro.PedroCommands.*;
   import static com.pedropathing.ivy.groups.Groups.*;
   ```
   `Command` is the return type of the routine-building method (e.g. `autoRoutine()`); it's commonly
   missed since `Scheduler` gets remembered but `Command` doesn't.
3. Sync Gradle (Android Studio: File → Sync Project with Gradle Files, or bundled JDK 17/21 gradlew).

## Verifying the artifact exists (when gradlew can't run in the sandbox)
This machine may only have a JDK too new for the project's Gradle/AGP (e.g. JDK 26 vs Gradle 9.1 →
"Unsupported class file major version 70" evaluating `FtcRobotController/build.gradle`). That's an
unrelated toolchain issue, not a dependency problem. Confirm the Maven artifact resolves independently:
```bash
curl -sI https://repo1.maven.org/maven2/com/pedropathing/ivy/1.0.0/ivy-1.0.0.pom | head -5
# HTTP/2 200 confirms it's published on Maven Central
```
Report that full compile verification wasn't possible due to JDK mismatch, rather than claiming a
Gradle build succeeded when it didn't.
