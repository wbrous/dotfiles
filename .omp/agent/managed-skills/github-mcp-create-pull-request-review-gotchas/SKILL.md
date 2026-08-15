---
name: github-mcp-create-pull-request-review-gotchas
description: "Use when calling the mcp__github_create_or_update_file's sibling tool mcp__github_create_pull_request_review (or GitHub MCP \"create_pull_request_review\") to post a PR review with inline \\\\\\suggestion blocks — covers the exact param names/shapes and the commit SHA requirement that differ from what the tool's own error-echoed \"normalized\" args imply."
---

## Symptom
Calling `xd://mcp__github_create_pull_request_review` fails with either:
- `pull_number: is required` even though you passed `pullNumber` (camelCase) — the tool wants **snake_case** `pull_number`, not `pullNumber`.
- `comments/N/position: is required` even though you passed `line` + `side` — the schema is a union: either `{path, position, body}` (diff position) or `{path, line, body}` (file line number). Passing `side` alongside `line` is fine to omit; just don't mix `position` expectations. Prefer the `{path, line, body}` variant — it maps to a real file line number, easier to compute from a fetched diff.
- `Variable $commitOID of type GitObjectID was provided invalid value` — `commit_id` needs the **full 40-char SHA**, not a short/abbreviated one (e.g. from `git log --oneline`). Get it via `git rev-parse <branch-or-short-sha>`.

## Correct shape
```json
{
  "owner": "org",
  "repo": "repo",
  "pull_number": 18,
  "commit_id": "a7aced81f8ceec0842b9bb8122213e57fad2a971",
  "event": "COMMENT",
  "body": "overall review summary",
  "comments": [
    {
      "path": "bot/src/foo.ts",
      "line": 100,
      "body": "explanation...\n```suggestion\n  replacement code line(s)\n```"
    }
  ]
}
```

## Notes
- `line` refers to the line number in the **new** file version (post-diff), matching what you'd read via `pr://<owner>/<repo>/<N>/diff/<i>` or `read pr://.../diff/<i>` with line numbers derived from hunk headers (`@@ -a,b +c,d @@` → new lines start at `c`).
- `event: "COMMENT"` posts non-blocking feedback; use `REQUEST_CHANGES`/`APPROVE` for gating reviews.
- A `\`\`\`suggestion` fenced code block inside a comment `body` renders as a GitHub one-click-apply suggestion; content inside the fence must be the literal replacement text for the commented line(s), not a diff.
