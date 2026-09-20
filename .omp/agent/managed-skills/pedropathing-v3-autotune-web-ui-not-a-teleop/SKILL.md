---
name: pedropathing-v3-autotune-web-ui-not-a-teleop
description: "Use when a PedroPathing v3 (com.pedropathing:tuning) project's @Tuner-annotated procedures (e.g. pinpointTuner, foresightTuner in a Tuning.java class) don't appear in the Driver Station's TeleOp/Autonomous OpMode list — they are never registered as OpModes. Also covers verifying the com.pedropathing:tuning:1.0.0 dependency and its port."
---

## The tuning web UI is NOT a Driver Station OpMode

PedroPathing v3's AutoTune system (`com.pedropathing:tuning:1.0.0`) does not register
any `@TeleOp`/`@Autonomous` OpMode. It will never show up in the DS OpMode list, no
matter how many `@Tuner`-annotated static methods you add.

### How it actually works (traced from the tuning-1.0.0-sources.jar)

- `Tuning.java` (or wherever you put them) has static methods annotated `@Tuner`
  returning `Procedure`, e.g.:
  ```java
  @Tuner
  public static Procedure foresightTuner() { return new ForesightTuner(...); }
  ```
- `TunerScanner` (a `dev.frozenmilk.sinister.Scanner`) scans all classes at RC app
  boot for these `@Tuner` methods and registers each `Procedure` by name via
  `TunerRegistrar`.
- `Hooks.java` registers an `OnCreateEventLoop` app hook (Sinister SDK app-hooks
  mechanism) that starts a `WebServer` (NanoHTTPD) bound to **port 10158** as soon
  as the Robot Controller app finishes booting — independent of any OpMode
  selection.
- The web server serves a browser UI listing all registered `@Tuner` procedures.
  Selecting/running one there drives the robot via the RC app's internal
  `OpModeManagerImpl`, but the procedure itself is never a DS-selectable OpMode.

### How to actually reach it

1. Deploy the app and let the RC app fully boot on the Control/Driver Hub.
2. Find the hub's WiFi IP (Program & Manage page, or DS connection screen).
   Typical Control Hub AP address: `192.168.43.1`. Different if in Station/Client
   mode.
3. On a device on the same robot WiFi network, browse to
   `http://<hub-ip>:10158`.
4. Registered `@Tuner` procedures appear there; run/select from the browser.

### Debugging "nothing shows up"

- Confirm `implementation 'com.pedropathing:tuning:1.0.0'` is present in the
  Gradle deps (alongside `com.pedropathing:revhub:3.0.0`) — check
  `build.dependencies.gradle` / `TeamCode/build.gradle`.
- If the URL is unreachable (connection refused/timeout), the Sinister
  `OnCreateEventLoop` hook never fired — usually means the RC app crashed or
  never finished booting, not that the tuner setup is wrong. Check
  `adb logcat` / the RC app's on-device log viewer for a crash right after
  launch (e.g. a stale/conflicting `com.pedropathing:ftc:2.1.2` transitive
  dependency causing a dex-level crash — see
  biobuzz-pedropathing-v3-follower-stub-and-agp-compilesdk skill).
- Don't waste time looking for the tuner in the DS TeleOp dropdown — by design
  it will never be there.
