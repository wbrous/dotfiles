---
name: watermarks-remover-frontmatter-value-false-positive
description: "Use when a global git pre-commit hook (watermarks-remover) reports \"AI/C2PA provenance marks\" / \"AI-generator metadata present\" on a markdown file (e.g. an agent SKILL.md) and blocks or loops on dotfiles commit/git commit, especially when mode=clean keeps \"cleaning\" the same files on every retry, or a frontmatter field (like description:) gets fully deleted after cleaning."
---

## Two distinct bugs in watermarks-remover (repo: `~/Documents/Development/watermarks-remover`, vendored to `~/.local/share/watermarks-remover` — keep both in sync, they must stay byte-identical for `service/scripts/*.py`)

### Bug 1: frontmatter value false positive destroys legitimate fields
`container_meta.py`'s `inspect_markdown`/`clean_markdown` scanned **every** top-level
frontmatter key's *value* against `AI_META_NAME_RE` (bare substrings like
`claude|gemini|openai|anthropic|copilot|...`). A long prose field — e.g. a skill's
`description:` that legitimately *talks about* AI tools/config files by name (not
actual AI-generation provenance) — trips this, and `clean_markdown` then **deletes
the entire frontmatter key**, not just the offending substring. This is real data
loss (skill `description` drives discovery — see `skill-location-convention`-style
skills).

Fixed via `_is_provenance_tag_value(val)` in `container_meta.py`: only treat a value
hit as real if the value is short/tag-like (`<= 6` words after stripping quotes) —
real generator/provenance metadata values are short tags (`"ChatGPT"`,
`"Adobe Firefly 2"`), not full sentences. Verified: still catches
`tool: "OpenAI"` (true positive), no longer catches a `description:` sentence that
merely mentions "gemini"/"claude"/"copilot" as subject matter.

Note: `AI_META_NAME_RE` doesn't include "chatgpt" as a bare token (only "openai") —
a separate pre-existing gap, not touched by this fix.

### Bug 2: `clean_staged.py` reports "changed" forever, even on already-clean files
`_changed(result)`'s fallback (used when `result` has no `"stats"` key — true for
every image/AV/container result) was `bool(result.get("actions"))`. But
`clean_file.py` always emits a non-empty `actions` list for these kinds, including a
no-op placeholder string (`"no AI frontmatter keys or embedded data URIs removed"`)
when nothing actually changed. So `mode=clean` pre-commit hook exits 1 and reports
"cleaned N files" **every single run**, regardless of whether anything was really
rewritten — an infinite commit-blocked loop (`git add` + recommit never converges).

Fixed by comparing `bytes_in != bytes_out` (present on every image/AV/container
result) instead of the non-empty-actions heuristic, falling back to the old
`bool(actions)` only when byte counts aren't present (e.g. `stats`-based text kind
already handled by the `stats` branch above it).

## Diagnosis recipe for a stuck "cleaned N files" loop
1. `export WATERMARKS_REMOVER_HOME=~/.local/share/watermarks-remover` (needed in a
   fresh shell — the hook sources it from `~/.config/watermarks-remover/global-hooks.conf`,
   but that doesn't persist to your own manual invocations).
2. `python3 "$WATERMARKS_REMOVER_HOME/service/scripts/check_staged.py" <path>...`
   after manually `git add`ing the "cleaned" files — if this now exits 0, the files
   really are clean and the loop is bug 2 (compare `bytes_in`/`bytes_out` from
   `clean_file.py --in-place --json <path>` directly to confirm: identical bytes but
   non-empty/no-op `actions` = bug 2 firing).
3. `git diff HEAD -- <path>` on a flagged file to see exactly what got stripped — a
   frontmatter key vanishing entirely (not just a substring redacted) is bug 1;
   recover the field's prior content via `git show HEAD:<path>` and manually
   reinsert it (updating for any newer body content if the file has since evolved).

## Recovery workflow after hitting bug 1
Restore the destroyed frontmatter field from `git show HEAD:<path>`, but check the
file's *body* hasn't materially evolved since that commit (`diff` HEAD's body vs
current working-tree body) — if it has, the restored field should reflect the
current content, not be pasted back verbatim stale.
