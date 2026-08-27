---
name: git-global-hooks-and-omp-command-vendoring
description: "Use when installing a global git hook (via core.hooksPath) or an omp/Claude-style extension/command whose logic lives inside a specific project checkout, and the tool must keep working after that checkout is deleted — e.g. \"make this work globally, then I want to rm -rf this repo\". Also covers safely sharing core.hooksPath with a pre-existing hook (e.g. gitleaks) without clobbering it, and the stale-cwd trap when a bash tool's persistent shell cwd is a directory you just moved/deleted."
---

## Problem

A repo ships a tool (Python/Node scripts) plus an installer that wires it into (a) a global git hook via `git config --global core.hooksPath`, and/or (b) an agent-harness extension/command (e.g. omp `~/.omp/agent/extensions/*.ts`). If the installer just symlinks or references files inside the checkout, the tool breaks the moment the user deletes that checkout — which they often want to do once "it's installed."

## Fix: vendor into a data home, never reference the checkout at runtime

1. Pick one shared directory, e.g. `~/.local/share/<tool-name>/`, overridable via an env var (`<TOOL>_DATA_HOME`).
2. Installer script's job: `cp -R` (not symlink) the runtime implementation from the checkout into `$DATA_HOME/...` on every install run (idempotent: `rm -rf` the destination subtree first, then copy fresh). This makes "re-run installer after `git pull`" the update path.
3. Write a small config file (e.g. `~/.config/<tool>/global-hooks.conf`) containing `TOOL_HOME="$DATA_HOME"` — both the hook and the extension read *this config*, never a path inside the checkout.
4. The git hook script itself, and the extension/command file, must also be **copied** (not symlinked) into their install targets (`git hooksPath` dir, `~/.omp/agent/extensions/`) — sourced from the vendored copy, not the live checkout.
5. Also vendor the installer/uninstaller scripts themselves into `$DATA_HOME/bin/` for future reference, plus a `.vendor-info` file recording source path + timestamp — nice-to-have but cheap and helps debugging "why is this stale."
6. Verify independence for real: temporarily `mv` the checkout aside (not just trust the design), re-run the installed hook / invoke the vendored script directly, confirm it works, then move the checkout back.

## Sharing `core.hooksPath` safely (don't clobber other tools)

Setting `git config --global core.hooksPath` is exclusive — git no longer looks at any other hook location, including other tools that already claimed that directory (e.g. a gitleaks or husky global hook).

- Before installing: check the current global `core.hooksPath`. If a `pre-commit` already exists there and doesn't carry your own marker comment, `mv` it aside to `pre-commit.pre-<yourtool>` and have your hook script `exec`/chain to that file at the end if it exists+executable.
- If your hook's own marker is already present (idempotent reinstall), just overwrite in place; don't re-chain (would duplicate/break).
- On uninstall, reverse this: remove your hook, restore the backed-up chained hook if present, and only `git config --global --unset core.hooksPath` if the managed dir is now empty.
- Test this explicitly: create a fake foreign hook first, install, confirm chaining fires (both tools' output appears), then uninstall and confirm the foreign hook is restored byte-for-byte.

## bash-tool stale-cwd trap

If a bash/shell tool has a **persistent session cwd**, and you `mv`/`rm` that directory mid-session (e.g. to simulate "checkout deleted" for a verification test), every subsequent command in that same session fails immediately with `Working directory does not exist: ...` — even commands that don't need that directory — because the shell tries to re-enter the stale cwd before running anything. Fix: pass an explicit different `cwd` (e.g. `/tmp`) on the next call, or open a fresh shell/subshell, rather than assuming the failure means your test failed.
