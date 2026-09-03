---
name: github-gh-cli-bulk-issue-and-projectv2-priority-seed
description: "Use when bulk-creating GitHub issues from a spreadsheet/table (e.g. a feature breakdown doc) via gh CLI and adding them to a GitHub Projects (v2) board with Priority and/or Team single-select fields — covers checking/refreshing gh auth scopes for project access, creating a missing ProjectV2SingleSelectField via gh project field-create, repurposing/seeding an existing single-select field's options (e.g. generic \"Squad 1/2/3\" → real person names) via the updateProjectV2Field GraphQL mutation (which replaces the entire options list — no CLI equivalent), the exact gh project item-add + gh project item-edit --field-id --single-select-option-id flow (needs the project's node ID, not its number), handling transient GraphQL \"TLS handshake timeout\" and \"Content already exists in this project\" errors with retries, the off-by-one slicing bug that silently skips one row when resuming a batch script after a partial failure (always verify final count via a title diff against the source list, not just trusting the last printed line), bulk-renaming issue titles afterward with gh issue edit -t (e.g. stripping numeric feature-code prefixes and adding a [FEAT] tag) while keeping category signaled via a separate epic/category label, and assigning a project single-select field per issue to a \"primary owner\" (first name in a slash-separated owner cell) even when that person has no GitHub account yet (fine for a project field value — only a GitHub assignee requires an account)."
---

## Context

Task: turn a spreadsheet-style feature breakdown (Title/Description/Owner/Size/Priority columns, sometimes multiple owners like "Carter Alfers/Andre Hamghalam") into GitHub issues in a repo, then add them all to a GitHub Projects v2 board with structured fields — repeated across two related requests (seed issues+priority, then reshape titles+add a Team field).

## Auth prerequisite

`gh project *` commands need the `read:project`/`project` scopes, which a default `gh auth login` token often lacks:

```
gh project view 2 --owner ORG
# error: your authentication token is missing required scopes [read:project]
gh auth refresh -s read:project,project -h github.com   # opens device-code flow, run in a PTY
```

## Discover project fields and IDs

```
gh project view 2 --owner ORG --format json | jq -r '.id, .number'   # project node ID, e.g. PVT_...
gh project field-list 2 --owner ORG --format json                     # field IDs + types
```

## Creating a new single-select field (e.g. Priority)

```
gh project field-create 2 --owner ORG --name "Priority" --data-type SINGLE_SELECT \
  --single-select-options "P0,P1,P2"
gh project field-list 2 --owner ORG --format json | jq -r '.fields[] | select(.name=="Priority")'
# → grab the field ID and each option's ID
```

## Repurposing/seeding an EXISTING single-select field's options

No CLI subcommand edits options on an existing field — `gh project field-create` only creates new fields. Use the `updateProjectV2Field` GraphQL mutation directly; it **replaces the entire options list** (can't append):

```
gh api graphql -f query='
mutation {
  updateProjectV2Field(input: {
    fieldId: "PVTSSF_...",
    name: "Team",
    singleSelectOptions: [
      {name: "Wils Brous", color: BLUE, description: ""},
      {name: "Ayden Yang", color: GREEN, description: ""},
      {name: "Carter Alfers", color: ORANGE, description: ""},
      {name: "Andre Hamghalam", color: PURPLE, description: ""}
    ]
  }) {
    projectV2Field {
      ... on ProjectV2SingleSelectField { id options { id name } }
    }
  }
}'
```

This is exactly how a generic "Squad 1/2/3" placeholder field became a real per-person "Team" field. A project single-select option can name someone with **no GitHub account** (e.g. "Andre Hamghalam") — it's just a label value, unlike a GitHub issue `assignee` which requires a real account and will fail if you try to assign a nonexistent user.

To discover valid option-input fields/colors before writing the mutation: `gh api graphql -f query='query { __type(name: "ProjectV2SingleSelectFieldOptionInput") { inputFields { name type { name kind ofType { name kind } } } } }'`.

## Bulk create + add-to-project + set-field loop

Build one JSON array of row objects (title, body, labels, assignees, size, priority, epic/category) with a script (Python is fine), then drive `gh` from a bash loop over `jq -c '.[]'`:

```bash
url=$(gh issue create -R "$REPO" -t "$title" -b "$body" -l "$labels" -a "$assignees")
item_id=$(gh project item-add "$PROJECT_NUM" --owner "$PROJECT_OWNER" --url "$url" --format json | jq -r '.id')
gh project item-edit --id "$item_id" --project-id "$PROJECT_ID" \
  --field-id "$PRIORITY_FIELD_ID" --single-select-option-id "$opt_id"
```

Note `gh project item-edit` wants the **project's node ID** (`PVT_...`), not its number — different from most other `gh project` subcommands which take `--owner`+number.

### Reliability

- Expect transient failures mid-batch: `Post "https://api.github.com/graphql": net/http: TLS handshake timeout` and `GraphQL: Content already exists in this project (addProjectV2ItemById)` (the latter can fire even on a genuinely-new add — just means it succeeded despite the error, or a retry landed twice; check `gh project item-list` to confirm before retrying that item).
- Wrap `item-add` and `item-edit` calls each in a small retry loop (e.g. 5 attempts, 2s sleep) rather than treating one failure as fatal.
- **Resuming a batch after a partial failure is the highest-risk step.** It's easy to off-by-one the resume slice (e.g. skip the row that failed, or skip the row *after* it, or double-process the one that "looked like" it failed but actually succeeded). After a batch finishes, always verify: `gh issue list --json title | jq -r '.[].title' | sort` diffed against the source list's titles (after stripping any prefix you added) — don't trust the last printed line of a background job as proof of completeness. This caught a real skipped row (`2.5 Installation monitor`) in production use.

## Bulk-editing titles afterward

`gh issue edit N -R REPO -t "new title"` renames one issue. To strip a numeric feature-code prefix ("1.1 Foo bar" → "[FEAT] Foo bar") across many issues, build a number→new-title map (matching by *old* title text against your original source JSON, not by assuming issue-number-equals-array-index — numbers can shift if any issue was created out of order during a resumed batch) and loop with the same retry pattern as above.

When a title's numeric/category prefix is removed, make sure the category is still discoverable — e.g. via a persistent `epic:<slug>` (or similar) label applied at issue-creation time, not encoded in the title text.

## Verifying full coverage of a project field

```
gh project item-list 2 --owner ORG --format json --limit 100 | jq -r '.items[] | select(.<fieldNameLower> == null) | .content.title'
```
Empty output = every item has that field set. (Note: `gh project item-list` JSON wraps items under `.items` with a sibling `.totalCount` — `jq '. | length'` on the raw object gives 2, not the item count; use `.items | length`.)
