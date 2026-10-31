---
name: rebrand-fork-keep-java-package
description: "Rebrand a forked Java/Gradle project (e.g. Grim to StMarksAC) by scripted rename, then optionally move the in-repo Java packages while keeping external-artifact packages and persisted identifiers."
---

## When
User asks to rebrand a whole repo (name, author, commands, perms). Dependencies/external artifacts may share the Java package; first keep it, and if the user later asks, move only the in-repo part (see "Moving the package").

## Procedure (rebrand)
1. Survey: `rg -il <old>`, token histogram (`rg -o --no-filename -i '[A-Za-z0-9_./:-]*old[A-Za-z0-9_./:-]*' | sort | uniq -c | sort -rn`), and `git ls-files | rg -i <old>` for filenames. Use `rg`, not `grep`, for speed (the user requires it).
2. Ask once (single `ask`): package handling, rename commands/perms, exact identifiers (display, author, lowercase id).
3. Write a Python script with a dry-run default and `--apply`. Design:
   - MASK protected spans with placeholders over the WHOLE file first, apply rename rules, then unmask. Protect: package paths and imports, every URL (default-deny `https?://\S+`; do NOT also add partial host allowlists, they shadow the URL rule and split URLs), `stableKey = "old.*"` and DB store names, version-catalog `libs.old.*` and external artifact ids, Gradle convention-plugin ids, LICENSE and upstream copyright.
   - In .java/.kt/.kts rewrite only string literals and comments, never identifiers.
   - Config and message keys referenced from both Java and YAML must be renamed on both sides.
   - Rename resource filenames with `git mv`, and update all references.
   - Put one-off edits (author, fork notice, retargeting repo links) in a `post_fixups` step, not global rules.
4. Test on a scratch copy first (`git init` there, commit with `GIT_ALLOW_SECRETS=1 -c core.hooksPath=/dev/null` because gitleaks flags stableKey strings). Compare invariant counts before and after: package refs, stableKeys, store names, libs.* refs, and per-file URL token lists.
5. Apply to the repo, then run offline Gradle: tests, `shadowJar`, and Fabric `processResources`/`compileJava`.

## Moving the package (in-repo only)
Decide ownership from the SECOND path segment, verified against the real external jars in `~/.gradle/caches/modules-2` (`unzip -Z1 jar | rg '\.class$'`). For Grim: `ac.grim.grimac.api.**` and `.internal.**` are external; everything else moves (note `platform.api` is in-repo, only the 2nd segment counts). Also scan external bytecode for references to in-repo packages; none means the move is safe.
- Rewrite dotted FQNs with a regex that requires a following segment (`(?=\.[A-Za-z_*])`) so the Maven group `"ac.grim.grimac"` (build files, `libs.versions.toml`, `includeGroup`) is never touched. Shade `relocate()` destinations are yours: move them.
- Root-level classes (`pkg.GrimAPI`) are a separate case: the same regex misses their bare `package pkg;` line. Fix declarations explicitly, then check EVERY file: declared package must equal its directory.
- `git mv` the dirs per source root (`common`, `bukkit`, `fabric/*`, tests). Never move third-party-package files that live in your tree (e.g. `net/kyori/...`).
- Slash/path forms are not FQNs and escape the dotted rewrite: tests that read `Path.of("src/main/java/old/pkg/checks")` (VerboseTemplateAuditTest), `cliff.toml` commit_preprocessors. Search `rg 'ac/grim|"ac", *"grim"'` after the move. Leave pre-existing stale cliff entries (engine/config/api) alone.
- Loaded-by-name strings must be rewritten in lockstep: `plugin.yml main` (bukkit-yml plugin block), `fabric.mod.json` entrypoints, mixin json `package`, reflective `HANDLER_CLASS` strings (LuckPerms). Verify each resolves to a real file.
- Verify: invariants (external FQN count unchanged, zero leftover old in-repo FQNs, java file count unchanged), `:common:test`, `:bukkit:shadowJar`, Fabric compile/processResources, then a JVM smoke that `Class.forName`s renamed classes from the built jar (add the cached paper-api jar to the classpath) and asserts the OLD in-repo names no longer resolve. Do not guess class names for that smoke test; list them from the jar.

## Pitfalls found
- Code may build a JVM system-property prefix from the brand (`SystemArgumentFactory.Builder.of("Brand")` gives `-DBrandPlatformOverride`). Update `systemProperty(...)` in build.gradle.kts, or tests fail with "Unknown platform!".
- Renaming both command aliases (`"grim","grimac"`) collapses them into a duplicate `"x","x"`. Give the second a distinct short alias and update any alias checks (e.g. CloudCommandService).
- Env vars and CI user-agents need renaming consistently across workflow, build.gradle.kts and buildSrc.
- Language-specific inflections and CJK adjacency defeat `\b`; use ASCII-letter lookarounds.
- Verify with a throwaway test that registers commands against a real Cloud CommandManager, then delete it.
- Never `grep -r -a` over an extracted jar tree (hangs); use a targeted scan of class names.
- Do not create or push remotes; report that new repo links 404 until the repo exists.
