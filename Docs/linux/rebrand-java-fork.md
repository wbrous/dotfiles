# Rebranding a Forked Java/Gradle Project

When rebranding a whole forked repo (name, author, commands, perms). Dependencies/external artifacts may share the Java package — keep it first; move only the in-repo part later if asked.

## Procedure (rebrand)

1. Survey: `rg -il <old>`, token histogram (`rg -o --no-filename -i '[A-Za-z0-9_./:-]*old[A-Za-z0-9_./:-]*' | sort | uniq -c | sort -rn`), `git ls-files | rg -i <old>` for filenames.
2. Ask once: package handling, rename commands/perms, exact identifiers (display, author, lowercase id).
3. Write a Python script with dry-run default and `--apply`:
   - MASK protected spans with placeholders over the WHOLE file first, apply rename rules, unmask. Protect: package paths and imports, every URL (default-deny `https?://\S+` — do NOT add partial host allowlists, they shadow the URL rule and split URLs), `stableKey = "old.*"` and DB store names, version-catalog `libs.old.*` and external artifact ids, Gradle convention-plugin ids, LICENSE and upstream copyright.
   - In `.java`/`.kt`/`.kts` rewrite only string literals and comments, never identifiers.
   - Config and message keys referenced from both Java and YAML must be renamed on both sides.
   - Rename resource filenames with `git mv`, update all references.
   - One-off edits (author, fork notice, retargeting repo links) go in a `post_fixups` step, not global rules.
4. Test on a scratch copy first (`git init` there, commit with `GIT_ALLOW_SECRETS=1 -c core.hooksPath=/dev/null` — gitleaks flags stableKey strings). Compare invariant counts before/after: package refs, stableKeys, store names, `libs.*` refs, per-file URL token lists.
5. Apply, then run offline Gradle: tests, `shadowJar`, Fabric `processResources`/`compileJava`.

## Moving the package (in-repo only)

Decide ownership from the SECOND path segment, verified against the real external jars in `~/.gradle/caches/modules-2` (`unzip -Z1 jar | rg '\.class$'`). Example: `ac.grim.grimac.api.**` and `.internal.**` are external; everything else moves (note `platform.api` is in-repo — only the 2nd segment counts). Scan external bytecode for references to in-repo packages; none means the move is safe.

- Rewrite dotted FQNs with a regex requiring a following segment (`(?=\.[A-Za-z_*])`) so the Maven group `"ac.grim.grimac"` (build files, `libs.versions.toml`, `includeGroup`) is never touched. Shade `relocate()` destinations are yours: move them.
- Root-level classes (`pkg.GrimAPI`): the same regex misses bare `package pkg;` — fix declarations explicitly, then check EVERY file: declared package must equal its directory.
- `git mv` the dirs per source root (`common`, `bukkit`, `fabric/*`, tests). Never move third-party-package files in your tree (e.g. `net/kyori/...`).
- Slash/path forms escape the dotted rewrite: tests reading `Path.of("src/main/java/old/pkg/checks")`, `cliff.toml` commit_preprocessors. Search `rg 'ac/grim|"ac", *"grim"'` after the move. Leave pre-existing stale cliff entries alone.
- Loaded-by-name strings must be rewritten in lockstep: `plugin.yml main`, `fabric.mod.json` entrypoints, mixin json `package`, reflective `HANDLER_CLASS` strings. Verify each resolves to a real file.
- Verify: invariants (external FQN count unchanged, zero leftover old in-repo FQNs, java file count unchanged), `:common:test`, `:bukkit:shadowJar`, Fabric compile/processResources, then a JVM smoke `Class.forName`-ing renamed classes from the built jar (add cached paper-api jar to classpath), asserting OLD in-repo names no longer resolve. List class names from the jar — don't guess.

## Pitfalls

- Code may build a JVM system-property prefix from the brand (`SystemArgumentFactory.Builder.of("Brand")` gives `-DBrandPlatformOverride`) — update `systemProperty(...)` in build.gradle.kts or tests fail with "Unknown platform!".
- Renaming both command aliases (`"grim","grimac"`) collapses them into duplicate `"x","x"` — give the second a distinct short alias and update alias checks.
- Env vars and CI user-agents need renaming across workflow, build.gradle.kts, buildSrc.
- Language inflections and CJK adjacency defeat `\b`; use ASCII-letter lookarounds.
- Verify with a throwaway test registering commands against a real Cloud CommandManager, then delete it.
- Never `grep -r -a` over an extracted jar tree (hangs); targeted class-name scan instead.
- Do not create or push remotes; new repo links 404 until the repo exists.

_Migrated from: rebrand-fork-keep-java-package_
