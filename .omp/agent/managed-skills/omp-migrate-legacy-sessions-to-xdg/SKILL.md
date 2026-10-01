---
name: omp-migrate-legacy-sessions-to-xdg
description: "Migrate old omp sessions, blobs and prompt history from ~/.omp/agent/ into ~/.local/share/omp/ without clobbering the new install."
---

# Migrate legacy omp sessions to ~/.local/share/omp/

Old layout: `~/.omp/agent/{sessions,blobs,history.db}`. New layout: `~/.local/share/omp/{sessions,blobs,history.db}`. Both use `sessions/<cwd-slug>/<ts>_<uuid>.jsonl` plus a same-named artifact dir, so the trees merge directly.

## Procedure
1. Inspect both trees. Use `LC_ALL=C` for `sort`/`comm`; the `-` slug breaks default-locale sort order. Check for slug and filename collisions (UUID-named files normally do not collide).
2. Copy without overwriting, then verify by checksum:
   - `cp -an --reflink=auto OLD/. NEW/` for `sessions` and `blobs`
   - `cd OLD && find . -type f -print0 | sort -z | xargs -0 sha256sum > /tmp/x.sha; cd NEW && sha256sum -c --quiet /tmp/x.sha`
3. Merge `history.db` (do NOT copy over it). The new schema has extra `use_count` and `session_recaps`. Back up first: `sqlite3 "file:NEW?mode=ro" ".backup /tmp/history.db.pre-migrate.bak"`. Then `ATTACH` the old DB read-only and run, in one `BEGIN IMMEDIATE` transaction:
   - `INSERT OR IGNORE INTO session_titles(session_id,title,updated_at) SELECT ... FROM old.session_titles;`
   - `INSERT OR IGNORE INTO history(prompt,created_at,cwd,session_id) SELECT ... FROM old.history ORDER BY id;` (`prompt` is UNIQUE; the `history_ai` trigger keeps the FTS index in sync)
   Verify: `history_fts` count equals `history`, `pragma integrity_check` is ok, and no old prompts or titles are missing.
4. Smoke test with no model call: `omp --export <migrated .jsonl>` (writes an HTML file to cwd; delete it). `omp --resume <id-prefix>` works, but `--resume` conflicts with `--no-session`.

## Leave alone
- Old `agent.db`, `models.db`, `stats.db`: the new install has its own credentials, settings and usage, so overwriting could break login.
- Do not delete `~/.omp/` contents unless the user asks. `terminal-sessions/` and `predict/` are unmigrated (unknown whether the new version reads them).
