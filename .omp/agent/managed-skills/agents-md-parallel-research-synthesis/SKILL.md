---
name: agents-md-parallel-research-synthesis
description: "Use when asked to generate/refresh AGENTS.md (or CLAUDE.md) via parallel research agents covering core src, tests, configs/build, scripts/docs; not for single-pass manual writing."
---

## When to use
User asks to build/refresh a top-level `AGENTS.md` (or `CLAUDE.md`) using parallel `task` research agents, with a required section structure (Overview, Architecture, Key Directories, Dev Commands, Conventions, Important Files, Runtime/Tooling, Testing & QA).

## Procedure

1. **Quick root scan first** (bash `find -maxdepth 3`, ignoring build/.gradle/.idea/node_modules/.git) so task prompts reference real top-level paths instead of guessed ones.

2. **Spawn exactly 4 scout agents in one `task` batch**, each read-only, each targeting one slice:
   - `CoreSrcResearch` — main source tree(s): directory layout, architecture/data flow, key entry points, code conventions (naming, comment style, state management, DI patterns), third-party integrations.
   - `TestsResearch` — search whole repo for test frameworks/dirs/deps/CI; if none exist, get an explicit "no automated tests" verdict plus whatever manual/interactive verification surface exists instead (tuner opmodes, scripts, etc.) — don't let this come back empty just because there's no `src/test`.
   - `ConfigBuildResearch` — build tool version(s), dependency manifests, module structure, exact verified shell commands to build/test/lint/run (cross-check against actual build artifacts on disk when possible, not just declared gradle/npm tasks).
   - `ScriptsDocsResearch` — README, doc/ folders, any existing AGENTS.md/CLAUDE.md/CONTRIBUTING.md, project-specific skill files (global or repo-local), IDE run configs / deployment workflow hints.

   Give each task prompt: full project context paragraph (what the repo is, key third-party frameworks in play), an explicit output contract (structured markdown report, cite every claim to a real file path, state "not found" explicitly rather than omitting), and READ-ONLY constraint.

3. **Wait for all 4 via `wait`**, reading each `agent://<TaskName>/report` (or full JSON) in full — the preview/summary field truncates; always pull the full `report` field before synthesizing, since the richest detail (code snippets, drift/dead-code findings, exact line numbers) lives there.

4. **Cross-check overlapping claims** between agents (e.g. TestsResearch and ConfigBuildResearch both should agree on "no test framework"; ScriptsDocsResearch and CoreSrcResearch both should agree on doc-vs-code drift) before trusting them.

5. **Synthesize into one AGENTS.md** matching the user's required section structure exactly (headings must match literally, e.g. "Repository Guidelines" title). Prioritize:
   - Real code snippets copied verbatim from agent reports (not paraphrased/invented).
   - Explicit call-outs of dead code / stale docs / landmines the agents found (e.g. "constructed but never used", "still holds vendor's doc-example values") — these are exactly what makes an AI-assistant guide useful versus a generic README rehash.
   - Real, artifact-verified commands, not guessed ones.
   - An honest "no tests exist" section if that's what was found, describing whatever manual/alternative verification workflow actually exists instead of inventing test guidance.

6. Write the file with `write` to the exact path requested (usually repo root).

## Pitfalls
- Don't skip pulling the full `agent://<id>/report` field — the top-level task-result preview is truncated and drops the best material.
- Don't invent "how to run tests" guidance when agents confirm none exist; state it plainly and describe the real (possibly manual/on-device) verification path instead.
- Don't let doc/README claims go unverified — cross-reference with the core-src agent's findings; repos with stale docs are common and worth calling out explicitly in the Conventions section.
