---
name: uninstall-vendored-global-tool-hook-extension-dotfiles
description: "Use when fully removing a machine-wide tool installed as a core.hooksPath git hook, an ~/.omp/agent/extensions file, and a vendored data dir, including its tracking in the ~/.dotfiles bare repo and mentions in managed skills."
---

## Scope rule
Ask only if scope is ambiguous. "Remove X's hooks/extensions" meant ONLY things pertaining to X, not all hooks/extensions. Other hooks (pre-push, prepare-commit-msg) and extensions stay.

## Survey first (read-only)
- `git config --global core.hooksPath` (may live in ~/.config/git/config); `ls -la` the hooks dir.
- If the installer chained a foreign hook, it exists as `pre-commit.pre-<tool>`: restore it with `mv -f` over `pre-commit` (chmod +x), do NOT just delete.
- Extension: `~/.omp/agent/extensions/<tool>.ts` (+ `.bak`).
- Data/config: `~/.local/share/<tool>`, `~/.config/<tool>`, source checkout (check `git status` clean and branch == origin first).
- Mentions: `grep -rIl -i '<tool>|<ENV_VAR>' ~/.config ~/.local/bin ~/.bashrc ~/.omp/agent/extensions ~/.omp/agent/managed-skills ~/.claude ~/.gitconfig`. Do NOT grep ~/.local/share/omp/sessions (history, noisy; leave it).
- Other extensions may inject the tool's bypass env var (e.g. `X_DISABLE=1` in a bareGit command string); remove it, it becomes dead code.
- `git --git-dir=$HOME/.dotfiles --work-tree=$HOME ls-files | grep -i <tool>` for tracked artifacts.

## Remove
1. Restore chained hook, delete extension, data, config, checkout (use cwd=/tmp).
2. Delete the tool's managed skills; edit other skills' stale mentions (managed-skills are editable with `edit`; hash-tag edits shift line numbers, re-read after each PUT/CUT, and a CUT of a range eats the blank line before the next heading).
3. Delete `.bak` debris the hook left, but only after `cmp` shows IDENTICAL or the dir is yours (managed-skills, extensions). Do not mass-delete .bak in ~/.config without proof.
4. Commit dotfiles: `git add -u -- <explicit paths>` then `OMPCODE=1 git --git-dir=... -c commit.gpgsign=false commit` (unsigned to avoid fingerprint prompt; pre-push resigns). Never push unasked.

## Verify
- Smoke in a mktemp repo: the thing the old hook blocked now commits; a realistic fake secret (random `ghp_` + 36 chars, NOT AWS's documented EXAMPLE key, which gitleaks allowlists) is still blocked by gitleaks.
- Re-grep; autosync/survey processes may rewrite skills mid-task and reintroduce mentions, so re-check just before finishing.

## Gotcha
Bash output can vanish entirely when a script uses `${PIPESTATUS[0]}` with `grep -v` filtering, or ends on a failing `grep` under set -e style chains. Write a throwaway script to /tmp, run `bash file`, then delete it.
