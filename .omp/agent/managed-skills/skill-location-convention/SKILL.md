---
name: skill-location-convention
description: "Use when creating, moving, or relocating agent skills — project-specific skills belong in the project's .omp/skills/ (git-tracked), not the global ~/.omp/agent/managed-skills/."
---

## Rule

A skill that is specific to one repository MUST live in that repo under `.omp/skills/<skill-name>/SKILL.md` (project-local, git-tracked), NOT in the global `~/.omp/agent/managed-skills/`.

Only genuinely cross-project skills (e.g. `spotify-*`, `omarchy-*`, `orca-*`) belong globally.

## Why

`manage_skill` only writes to `~/.omp/agent/managed-skills/` (global). Project-specific knowledge created there:
- leaks into every other project's session,
- is not versioned with the repo, and
- is not shared with the team.

## How to move a managed skill to project-local

1. Read the current global file: `~/.omp/agent/managed-skills/<name>/SKILL.md`.
2. `write` it to `<project>/.omp/skills/<name>/SKILL.md` with explicit frontmatter:
   ```yaml
   ---
   name: <name>
   description: "<one-line discovery description>"
   ---
   ```
   The directory name is the skill name; layout is `<skills-root>/<skill-name>/SKILL.md` (non-recursive, one level under `skills/`).
3. `manage_skill` with `action: "delete"` to remove the stale global copy.
4. `git add .omp/` and commit so it ships with the repo.

When creating a NEW project-specific skill, write it directly to `.omp/skills/<name>/SKILL.md` — never via `manage_skill`.
