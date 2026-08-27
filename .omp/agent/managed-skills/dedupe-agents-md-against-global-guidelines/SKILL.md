---
name: dedupe-agents-md-against-global-guidelines
description: "Use when the user asks to clean up, dedupe, or rewrite a project's AGENTS.md/CLAUDE.md (or similar agent context file) so it only contains project-specific facts instead of generic engineering philosophy — especially after that philosophy has been (or will be) moved into the global ~/.omp/agent/APPEND_SYSTEM.md. Triggers: \"strip the generic stuff from AGENTS.md\", \"make this AGENTS.md project-specific\", \"dedupe AGENTS.md against global config\", or requests to research a repo and rewrite its agent guidelines file."
---

## Goal

Given a project's `AGENTS.md` (or `CLAUDE.md`) that currently mixes generic engineering philosophy with project facts, rewrite it to contain ONLY project-specific, verifiable facts. Generic philosophy (contracts, invalid-states-unrepresentable, crash-early, test-the-property-not-the-wiring, "you are lazy and stupid" framing, etc.) belongs in the global `~/.omp/agent/APPEND_SYSTEM.md` — it applies to every session automatically and must not be repeated per-project.

## Procedure

1. **Read the existing file(s).** Read the target repo's `AGENTS.md` and `CLAUDE.md` (often `CLAUDE.md` is just `@AGENTS.md`, a pointer — check before treating it as a separate target). Read the current global `~/.omp/agent/APPEND_SYSTEM.md` too, so you know exactly what's already covered globally and never re-embed it.

2. **Research the repo before writing anything.** Never invent project facts from memory or guesswork. Dispatch a `scout` subagent (via `task`) to investigate the actual repository and report back, grounded in real file paths, covering:
   - Project purpose (one paragraph, from README/docs)
   - Language(s), frameworks, package manager
   - Exact commands: install, build, dev/run, test, lint, typecheck, format, db/migration commands — read `package.json`/`pyproject.toml`/`Cargo.toml`/`Makefile`/CI workflows for the real invocations, don't guess
   - Directory/module structure and architecture at a level someone unfamiliar with the repo needs
   - Project-specific conventions actually evidenced in code (not generic advice) — e.g. a custom DSL, a specific routing/dispatch pattern, a specific state-management approach, naming schemes, file-discovery conventions
   - Environment/config: required env vars, `.env.example` contents, external services integrated
   - Any existing CONTRIBUTING.md / house-rules docs / code comments describing conventions beyond generic philosophy
   - Gotchas: unusual build/deploy steps, monorepo/workspace layout, non-standard tooling, ordering-sensitive startup code, CI-enforced rules (e.g. Conventional Commits, pinned tool versions)

   For a large or unfamiliar repo, this may need more than one scout (e.g. one per major subsystem) — fan them out in a single `tasks[]` batch, not serially.

3. **Write the new file.** Structure it as:
   - One-line/one-paragraph project identity (what it is, core stack)
   - A short explicit note that generic philosophy lives in the global config and is intentionally not repeated here
   - **Commands** section: exact, copy-pasteable commands, with directory context (e.g. "run from `bot/`") and any CI-enforced version pins or gates
   - **Environment** section: required/optional env vars and what they actually control
   - **Architecture** section: the real load-bearing structure — call out ordering-sensitive or non-obvious behavior explicitly (e.g. "commands are loaded before login on purpose, to close a cold-start gap — don't reorder this")
   - **Conventions specific to this repo** section: only things you can point to actual files for (a custom import style, a specific type-satisfaction pattern, a logging discipline, an automated review bot, etc.)

   Every claim must be traceable to a file the scout(s) actually read. No speculative or generic filler.

4. **Verify no duplication.** Diff the new content mentally against the global `APPEND_SYSTEM.md` — if a sentence would apply equally to any TypeScript/Python/Rust project, it doesn't belong in the project file. Cut it.

5. **Write the file** with the `write` tool (full overwrite, since nearly everything changes), preserving any pointer file (`CLAUDE.md` → `@AGENTS.md`) if it already exists as a pointer.

## Notes

- This is a research-then-write task, not a text-diffing task — the point is to replace assumed/generic content with grounded, repo-specific content, which requires actually reading the repo.
- If the repo is a monorepo or has multiple packages with meaningfully different stacks/conventions, consider whether per-package AGENTS.md files are warranted instead of one flat file — ask the user if genuinely ambiguous, otherwise default to one root file describing the structure.
