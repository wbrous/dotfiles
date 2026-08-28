---
name: managed-skill-dotfiles-autosync-extension
description: "Use when maintaining/debugging the omp extension that auto-commits every successful manage_skill outcome (create/update/delete) for managed skills (~/.omp/agent/managed-skills) into the dotfiles bare repo (~/.dotfiles), when a managed skill wasn't auto-backed-up after manage_skill, or when writing any omp extension that runs git against the dotfiles repo — covers the tool_result event hook, the pi.exec env-not-forwarded gotcha (must use git --git-dir/--work-tree leading flags), the OMPCODE=1 co-author gotcha (must shell-prefix OMPCODE=1 git … via /bin/sh -c; process.env mutation does NOT work), delete sync via git rm, the no-op commit skip, and gitleaks-respecting behavior."
---

# managed-skill-dotfiles autosync extension

The omp extension at `~/.omp/agent/extensions/managed-skill-dotfiles.ts` (tracked in the dotfiles bare repo) auto-commits **every successful `manage_skill` outcome** — create, update, AND delete — into the dotfiles bare repo (`~/.dotfiles`) the moment the tool lands, so managed skills stay backed up without a manual fan-out scout survey.

## Architecture

- Hooks the extension `tool_result` event (fires after every tool executes with `{ toolName, input, isError }`), filters `toolName === "manage_skill"` and `!isError`, then runs the git mutation async (never awaited, reported back via `pi.sendMessage({ triggerTurn: true })`).
- Commit messages follow the repo convention: `Add managed-skill: <name>`, `Update managed-skill: <name>`, `Remove managed-skill: <name>`.
- Per-name `inFlight` Set dedupes rapid consecutive mutations of the same skill so they can't race the bare-repo commit.

## Action handling

- **create** → `git add -- <path>` then commit `Add managed-skill: <name>`.
- **update** → same as create but `Update managed-skill: <name>`; skips the commit entirely when `git diff --cached --quiet` returns 0 (byte-identical to HEAD, no no-op commit noise).
- **delete** → `git rm -- <path>` then commit `Remove managed-skill: <name>`, dropping the file from dotfiles HEAD. If `manage_skill` reported a successful delete but the SKILL.md still exists on disk, the dotfiles copy is left untouched and the anomaly is reported. If the skill was never tracked in dotfiles (e.g. its earlier commit failed), `git rm`'s pathspec error is treated as a clean no-op.
- Never `add -A` / `git rm -r` — only the single `.omp/agent/managed-skills/<name>/SKILL.md` path.

## Gotcha 1: pi.exec does NOT forward env

`pi.exec`'s `ExecOptions` only has `signal`/`timeout`/`cwd` — no `env`. Setting `GIT_DIR`/`GIT_WORK_TREE` via an env option is silently dropped and git runs against the wrong repo. The fix: use leading global flags instead, exactly the expansion of the `dotfiles` shell alias:

```ts
const argv = ["git", `--git-dir=${DOTFILES_DIR}`, `--work-tree=${homedir()}`, ...args];
```

## Gotcha 2: OMPCODE=1 — process.env mutation does NOT work, shell-prefix does

The shared `prepare-commit-msg` hook (see `git-scoped-coauthor-trailer` skill) appends `Co-authored-by: wbrous-dev-ai <ai-bot@gir0fa.com>` **only when `OMPCODE=1`** is in the git subprocess env, distinguishing agent commits from manual ones. The harness injects `OMPCODE=1` only into per-tool bash subprocesses, not the omp process env the extension runs in.

Setting `process.env.OMPCODE = "1"` before `pi.exec` **was live-verified to fail** (extension commit `52ad597` had Signed-off-by but no Co-authored-by). The working approach: run the git command through a shell with `OMPCODE=1` prefixed on the argv, with every git arg single-quoted (`shq`) so the deliberately-shallow wrapper can only ever run git:

```ts
function shq(s: string): string { return `'${s.replace(/'/g, `'\\''`)}'`; }

const cmd = `OMPCODE=1 ${argv.map(shq).join(" ")}`;
const result = await pi.exec("/bin/sh", ["-c", cmd], { cwd: homedir() });
```

Live-verified: extension-made commits `eae8f1c` (Add) and `7394186` (Remove) both carry `Co-authored-by: wbrous-dev-ai`.

## Gotcha 3: gitleaks

The global gitleaks pre-commit hook fires on every dotfiles commit. Never bypass with `GIT_ALLOW_SECRETS=1` — that is a deliberate human escape hatch. If the commit fails (hook rejection), surface the hook's stderr via `sendMessage` and let the agent/user decide.

## Verification

End-to-end test in a live session: `manage_skill create` a throwaway skill → expect an `Add managed-skill:` auto-commit with the wbrous-dev-ai co-author; `manage_skill delete` it → expect a `Remove managed-skill:` auto-commit, file gone from both disk and dotfiles HEAD. Check with `git --git-dir=~/.dotfiles --work-tree=~ log --oneline -2` and `git show -s --format=%B HEAD`. Note: extension edits only take effect on the NEXT session reload (extensions load at session start).
