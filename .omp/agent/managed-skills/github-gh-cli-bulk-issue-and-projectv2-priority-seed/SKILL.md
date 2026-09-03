---
name: github-gh-cli-bulk-issue-and-projectv2-priority-seed
description: "Use when bulk-creating GitHub issues from a spreadsheet/table (e.g. a feature breakdown doc) via gh CLI and adding them to a GitHub Projects (v2) board with a Priority field — covers checking/refreshing gh auth scopes for project access, creating a missing ProjectV2SingleSelectField via gh project field-create, the exact gh project item-add + gh project item-edit --field-id --single-select-option-id flow (needs the project's node ID, not its number), handling transient GraphQL \"TLS handshake timeout\" and \"Content already exists in this project\" errors with retries, and the off-by-one slicing bug that silently skips one row when resuming a batch script after a partial failure (always verify final count via a title diff against the source list, not just trusting the last printed line)."
---

## Context
Task: turn a table of N features (title, description, owner, size, priority) into GitHub issues in a repo, each added to an org Projects-v2 board with a Priority field set to match.

## Auth
`gh` may be logged in but missing project scopes:
```
gh project field-list 2 --owner ORG   # errors: missing required scopes [read:project]
gh auth refresh -s read:project,project -h github.com   # device-flow, needs user to open browser
```
Run this refresh check first — don't discover it mid-batch.

## Project setup
- List existing fields: `gh project field-list <num> --owner ORG`
- If no Priority field exists, create one:
  ```
  gh project field-create <num> --owner ORG --name "Priority" --data-type SINGLE_SELECT --single-select-options "P0,P1,P2"
  ```
- Get the project's **node ID** (not the display number) and the new field's ID + option IDs:
  ```
  gh project view <num> --owner ORG --format json | jq -r '.id'
  gh project field-list <num> --owner ORG --format json | jq -r '.fields[] | select(.name=="Priority")'
  ```
- Also create repo labels for priorities/epics/sizes as needed (`gh label create NAME -R repo -c "#hex" -f`).

## Per-issue flow
```bash
url=$(gh issue create -R "$REPO" -t "$title" -b "$body" -l "$labels" -a "$assignees")
item_id=$(gh project item-add "$PROJECT_NUM" --owner "$OWNER" --url "$url" --format json | jq -r '.id')
gh project item-edit --id "$item_id" --project-id "$PROJECT_ID" \
  --field-id "$PRIORITY_FIELD_ID" --single-select-option-id "$OPT_ID"
```
`item-edit` needs the **project's node ID** via `--project-id`, separate from `--id` (the item's own node ID).

## Reliability
`gh project item-add`/`item-edit` calls transiently fail with `net/http: TLS handshake timeout` or (on retry) `Content already exists in this project`. Wrap both calls in a retry loop (3-5 attempts, short sleep); the "already exists" error on retry usually means the first attempt actually succeeded — look it up via `gh project item-list --format json` instead of assuming failure.

## Verifying a resumed batch
When a batch script dies partway and you resume by slicing the remaining rows out of a JSON array, it's very easy to off-by-one and skip exactly one row (e.g. slicing `.[N:]` when the last successfully-processed index was `N-1`, not `N`, because the failure happened on the *next* call after "Created: ..." printed for row `N`).

Don't trust running totals. After the whole batch finishes, always diff the full expected title list against what's actually in the repo:
```bash
gh issue list -R REPO --state all --limit 100 --json title | jq -r '.[].title' | sort > created.txt
jq -r '.[].title' expected.json | sort > expected.txt
diff expected.txt created.txt
```
And confirm project item count matches issue count, and no project item has a null Priority:
```bash
gh project item-list <num> --owner ORG --format json --limit 100 | jq -r '.items | length'
gh project item-list <num> --owner ORG --format json --limit 100 | jq -r '.items[] | select(.priority == null) | .content.title'
```
(Note: `gh project item-list --format json` output is `{items: [...], totalCount}` — `jq length` on the raw object gives the wrong number; use `.items | length`.)

## Gotchas
- Doc header counts (e.g. "42 features") can be off from the actual row count — trust the parsed row count from the source table, not the header claim.
- Map named owners to GitHub usernames explicitly; skip/omit assignees the user says to leave out rather than guessing.
- Verify candidate usernames exist before batch-assigning: `gh api users/<login> --jq '.login'`.
