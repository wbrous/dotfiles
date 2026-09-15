---
name: biobuzz-gradle-wrapper-agp-version-pinning
description: "Use when the St-Marks-Robotics-FTC/Biobuzz (or sibling Decode) repo's Gradle build fails, hangs, or the robot \"bricks on upload\" after gradle/wrapper/gradle-wrapper.properties was hand-edited — covers finding the FTC-SDK-official Gradle version paired with the repo's pinned AGP version, and the JDK-major-version trap."
---

## Where to look first

`gradle/wrapper/gradle-wrapper.properties`'s `distributionUrl` is a recurring footgun in this
org's FTC repos (Biobuzz, Decode). Team members hand-edit it to "fix builds" without checking
AGP compatibility, and the fix regresses later. Before debugging anything else, `git log -p
--follow -- gradle/wrapper/gradle-wrapper.properties` to see the edit history — the culprit
commit is usually recent, small (1-2 line diff), and often has a suspicious/ironic message like
"This fixed my builds".

## Ground truth for the correct pairing

Don't guess a Gradle version — find what FIRST actually shipped and validated. The
`FtcRobotController vX.Y` merge commits (from `FIRST-Tech-Challenge` upstream, not local edits)
contain the *stock, tested* `gradle-wrapper.properties` alongside the matching AGP version in
`build.gradle` (`com.android.application`/`com.android.library` plugin version). Find the merge
commit for the currently-pinned AGP version and diff its wrapper properties against HEAD:

```
git log --oneline | grep "FtcRobotController v"
git show <merge-sha>:build.gradle | grep "com.android"          # confirms AGP version
git show <merge-sha>:gradle/wrapper/gradle-wrapper.properties    # the known-good wrapper config
```

For AGP 8.13.2 (Biobuzz's current pin, from `FtcRobotController v11.2`), the stock/validated pair
is Gradle **9.1.0** with `validateDistributionUrl=true` and `networkTimeout=10000` — NOT a
version bumped ad hoc to 9.7.1, and NOT downgraded to 8.13 (AGP 8.13.2's bare documented minimum,
zero headroom, and dropped the URL-validation/timeout safety net in the process).

Decode (sibling repo, same org) uses an older, internally-consistent pairing (AGP 8.7.0 + Gradle
8.9) — never independently bumped/downgraded, which is why it "just works". Don't port Decode's
wrapper version into Biobuzz; match the wrapper to whichever AGP version Biobuzz is actually
pinned to.

## The JDK-major-version trap

Restoring the stock Gradle version can still fail on a dev machine with a bleeding-edge default
JDK: Gradle 9.1.0's Groovy layer chokes on JDK 26 with `BUG! exception in phase 'semantic
analysis' ... Unsupported class file major version 70`. This is a local toolchain issue, not a
repo config issue — verify by re-running with `JAVA_HOME=/usr/lib/jvm/java-21-openjdk
./gradlew ...` (or java-17). Android Studio normally sidesteps this by using its own bundled JBR
(17/21), so this only bites when running `gradlew` from a raw shell with a rogue system JDK.

## Fix + verify recipe

1. `git show <merge-sha>:gradle/wrapper/gradle-wrapper.properties` → write that exact content back.
2. `JAVA_HOME=/usr/lib/jvm/java-21-openjdk ./gradlew :TeamCode:assembleDebug` and confirm
   `BUILD SUCCESSFUL` — this is the deliverable proof, not just "it should work now".
3. If the ambient JDK is too new, that's a machine toolchain fix (point JAVA_HOME at 17/21), not
   a repo change — call it out separately rather than bundling it into the wrapper-file fix.
