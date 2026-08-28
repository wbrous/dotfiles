---
name: managed-skill-dotfiles-autosync-test
description: Temporary test skill verifying the managed-skill-dotfiles extension auto-commits new managed skills into the dotfiles bare repo.
---

# managed-skill-dotfiles-autosync-test

Temporary integration-test skill. Its sole purpose is to confirm that the
`managed-skill-dotfiles` omp extension observes a successful `manage_skill`
create and auto-commits `~/.omp/agent/managed-skills/<name>/SKILL.md` into the
`~/.dotfiles` bare repo with a `git commit` message following the repo's
`Add managed-skill: <name>` convention.

Used by: manual verification that a newly created managed skill lands in
dotfiles without a separate fan-out scout survey. Delete this skill once
verified (`manage_skill` action=delete, name=managed-skill-dotfiles-autosync-test).
