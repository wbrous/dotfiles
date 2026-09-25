---
name: biobuzz-ftc-subsys-package-conventions
description: "Adding new FTC subsystem classes under teamcode/subsys (motors/servos); shows style, PIDF reuse, state enums, hardwareMap naming."
---

## Context
Repo: Biobuzz FTC robot, `TeamCode/src/main/java/org/firstinspires/ftc/teamcode/subsys/`.
Existing subsystems: `PIDF.java` (general PIDF controller, already implemented), `Flywheel.java`, `Intake.java`, `Transfer.java`.

## Conventions observed
- Minimal comments: one-line intent comments only where non-obvious (e.g. `// tune once flywheel is mounted`, `// call every loop to drive ... towards targetRPM via PIDF`). No large doc blocks in subsys classes (unlike `Robot.java` which has a one-line file-summary comment at the very top).
- Package: `org.firstinspires.ftc.teamcode.subsys;` — no blank-then-comment header needed.
- Constructor takes `HardwareMap hw` and pulls the device via `hw.get(Type.class, "deviceName")` where `deviceName` matches the lowercase subsystem name (`"flywheel"`, `"intake"`, `"transfer"`).
- Motors: use `DcMotor` for simple on/off/reverse subsystems (Intake), `DcMotorEx` when closed-loop velocity control is needed (Flywheel, via `motor.getVelocity()` in ticks/sec).
- State exposed via a public `enum State {...}` nested in the subsystem class, with a private `state` field and a `getState()` accessor. Setter methods (`open()/close()`, `forward()/reverse()/off()`) both mutate `state` and command hardware in one call — no separate "apply" step.
- Servos: placeholder open/closed positions as `private static final double OPEN_POSITION/CLOSED_POSITION` with a `// placeholder positions, tune once the servo is mounted` comment; constructor calls `close()` to set a known initial state.
- PIDF-driven subsystems reuse the existing `subsys/PIDF.java` class (`new PIDF(kP, kI, kD, kF)`, `.calc(target, current)`) rather than writing a new controller. Gains are seeded at 0 with a `// tune once X is mounted` comment; an `update()` method (called every loop by the caller) computes and applies `motor.setPower(pidf.calc(target, current))`.
- Verification: `./gradlew :TeamCode:compileDebugJavaWithJavac -q` to confirm new subsys classes compile (fast, ~10s); no unit-test harness exists for subsys classes in this repo.

## Gotcha
The `edit` tool's `PUT` line-range anchoring can reject edits on files it hasn't fully displayed (e.g. after a truncated/partial read). For brand-new near-empty stub files, prefer `write` (full-file overwrite) over `edit` to avoid anchor-mismatch errors.
