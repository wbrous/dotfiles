---
name: orca-mise-config-stomp
description: "Use when mise shims (e.g. bun, node) report \"No version is set for shim\" inside an Orca-managed pane/worktree, or when ~/.config/mise/config.toml keeps reverting/getting corrupted (e.g. truncated TOML like a stray st\" line) even after running mise use -g. Also covers git push failing with \"unable to get password from user\" / \"terminal prompts disabled\" in these panes."
---

## Symptom
- `mise ERROR No version is set for shim: bun` (or similar) even after `mise use -g <tool>@<version>`.
- `~/.config/mise/config.toml` reverts to a minimal manifest (e.g. just `gh = "latest"`) shortly after being edited.
- Sometimes the file gets corrupted mid-write (malformed TOML, truncated fragment like a stray `st"` line), causing `mise::config::parse_error` spam.
- Bash commands that touch mise config (e.g. `git config --global ...`) can also trigger a runaway repeated-log spam ("mise ~/.config/mise/config.toml tools: gh@2.97.0" printed hundreds/thousands of times) — this looks like an infinite loop but is just the Orca write-loop's log line repeating; it is harmless noise, not a hung process.

## Root cause
Inside an Orca-managed pane (env has `ORCA_*` vars, `TERM_PROGRAM=Orca`), the pane's own long-running `omp` runtime process periodically re-asserts its own cached tool manifest onto the **global** `~/.config/mise/config.toml` (observed interval: ~2 seconds). This is a background loop independent of any `mise` CLI invocation you run — it will stomp manual edits to the global config file continuously, for as long as that Orca pane process is alive. Concurrent Orca panes racing to write the same global file simultaneously can also produce transient TOML corruption (non-atomic write interleaving).

## Diagnosis
1. Confirm it's Orca: `ps aux | grep omp` — look for a `bun /.../omp` process; check its env via `cat /proc/<pid>/environ | tr '\0' '\n' | grep -i orca`.
2. Confirm the loop: watch the file mtime — `for i in 1 2 3; do sleep 2; stat -c '%y' ~/.config/mise/config.toml; done`. If it changes every ~2s, it's the Orca loop, not a one-off race.

## Fix
Do NOT keep editing the global `~/.config/mise/config.toml` — Orca will always win that race. Instead pin tool versions in a **project-local** `.mise.toml` at the worktree root:

```toml
[tools]
node = "25.2.1"
bun = "1.3.14"
```

mise layers project config on top of global config, and Orca's loop only touches the global file, so this survives. Verify with `mise config ls` (should show both the global file and the project file with their respective tools) and `bun -v` / `node -v` resolving correctly, repeated across a couple of the loop's rewrite cycles to confirm stability.

Tools not worth pinning per-project (e.g. `gh`, used only globally) will still occasionally emit that noisy repeated log line to stderr on shim invocation — safe to ignore/grep out (`grep -v "mise ~/.config/mise/config.toml tools"`), not an error.

## Related: `git push` fails with "terminal prompts disabled"
If `gh auth status` shows already logged in but `git push` fails with `fatal: could not read Username for 'https://github.com'` / `unable to get password from user` / `unable to read askpass response from '/usr/bin/false'`, git simply has no credential helper wired up — it's not a mise issue. Fix: `gh auth setup-git` (uses gh's already-stored token as git's credential helper). Then `git push` works normally. No need to touch remotes or tokens manually.
