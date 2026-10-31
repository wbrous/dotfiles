---
name: rebrand-fork-keep-java-package
description: Rebrand a forked Java/Gradle project (e.g. Grim to StMarksAC) by scripted rename while keeping the Java package and persisted identifiers.
---

## When
User asks to rebrand a whole repo (name, author, commands, perms) but dependencies or external artifacts share the Java package, so the package stays.

## Procedure
1. Survey: `git grep -i -l <old>`, token histogram (`git grep -h -i -o -E '[A-Za-z0-9_./:-]*old[A-Za-z0-9_./:-]*' | sort | uniq -c`), and `git ls-files | grep -i <old>` for filenames.
2. Ask once (single `ask`): package handling, rename commands/perms, exact identifiers (display, author, lowercase id).
3. Write a Python script with a dry-run default and `--apply`. Design:
   - MASK protected spans with placeholders over the WHOLE file first, apply rename rules, then unmask. Protect: package paths and imports, every URL (default-deny `https?://\S+`; do NOT also add partial host allowlists, they shadow the URL rule and split URLs), `stableKey = "old.*"` and DB store names, version-catalog `libs.old.*` and external artifact ids, Gradle convention-plugin ids, LICENSE and upstream copyright.
   - In .java/.kt/.kts rewrite only string literals and comments, never identifiers.
   - Config and message keys referenced from both Java and YAML must be renamed on both sides.
   - Rename resource filenames with `git mv`, and update all references.
   - Put one-off edits (author, fork notice, retargeting repo links) in a `post_fixups` step, not global rules.
4. Test on a scratch copy first (`git init` there, commit with `GIT_ALLOW_SECRETS=1 -c core.hooksPath=/dev/null` because gitleaks flags stableKey strings). Compare invariant counts before and after: package refs, stableKeys, store names, libs.* refs, and per-file URL token lists.
5. Apply to the repo, then run offline Gradle: tests, `shadowJar`, and Fabric `processResources`/`compileJava`.

## Pitfalls found
- Code may build a JVM system-property prefix from the brand (`SystemArgumentFactory.Builder.of("Brand")` gives `-DBrandPlatformOverride`). Update `systemProperty(...)` in build.gradle.kts, or tests fail with "Unknown platform!".
- Renaming both command aliases (`"grim","grimac"`) collapses them into a duplicate `"x","x"`. Give the second a distinct short alias and update any alias checks (e.g. CloudCommandService).
- Env vars and CI user-agents need renaming consistently across workflow, build.gradle.kts and buildSrc.
- Language-specific inflections and CJK adjacency defeat `\b`; use ASCII-letter lookarounds.
- Verify with a throwaway test that registers commands against a real Cloud CommandManager, then delete it.
- Do not create or push remotes; report that new repo links 404 until the repo exists.
