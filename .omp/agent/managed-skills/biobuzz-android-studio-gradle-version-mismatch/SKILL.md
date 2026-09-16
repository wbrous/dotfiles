---
name: biobuzz-android-studio-gradle-version-mismatch
description: "Use when the St-Marks-Robotics-FTC/Biobuzz (or sibling FTC) repo's Android Studio Gradle sync fails with \"Plugin 'com.android.internal.library' relies on ... a Gradle internal API that was removed in Gradle 9.6.0\", or any AGP-vs-Gradle-version incompatibility error referencing a Gradle version that doesn't match gradle/wrapper/gradle-wrapper.properties — Android Studio's IDE sync can silently use a different (often newer/bundled) Gradle distribution than the project's pinned wrapper version when .idea/gradle.xml lacks an explicit distributionType, or has distributionType=LOCAL pointing at a stale myGradleHome path."
---

## Symptom

`./gradlew` from the CLI works fine, but Android Studio's IDE sync fails with something like:

```
Failed to apply plugin 'com.android.internal.library'.
> ... InternalProblems ...
> Plugin 'com.android.internal.library' relies on 'org.gradle.api.problems.internal.InternalProblems',
  a Gradle internal API that was removed in Gradle 9.6.0.
```

The version named in the error (e.g. 9.6.0/9.7.1) does NOT match `gradle/wrapper/gradle-wrapper.properties` (e.g. 9.1.0). AGP 8.13.2 is not compatible with Gradle >= 9.6.0 (removed internal API), only with the older pinned wrapper version.

## Root cause

`.idea/gradle.xml` controls which Gradle distribution the IDE uses for sync — it does NOT always follow the wrapper. Two failure shapes seen:

1. No `distributionType` set at all → IDE defaults to its own bundled Gradle version.
2. `distributionType=LOCAL` with an explicit `myGradleHome` pointing at a specific local Gradle install dir under `~/.gradle/wrapper/dists/gradle-X.Y.Z-bin/...`. If a *different*, newer Gradle version (e.g. 9.7.1) also happens to be installed on the machine and something causes AS to pick it (or the LOCAL path was previously set incorrectly), sync uses that instead of the wrapper's pinned version.

Confirm the mismatch by checking `~/.gradle/wrapper/dists/` for multiple installed Gradle versions, and comparing `gradle-wrapper.properties`' `distributionUrl` version against the version implicated in the error.

## Fix

Edit `.idea/gradle.xml`: set `distributionType` to `DEFAULT_WRAPPED` and remove any `myGradleHome` override, so the IDE follows the wrapper:

```xml
<GradleProjectSettings>
  <option name="testRunner" value="CHOOSE_PER_TEST" />
  <option name="distributionType" value="DEFAULT_WRAPPED" />
  <option name="externalProjectPath" value="$PROJECT_DIR$" />
  <option name="gradleJvm" value="#GRADLE_LOCAL_JAVA_HOME" />
  <option name="modules">
    <set>
      <option value="$PROJECT_DIR$" />
      <option value="$PROJECT_DIR$/FtcRobotController" />
      <option value="$PROJECT_DIR$/TeamCode" />
    </set>
  </option>
</GradleProjectSettings>
```

(No `myGradleHome` entry.)

## Verify

Do NOT trust IDE re-sync alone as proof — confirm from the CLI first:

```
./gradlew -version                          # confirm resolved Gradle version matches wrapper-properties
./gradlew :FtcRobotController:help          # confirm the plugin applies / project evaluates, BUILD SUCCESSFUL
```

Then re-sync in Android Studio (File → Sync Project with Gradle Files) to pick up the `.idea/gradle.xml` change.
