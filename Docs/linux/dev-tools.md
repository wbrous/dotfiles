# Dev Tools on Arch (Flutter, Maven)

Flutter SDK install without sudo; Maven builds via IntelliJ's bundled copy.

## Install Flutter SDK and scaffold an app (no sudo)

**Symptom:** `flutter` missing on Arch/Omarchy — not in official pacman repos (only `fvm`, needs sudo); `yay -Ss flutter` returns unrelated AUR apps; `sudo -n` fails.

**Fix:**
```sh
git clone --depth 1 -b stable https://github.com/flutter/flutter.git ~/development/flutter
export PATH="$HOME/development/flutter/bin:$PATH"   # per command; PATH is not persisted
flutter create --platforms=android,ios --org <org> --project-name <name> .
# first run downloads the Dart SDK (~60s); project names must be valid Dart identifiers
flutter analyze && flutter test   # template includes a counter widget test
```
Tell the user to add the PATH export to shell config. `flutter doctor` lists missing pieces: iOS builds need macOS+Xcode, Android builds need the Android SDK. Ask about platforms and app scope before scaffolding — don't assume defaults.

_Migrated from: flutter-arch-sdk-install-and-create_

## Build a Maven project with IntelliJ's bundled Maven

**Symptom:** `mvn: command not found`; `mise which mvn` says "not a mise bin"; no `~/.m2/wrapper`, no `mvnw`.

**Fix:** IntelliJ (JetBrains Toolbox) bundles Maven — locate and use it, don't install system-wide unasked:
```bash
find / -type f -name mvn -path '*bin*' 2>/dev/null
# e.g. /home/wils/.local/share/JetBrains/Toolbox/apps/intellij-idea/plugins/maven-plugin/lib/maven3/bin/mvn
MVN=<path from above>
$MVN -q clean package
```

**Verify the jar (don't trust exit code alone):**
```bash
unzip -p target/<artifact>.jar paper-plugin.yml     # resource filtering applied?
unzip -Z1 target/<artifact>.jar | grep -i <package>  # expected classes present?
```
Resource filtering only replaces `${prop}` (with braces); `$prop` stays literal.

**Gotcha — Java sources silently skipped (Kotlin Paper plugin template):** if `pom.xml` sets `<sourceDirectory>src/main/kotlin</sourceDirectory>` and only `kotlin-maven-plugin` compiles, files under `src/main/java` (e.g. a `PluginLoader`) are NOT compiled — build succeeds but `paper-plugin.yml` `loader:` points at a class missing from the jar. Check after any rename/refactor; fix by porting to Kotlin, dropping `loader:`, or configuring the compiler plugin for Java sources.

**Renaming a plugin:** `git mv` dirs/files (keeps history), edit package/class lines, update `paper-plugin.yml` (`name`, `prefix`, `main`, `bootstrapper`, `loader`, `website`) and `pom.xml` (`artifactId`, `name`). Grep case-insensitively for the old name in `src` and `pom.xml`; `.idea/`, `*.iml`, `target/`, `dependency-reduced-pom.xml` are gitignored and regenerate.

_Migrated from: maven-build-without-system-mvn-intellij-bundled_
