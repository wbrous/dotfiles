---
name: watermarks-remover-propagate-to-system
description: "After merging/changing wbrous/watermarks-remover, propagate to the machine (global git hooks + omp /remove-watermarks extension only), and debug \"audit_dir.py failed\" from /remove-watermarks."
---

## Propagate to system (user wants ONLY omp extension + git hooks, nothing else)
From the checkout (`~/Documents/Development/watermarks-remover`), after the change is on `main`:
1. `./service/scripts/install_global_hooks.sh` - re-vendors `service/scripts` into `~/.local/share/watermarks-remover/`, copies pre-commit hook to `~/.config/git/hooks/`, keeps core.hooksPath/mode settings. The omp extension reads `audit_dir.py`/`clean_file.py` from this data home, so this is required for both.
2. `./integrations/omp/install.sh` - copies `integrations/omp/extensions/remove-watermarks.ts` to `~/.omp/agent/extensions/`.
3. Verify with `diff -rq service/scripts ~/.local/share/watermarks-remover/service/scripts -x __pycache__`, `diff -q` on the extension and `service/scripts/git_hooks/pre-commit` vs `~/.config/git/hooks/pre-commit`.
4. Tell user to restart omp or `/reload-plugins`.
Do NOT install skills (claude/codex/grok/cursor `install_skill.py`, `make install-*-skill`) - user explicitly said not to.

## Smoke test hook
In a `mktemp -d` repo: commit a file with U+200B -> must exit 1 (blocked); commit clean files -> exit 0.

## Gotcha: `/remove-watermarks` -> "audit_dir.py failed: Command failed" with empty stderr
`audit_dir.py` exit codes: 0 clean, 1 actionable findings (JSON still on stdout), 2 usage error, 3 partial scan. Node `execFileSync` throws on any non-zero, so the extension used to fail on every dir that had marks. Fixed in `runAudit` (accept 0/1/3, read `e.stdout`), commit c942f01. If it recurs, check the fix survived an upstream merge of `integrations/omp/`. `clean_file.py` exit 1 = residual marks/failure, so `runClean` treating it as failed is correct.

## Test workspaces
Dirty fixture dir pattern: `/tmp/wm-dirty-N` plus `/tmp/wm-dirty-N.pristine` copy for diffing; include controls (clean text, legit ZWJ emoji, prose mentioning Claude as subject, code `generator`) that must not change. Audit JSON: `audit_dir.py DIR --json` -> `files[]` with `path, kind, confidence, has_ai_metadata, suspicious_total`.
