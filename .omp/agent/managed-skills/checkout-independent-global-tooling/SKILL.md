---
name: checkout-independent-global-tooling
description: "Use when a project's global git hooks, omp/Claude extensions, or other machine-wide tooling must keep working after the source repo checkout is deleted — vendor the implementation into a data dir under ~/.local/share/project/ and point every consumer (hook config, extension file) at that vendored copy instead of the live checkout."
---

## Problem

A repo ships global tooling that installs itself machine-wide: a `core.hooksPath` git hook, an omp/Claude Code extension symlinked into `~/.omp/agent/extensions` or `~/.claude/...`, etc. The naive install either symlinks straight into the checkout or hardcodes the checkout's absolute path. Works fine until the user runs `rm -rf` on the repo — then every future `git commit` anywhere, or the `/slash-command`, silently breaks (dangling symlink, missing script, hook exits nonzero or errors).

## Fix pattern

1. Pick one data home: `~/.local/share/<project>/`, overridable via an env var (`<PROJECT>_DATA_HOME`).
2. The installer script (run once from inside the checkout) **vendors**: `cp -R` the actual implementation (scripts, extension `.ts`/`.js` files) into that data home. Not a symlink — a real, standalone copy.
3. Any generated config (e.g. `~/.config/<project>/global-hooks.conf` sourced by the hook, or an env var the extension reads at runtime) points at the **data home**, never at the checkout path.
4. Anything installed into a third-party-managed location (git's `core.hooksPath` dir, `~/.omp/agent/extensions/`) must be a **copy of the vendored file**, not a symlink into the checkout and not a symlink into the data home either if that location itself might get relocated — copy-of-copy is fine and cheap.
5. Uninstall scripts should never reference the checkout at all — only `$HOME`-relative paths — so they keep working even after the checkout is gone.
6. Re-running the installer (from a fresh `git pull` or fresh clone) re-vendors (`rm -rf` the old vendored dir, `cp -R` fresh) — this is the update mechanism, not `git pull` itself.

## Verification that actually proves it

Don't just trust the design — prove it: `mv` the checkout directory aside (or to a `.MOVED_AWAY` suffix), then exercise the real behavior (run the vendored script directly, run an actual `git commit` through the installed hook) from a **shell with a valid cwd** (a bash tool's persistent shell can have a stale cwd pointing inside the now-moved directory — pass an explicit safe `cwd` like `/tmp` to escape that trap). Then move the checkout back.

## Gotcha: bash tool persistent-shell stale cwd

If a persistent shell tool's cwd is inside a directory you just `mv`'d/`rm -rf`'d, every subsequent command in that shell fails with "working directory does not exist" even for commands that don't touch that path. Pass an explicit `cwd` parameter pointing elsewhere (e.g. `/tmp`) to recover, rather than trying `cd` from within the broken shell.
