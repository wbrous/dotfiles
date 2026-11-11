# Mise shims, PATH loops, and wrapper hangs

Version-pinned tool paths that rot, self-recursive shims, and spinner output that looks like a loop.

## mise-updated gh breaks the git credential helper

**Symptom:** every git-over-HTTPS command drops to `Username for 'https://github.com':`; the helper line shows a versioned path that no longer exists:
```
/home/USER/.local/share/mise/installs/gh/2.97.0/.../bin/gh auth git-credential: line 1: .../gh: No such file or directory
```

**Cause:** `credential.https://github.com.helper` points at an absolute versioned mise path; mise auto-updated `gh` (2.97.0 → 2.98.0 via `latest`) and pruned the old dir. Confirm: `mise ls gh`, `which gh`, `git config --global --get-regexp credential`.

**Fix:** point at `gh` via PATH/shim (survives updates). `credential.<url>.helper` is multi-valued (empty-string reset entry + real helper), so reset then add — plain set errors "cannot overwrite multiple values":
```sh
git config --global --replace-all credential.'https://github.com'.helper '' ''
git config --global --add credential.'https://github.com'.helper '!gh auth git-credential'
```
Repeat for other versioned-path hosts (e.g. `gist.github.com`). Verify: `printf 'protocol=https\nhost=github.com\n\n' | git credential fill` returns username with no prompt.

_Migrated from: mise-tool-git-credential-helper-path-rot_

## Custom shim hangs forever (self-recursion via PATH)

**Symptom:** `~/.local/bin/gh` (or claude/ghui/playwright shim) hangs indefinitely — `timeout 5 gh --version; echo EXIT:$?` → `EXIT:124`.

**Cause:** template `command -v X || mise use -g X; exec X "$@"` in a dir first in `$PATH` — PATH lookup finds the shim itself again; infinite self-re-exec (single-process chain, not a fork bomb).

**Fix:** exec the resolved real binary, never the bare name:
```sh
exec "$(mise which gh)" "$@"
```
Apply to every same-template shim. Verify: `timeout 10 gh --version` exits 0 quickly. Diagnose copies: `which -a gh` + `cat "$(which gh)"`.

_Migrated from: self-recursive-path-shim-hang_

## mise spinner transcript looks like an infinite loop

**Symptom:** captured transcript shows `mise ~/.config/mise/config.toml tools: gh@2.97.0 ◜` hundreds of times.

**Cause:** not a loop — one ~1–2s spinner redrawn via `\r`, which non-TTY capture (log read, piped paste) expands to one line per frame. Verified against Orca's asar and omp's binary: neither spawns mise nor rewrites the mise config; Orca's xterm.js panes collapse `\r` correctly. A since-deleted "Orca stomps mise config" theory was checked against source and is wrong — don't resurrect it.

**Fix:** `mise settings set quiet true` (verify `mise settings get quiet` → `true`).

_Migrated from: mise-spinner-looks-like-loop_

## gh wrapper hangs over SSH; general hang triage

**Symptom:** `gh --version` hangs through a wrapper (see self-recursion above) or `gh auth git-credential get` blocks.

**Fix:** same shim fix first; if the helper path itself is stale see the credential-helper section. Diagnose with `timeout` + `which -a` before assuming a network/auth fault.

_Migrated from: gh-mise-wrapper-hang-use-real-binary_
