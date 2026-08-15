---
name: self-recursive-path-shim-hang
description: "Use when a custom shim script in ~/.local/bin (or any early-$PATH dir) does command -v X || mise use -g X; exec X \"$@\" and invoking X hangs forever (e.g. gh, claude, playwright shims) — the shim re-execs itself via PATH lookup instead of the real binary."
---

## Symptom
A wrapper script like `~/.local/bin/gh`:
```bash
#!/bin/bash
command -v gh >/dev/null 2>&1 || mise use -g gh
exec gh "$@"
```
placed in a directory that is *first* in `$PATH` (e.g. `~/.local/bin`). Running `gh --version` (or any invocation) hangs indefinitely — no output, no error, just blocks until killed.

## Root cause
`exec gh "$@"` resolves `gh` via `$PATH`, and since this script's own directory is first in `$PATH`, `command -v gh` / the exec both find *this same script* again. Each invocation re-execs itself → infinite self-recursion. Not a fork bomb (single process re-exec chain), but it never returns — looks exactly like a hang under `timeout`.

Check for this pattern across all custom shims in the same dir (e.g. `gh`, `claude`, `ghui`, `playwright` — anything following the same template) since it's usually copy-pasted.

## Diagnosis
```bash
timeout 5 gh --version; echo EXIT:$?   # EXIT:124 confirms hang/timeout
which -a gh                            # confirms the broken shim shadows the real binary
cat "$(which gh)"                      # inspect the shim for a bare `exec <toolname> "$@"`
```

## Fix
Point `exec` at the resolved real binary path instead of the bare tool name, so PATH lookup can't loop back to the shim itself:
```bash
#!/bin/bash
command -v gh >/dev/null 2>&1 || mise use -g gh
exec "$(mise which gh)" "$@"
```
Apply the same fix to every shim in the directory sharing the template. Verify with `timeout 10 gh --version` returning quickly and exit 0.
