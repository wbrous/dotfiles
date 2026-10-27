---
name: managed-skill-dotfiles-autosync-extension
description: "Use when maintaining/debugging the omp extension that auto-commits managed skills (create/update/delete) into the dotfiles bare repo, or when writing any omp extension that runs git against dotfiles — covers the tool_result hook, pi.exec env-not-forwarded gotcha, the OMPCODE=1 shell-prefix requirement (process.env fails), no-op skip, gitleaks behavior, and the /dotfiles-scan scout-survey command."
---

# managed-skill-dotfiles autosync extension

The omp extension at `~/.omp/agent/extensions/managed-skill-dotfiles.ts` auto-commits EVERY successful `manage_skill` outcome — **create, update, AND delete** — into the dotfiles bare repo (`~/.dotfiles`) the moment it lands, so managed skills stay backed up without a manual fan-out scout survey. Create/update commit `Add managed-skill: <name>` / `Update managed-skill: <name>`; delete runs `git rm` and commits `Remove managed-skill: <name>`.

## Mechanism

Hooks the `tool_result` event: fires after every tool executes with `{ toolName, input, isError }`. Filters `toolName === "manage_skill"`, skips `isError`, reads `input.action` + `input.name`, and runs the bare-repo git mutation via `pi.exec`. A per-name `inFlight` set dedupes rapid same-skill mutations.

## Gotcha 1: pi.exec does NOT forward `env` — use git leading flags, not GIT_DIR/GIT_WORK_TREE env vars

`pi.exec`'s `ExecOptions` has only `cwd`/`signal`/`timeout` — an `env` option is silently dropped (the type doesn't even have it). So to target the bare repo, pass `--git-dir`/`--work-tree` as leading global options (the exact expansion of the `dotfiles` alias):

```ts
pi.exec("git", [`--git-dir=${DOTFILES_DIR}`, `--work-tree=${homedir()}`, ...args], { cwd: homedir() });
```

## Gotcha 2 (verified the hard way): OMPCODE=1 must be a shell PREFIX, not process.env

The shared `prepare-commit-msg` hook (see `git-scoped-coauthor-trailer` skill) appends `Co-authored-by: wbrous-dev-ai` ONLY when `OMPCODE=1` is in the git subprocess env. The harness injects `OMPCODE=1` only into the per-tool bash env, NOT into the omp process env extensions run in — so extension-spawned git commits silently miss the co-author.

- **FAILED approach**: `process.env.OMPCODE = "1"` before `pi.exec` — empirically did NOT propagate (live extension commit `52ad597` lacked the co-author).
- **WORKING approach**: run the git command through a shell with the env assignment on the argv:

```ts
const argv = ["git", `--git-dir=${DOTFILES_DIR}`, `--work-tree=${homedir()}`, ...args];
const cmd = `OMPCODE=1 ${argv.map(shq).join(" ")}`;
const result = await pi.exec("/bin/sh", ["-c", cmd], { cwd: homedir() });
```

with `shq(s) = "'" + s.replace(/'/g, `'\\''`) + "'"` so skill names/paths can't escape the shell. Verified: extension commits `eae8f1c` (create) and `7394186` (delete) both carried `Co-authored-by: wbrous-dev-ai`.

## Other guardrails

- Never `add -A` / `git rm -r`; only the single `.omp/agent/managed-skills/<name>/SKILL.md` path.
- No-op skip: `git diff --cached --quiet -- <path>` returns 0 → byte-identical to HEAD → skip commit (keeps the "what's new" signal clean).
- Delete of a never-tracked skill is a clean no-op (git rm "did not match" → return silently).
- Delete reported but file still on disk → leave dotfiles untouched and report the anomaly.
- Never bypass gitleaks (`GIT_ALLOW_SECRETS=1` stays a human escape hatch); a blocked commit surfaces the hook stderr via `sendMessage({ triggerTurn: true })`.
- Never calls `manage_skill`, so it can never re-trigger itself.

## Companion: /dotfiles-scan extension

`~/.omp/agent/extensions/dotfiles-scan.ts` registers the `/dotfiles-scan` slash command. It does NOT survey itself — it injects a precise prompt (via `sendMessage` + `triggerTurn`) telling the agent to: snapshot `git --git-dir='$HOME/.dotfiles' --work-tree='$HOME' ls-tree -r --name-only HEAD`, diff against on-disk candidates per cluster, fan out READ-ONLY scout subagents via one parallel `task` batch (verdicts `DEF ADD` / `MAYBE` / `SHOULDN'T ADD`), auto-commit DEF ADDs one path at a time (filtered against already-tracked), and report `DEF ADD COMMITTED:` / `MAYBE:` / `NO:` lists. Args: `skills` / `config` / `home` scopes (autocompleted) or free-form focus.

## Verification recipe

Create a throwaway skill, confirm `Add managed-skill:` commit with the co-author; delete it, confirm `Remove managed-skill:` commit with the co-author and the file gone from `ls-tree`; check the commit trailers with `git show -s --format=%B`.
