---
name: maven-build-without-system-mvn-intellij-bundled
description: "mvn not found on Omarchy/Arch; build Maven/Kotlin Paper plugin using IntelliJ's bundled Maven; verify jar contents."
---

# Building a Maven project when `mvn` is not installed

Symptom: `mvn: command not found`; `mise which mvn` says "not a mise bin"; no `~/.m2/wrapper`, no `mvnw`.

## Fix
IntelliJ (JetBrains Toolbox) bundles Maven. Locate and use it:

```bash
find / -type f -name mvn -path '*bin*' 2>/dev/null
# e.g. /home/wils/.local/share/JetBrains/Toolbox/apps/intellij-idea/plugins/maven-plugin/lib/maven3/bin/mvn
MVN=<path from above>
$MVN -q clean package
```

Do not try to install Maven system-wide unless asked. Searching `/` can take long; the shell may background it, so wait for the result.

## Verify the jar (do not trust exit code alone)
```bash
unzip -p target/<artifact>.jar paper-plugin.yml     # resource filtering applied?
unzip -Z1 target/<artifact>.jar | grep -i <package>  # expected classes present?
```
Resource filtering only replaces `${prop}` (with braces); `$prop` stays literal.

## Gotcha: Java sources silently skipped (Kotlin Paper plugin template)
If `pom.xml` sets `<sourceDirectory>src/main/kotlin</sourceDirectory>` and only `kotlin-maven-plugin` compiles, files under `src/main/java` (e.g. a `PluginLoader` Java class) are NOT compiled. The build succeeds, but `paper-plugin.yml` `loader:` points at a class missing from the jar. Check for it after any rename/refactor; fix by porting to Kotlin, dropping `loader:`, or configuring the compiler plugin for Java sources.

## Renaming a plugin (package + classes)
Use `git mv` for dirs and files (keeps history), edit package/class lines, then update `paper-plugin.yml` (`name`, `prefix`, `main`, `bootstrapper`, `loader`, `website`) and `pom.xml` (`artifactId`, `name`). Grep case-insensitively for the old name in `src` and `pom.xml`; `.idea/`, `*.iml`, `target/`, `dependency-reduced-pom.xml` are gitignored and regenerate.
