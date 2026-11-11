# omp skills, agents, and research workflows

Scope: where skills live, how to generate/refresh AGENTS.md with parallel research, and how to dedupe project AGENTS.md against global guidelines.

## Skill location: project-local vs global

**Rule:** a skill specific to one repository MUST live in that repo under `.omp/skills/<skill-name>/SKILL.md` (project-local, git-tracked), NOT in global `~/.omp/agent/managed-skills/`. Only genuinely cross-project skills (e.g. `spotify-*`, `omarchy-*`, `orca-*`) belong globally.

**Why:** `manage_skill` only writes to `~/.omp/agent/managed-skills/` (global). Project-specific knowledge created there leaks into every other project's session, isn't versioned with the repo, and isn't shared with the team.

**Moving a managed skill to project-local:**
1. Read the global file `~/.omp/agent/managed-skills/<name>/SKILL.md`.
2. `write` it to `<project>/.omp/skills/<name>/SKILL.md` with explicit frontmatter (`name:`, one-line `description:`). Layout is `<skills-root>/<skill-name>/SKILL.md` (non-recursive, one level under `skills/`).
3. `manage_skill` with `action: "delete"` to remove the stale global copy.
4. `git add .omp/` and commit so it ships with the repo.

New project-specific skills go directly to `.omp/skills/<name>/SKILL.md` — never via `manage_skill`.

_Migrated from: skill-location-convention_

## Generating/refreshing AGENTS.md via parallel research agents

**When:** asked to build/refresh top-level `AGENTS.md` (or `CLAUDE.md`) with a required section structure (Overview, Architecture, Key Directories, Dev Commands, Conventions, Important Files, Runtime/Tooling, Testing & QA).

**Procedure:**
1. Quick root scan first (`find -maxdepth 3`, ignoring build/`.gradle`/`.idea`/`node_modules`/`.git`) so task prompts reference real top-level paths, not guesses.
2. Spawn exactly 4 **read-only** scouts in one `task` batch:
   - `CoreSrcResearch` — source tree layout, architecture/data flow, entry points, code conventions (naming, comments, state, DI), third-party integrations.
   - `TestsResearch` — test frameworks/dirs/deps/CI repo-wide; if none, an explicit "no automated tests" verdict plus whatever manual/interactive verification exists (tuner opmodes, scripts) — never come back empty just for lack of `src/test`.
   - `ConfigBuildResearch` — build tool versions, manifests, module structure, exact verified build/test/lint/run commands (cross-check against on-disk artifacts, not just declared gradle/npm tasks).
   - `ScriptsDocsResearch` — README, `doc/` folders, existing AGENTS.md/CLAUDE.md/CONTRIBUTING.md, project skill files, IDE run configs, deployment hints.
   Each prompt gets: full project context (what the repo is, frameworks in play), an explicit output contract (structured markdown, every claim cited to a real file path, "not found" stated explicitly), and a READ-ONLY constraint.
3. `wait` for all 4, reading each full `agent://<TaskName>/report` — the preview/summary truncates; the richest detail (snippets, drift/dead-code findings, line numbers) is in the full report.
4. Cross-check overlapping claims (TestsResearch ∩ ConfigBuildResearch on "no test framework"; ScriptsDocsResearch ∩ CoreSrcResearch on doc-vs-code drift) before trusting them.
5. Synthesize into one AGENTS.md matching the required headings literally. Prioritize verbatim code snippets from reports (not paraphrase), explicit dead-code/stale-doc/landmine callouts (e.g. "constructed but never used", "still holds vendor doc-example values"), artifact-verified commands, and an honest "no tests exist" section describing the real manual/on-device verification path instead of inventing test guidance.
6. `write` to the exact requested path (usually repo root).

**Pitfalls:** don't skip the full `report` pull; don't invent test guidance when agents confirm none exist; don't let README claims go unverified — cross-reference with core-src findings and call out stale docs in Conventions.

_Migrated from: agents-md-parallel-research-synthesis_

## Deduping project AGENTS.md against global guidelines

**When:** asked to clean up a project's `AGENTS.md`/`CLAUDE.md` so it holds only project-specific facts after generic philosophy moved (or will move) into global `~/.omp/agent/APPEND_SYSTEM.md`. Triggers: "strip the generic stuff", "make this project-specific", "dedupe against global config".

**Procedure:**
1. Read the target `AGENTS.md` and `CLAUDE.md` (often `CLAUDE.md` is just `@AGENTS.md` — check before treating separately). Read global `~/.omp/agent/APPEND_SYSTEM.md` to know exactly what's covered globally; never re-embed it.
2. Research the repo before writing — never invent facts. Dispatch a `scout` via `task` (for large/unfamiliar repos, one per subsystem in a single `tasks[]` batch), grounded in real paths, covering: project purpose (from README/docs); languages/frameworks/package manager; exact install/build/dev/test/lint/typecheck/format/db commands from `package.json`/`pyproject.toml`/`Cargo.toml`/`Makefile`/CI (don't guess); directory/module structure and architecture; project-specific conventions evidenced in actual code (custom DSL, routing/dispatch pattern, state approach, naming, file discovery, logging discipline, review bots); environment/config (required/optional env vars, `.env.example`, external services); CONTRIBUTING/house-rules/code-comment conventions; gotchas (unusual build/deploy, monorepo layout, non-standard tooling, ordering-sensitive startup, CI-enforced rules like Conventional Commits or pinned versions).
3. Write the new file:
   - One-line/paragraph identity (what it is, core stack).
   - Short explicit note that generic philosophy lives in global config and is intentionally not repeated.
   - **Commands**: exact copy-pasteable commands with directory context (e.g. "run from `bot/`") and CI-enforced pins/gates.
   - **Environment**: required/optional env vars and what they actually control.
   - **Architecture**: real load-bearing structure — call out ordering-sensitive/non-obvious behavior explicitly (e.g. "commands are loaded before login on purpose, to close a cold-start gap — don't reorder this").
   - **Conventions specific to this repo**: only things pointable to actual files.
   Every claim traceable to a file the scout(s) actually read; no speculative or generic filler. If a sentence would apply equally to any TypeScript/Python/Rust project, it doesn't belong here — cut it. Preserve any pointer file (`CLAUDE.md` → `@AGENTS.md`).

**Note:** a research-then-write task, not a text-diffing task — replacing assumed/generic content with grounded, repo-specific content requires actually reading the repo. For monorepos with meaningfully different stacks, consider per-package AGENTS.md files instead of one flat root file.

_Migrated from: dedupe-agents-md-against-global-guidelines_
