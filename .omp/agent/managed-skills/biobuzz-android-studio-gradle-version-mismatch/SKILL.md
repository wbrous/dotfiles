---
name: biobuzz-android-studio-gradle-version-mismatch
description: "Use when the St-Marks-Robotics-FTC/Biobuzz (or sibling FTC) repo's Android Studio Gradle sync fails with \"Plugin 'com.android.internal.library' relies on ... a Gradle internal API that was removed in Gradle 9.6.0\", or any AGP-vs-Gradle-version incompatibility error referencing a Gradle version that doesn't match gradle/wrapper/gradle-wrapper.properties — Android Studio's IDE sync can silently use a different (often newer/bundled) Gradle distribution than the project's pinned wrapper version when .idea/gradle.xml lacks an explicit distributionType."
---

## Symptom

`./gradlew` (terminal) builds fine, but Android Studio's Gradle sync fails with an error like:

```
Failed to apply plugin 'com.android.internal.library'.
...
Plugin 'com.android.internal.library' relies on 'org.gradle.api.problems.internal.InternalProblems',
a Gradle internal API that was removed in Gradle 9.6.0. ... refer to
https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#agp_8x_incompatible
```

The Gradle version number embedded in that docs URL (e.g. `9.7.1`) is `GradleVersion.current()` at
the time of the failing build — i.e. the *actual* Gradle version the IDE used, which can differ from
`gradle/wrapper/gradle-wrapper.properties`.

## Root cause

AGP has a supported Gradle version ceiling (e.g. AGP 8.13.2 breaks on Gradle >= 9.6.0 because a
plugin-internal API it depends on, `InternalProblems`, was removed). The project's
`gradle-wrapper.properties` may already correctly pin a compatible Gradle version (verify with
`./gradlew --version` — it should print the pinned version, not the one in the IDE error).

If `.idea/gradle.xml`'s `GradleProjectSettings` block has no explicit `distributionType` option,
Android Studio can fall back to a different (bundled/local) Gradle distribution for IDE sync instead
of honoring the wrapper — causing this exact "wrapper works, IDE sync fails on a newer Gradle"
split-brain symptom.

## Fix

1. Confirm the wrapper itself is fine: `./gradlew --version` and a real task
   (`./gradlew :FtcRobotController:tasks --dry-run`) should succeed using the wrapper's pinned version.
2. Add `<option name="distributionType" value="DEFAULT_WRAPPED" />` inside the
   `<GradleProjectSettings>` block in `.idea/gradle.xml`, right after `gradleJvm`, e.g.:
   ```xml
   <GradleProjectSettings>
     <option name="testRunner" value="CHOOSE_PER_TEST" />
     <option name="externalProjectPath" value="$PROJECT_DIR$" />
     <option name="gradleJvm" value="#GRADLE_LOCAL_JAVA_HOME" />
     <option name="distributionType" value="DEFAULT_WRAPPED" />
     ...
   </GradleProjectSettings>
   ```
3. Tell the user to **File → Sync Project with Gradle Files** (or restart Android Studio).
4. If it still uses a newer Gradle after resync, the IDE has a manual per-project override at
   **Settings → Build, Execution, Deployment → Build Tools → Gradle** — the "Distribution" dropdown
   may be set to "Local Gradle Distribution"; switch it to
   **"Use Gradle from: 'gradle-wrapper.properties' file"**.

This is an IDE-config fix, not a build-file fix — don't touch `build.gradle`/AGP version/
`compileSdk` for this symptom unless the wrapper build itself also fails.
