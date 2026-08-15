---
name: github-mcp-create-file-content-plaintext
description: "Use when calling the mcp__github_create_or_update_file (or equivalent GitHub MCP file-write) tool — its content field takes raw plain text, not base64; the tool base64-encodes internally. Also relevant when a committed file that should be YAML/JSON/text instead shows up on GitHub as a base64-looking blob, or a config parser fails with an error like \"root of X must be a mapping\" right after a file was pushed via this tool."
---

## Symptom

After pushing a file via `mcp__github_create_or_update_file`, the committed file's content
on GitHub is a long base64-looking string instead of the real text (e.g. YAML/JSON), and a
consumer that parses it fails with something like:

```
schema error: root of <file> must be a mapping
```

or `yaml.safe_load` returns a plain string instead of a dict.

## Cause

`mcp__github_create_or_update_file`'s `content` parameter is **plain text** — the tool
base64-encodes it itself before calling the GitHub Contents API. If you pre-encode the
content yourself (e.g. `Buffer.from(text).toString("base64")`) and pass *that* as
`content`, it gets base64-encoded a second time. GitHub stores/decodes it once, so the
resulting file contains the literal base64 string of your original content, not the
content itself.

## Fix

Always pass raw plain text to `content` — never pre-base64-encode it:

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

When updating an existing file, you also need its current blob `sha` (from a prior
`mcp__github_get_file_contents` call or the previous write's response `content.sha`).

## Verifying after a push

Don't trust a raw.githubusercontent.com curl for verification on repos that might be
private or have propagation lag — it can 404 even when the API write succeeded. Instead
re-fetch through the same authenticated path, e.g. `mcp__github_get_file_contents` with
`owner`/`repo`/`path`/`ref`, and check its `content` field (already base64-decoded in the
response) matches what you intended, then parse/validate it locally against whatever
schema the consumer expects before considering the push done.
