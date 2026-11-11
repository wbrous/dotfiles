# GitHub MCP: file writes and PR reviews

Scope: two parameter-shape gotchas in the GitHub MCP tools that corrupt content or reject valid calls.

## `create_or_update_file`: `content` is plaintext, not base64

**Symptom:** after pushing via `mcp__github_create_or_update_file`, the committed file on GitHub is a long base64-looking string instead of real text (e.g. YAML/JSON), and a consumer fails with something like `schema error: root of <file> must be a mapping` or `yaml.safe_load` returns a plain string instead of a dict.

**Cause:** the tool's `content` parameter is **plain text** — the tool base64-encodes it itself before calling the GitHub Contents API. Pre-encoding (`Buffer.from(text).toString("base64")`) double-encodes; GitHub decodes once, leaving the literal base64 string in the file.

**Fix:** always pass raw text with real newlines:

```json
{
  "owner": "org",
  "repo": "repo",
  "path": "path/to/file.yml",
  "branch": "main",
  "message": "...",
  "content": "raw text here, e.g. actual YAML with real newlines"
}
```

Updating an existing file also needs its current blob `sha` (from a prior `mcp__github_get_file_contents` call or the previous write's `content.sha`).

**Verifying:** don't trust a raw.githubusercontent.com curl (private repos or propagation lag 404 even when the write succeeded). Re-fetch through the same authenticated path (`mcp__github_get_file_contents` with `owner`/`repo`/`path`/`ref`), check its `content` field matches intent, then parse/validate locally against the consumer's schema before considering the push done.

_Migrated from: github-mcp-create-file-content-plaintext_

## `create_pull_request_review`: snake_case params, line variant, full SHA

**Symptom:** calling `xd://mcp__github_create_pull_request_review` fails with `pull_number: is required` (despite passing camelCase `pullNumber`), `comments/N/position: is required` (despite passing `line` + `side`), or `Variable $commitOID of type GitObjectID was provided invalid value`.

**Cause:** the schema differs from what the tool's own error-echoed "normalized" args imply:
- The tool wants snake_case **`pull_number`**, not `pullNumber`.
- The comment schema is a union: `{path, position, body}` (diff position) OR `{path, line, body}` (file line number). Don't mix `position` expectations into the `line` variant; omitting `side` alongside `line` is fine. Prefer `{path, line, body}` — maps to a real new-file line number, computable from hunk headers (`@@ -a,b +c,d @@` → new lines start at `c`) in `pr://<owner>/<repo>/<N>/diff`.
- `commit_id` needs the **full 40-char SHA**, not a short one from `git log --oneline`. Get it via `git rev-parse <branch-or-short-sha>`.

**Correct shape:**

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

`event: "COMMENT"` posts non-blocking feedback; `REQUEST_CHANGES`/`APPROVE` for gating reviews. A ` ```suggestion ` fenced block renders as a one-click-apply suggestion; its contents must be the literal replacement text for the commented line(s), not a diff.

_Migrated from: github-mcp-create-pull-request-review-gotchas_
