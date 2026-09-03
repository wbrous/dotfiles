---
name: github-gh-cli-bulk-issue-and-projectv2-priority-seed
description: "Use when bulk-creating GitHub issues from a spreadsheet/table (e.g. a feature breakdown doc) via gh CLI and adding them to a GitHub Projects (v2) board with Priority, Team, and/or Status fields — covers checking/refreshing gh auth scopes for project access, creating a missing ProjectV2SingleSelectField via gh project field-create, repurposing/seeding an existing single-select field's options (e.g. generic \"Squad 1/2/3\" → real person names, even people without a GitHub account yet) via the updateProjectV2Field GraphQL mutation (which replaces the entire options list — no CLI equivalent), the exact gh project item-add + gh project item-edit --field-id --single-select-option-id flow (needs the project's node ID, not its number), handling transient GraphQL \"TLS handshake timeout\" and \"Content already exists in this project\" errors with retries (and the off-by-one index-slice bug this can cause when resuming a batch script — always verify final count via a title diff against the source list, not just trusting the last printed line), bulk-renaming issue titles afterward with gh issue edit -t to embed a tag like \"[P0 FEAT]\" combining a category/type marker with a dynamic field value (priority) pulled live from each issue's own labels, and bulk-moving a subset of project items between Status/column values (e.g. \"move everything above P0 into Backlog\") by filtering gh project item-list JSON output on a custom field value and looping gh project item-edit over the matching item IDs."
---

## Prereqs

`gh auth refresh -s read:project,project -h github.com` (interactive device-flow, needs user to complete in browser) before any `gh project` command — the default gh token usually lacks `read:project`.

## Get project + field IDs (once)

```
gh project view <NUM> --owner <ORG> --format json | jq -r '.id'          # project node ID (PVT_...)
gh project field-list <NUM> --owner <ORG> --format json                   # field IDs + option IDs
```

## Create a missing single-select field (e.g. Priority)

```
gh project field-create <NUM> --owner <ORG> --name "Priority" \
  --data-type SINGLE_SELECT --single-select-options "P0,P1,P2"
gh project field-list <NUM> --owner <ORG> --format json | jq '.fields[] | select(.name=="Priority")'
```

## Repurpose/seed an EXISTING single-select field's options (e.g. Team)

`gh project field-create`/`field-edit` cannot touch options on an existing field. Use the GraphQL mutation directly — it REPLACES the entire options list, so include every option you want to keep:

```
gh api graphql -f query='
mutation {
  updateProjectV2Field(input: {
    fieldId: "PVTSSF_...",
    name: "Team",
    singleSelectOptions: [
      {name: "Alice", color: BLUE, description: ""},
      {name: "Bob", color: GREEN, description: ""}
    ]
  }) {
    projectV2Field { ... on ProjectV2SingleSelectField { id options { id name } } }
  }
}'
```
People without a GitHub account are still valid option values here — it's a project field, not a GitHub assignee, so add them too.

## Bulk create issues + add to project + set fields

Per issue: `gh issue create -R <repo> -t "<title>" -b "<body>" -l "<labels>" -a "<assignees>"` → capture the returned URL → `gh project item-add <NUM> --owner <ORG> --url "$url" --format json | jq -r '.id'` → `gh project item-edit --id "$item_id" --project-id "$PROJECT_ID" --field-id "$FIELD_ID" --single-select-option-id "$OPT_ID"`.

Wrap every `gh project item-add`/`item-edit` call in a retry loop (3-5 attempts, `sleep 2`) — transient `TLS handshake timeout` and `Content already exists in this project` errors are common under batch load and otherwise abort the whole script mid-run.

**Off-by-one trap when resuming after a failure**: if you slice the remaining-items JSON to skip already-processed rows, count carefully — it's easy to skip one extra row (the one that failed) instead of one fewer. After a full batch run, always diff the created issue titles against the full source list (`diff <(jq -r '.[].title' source.json | sort) <(gh issue list ... --json title | jq -r '.[].title' | sort)`) rather than trusting the last printed status line.

## Rename titles to embed a dynamic tag (e.g. "[P0 FEAT]")

Read priority back from each issue's own labels (not from the original static source data, in case it changed) so the tag stays accurate, then bulk `gh issue edit <num> -R <repo> -t "<new title>"`:

```py
labels = [l["name"] for l in issue["labels"]]
prio = next(l for l in labels if l in ("P0","P1","P2"))
new_title = f"[{prio} FEAT] {desc}"
```

## Bulk-move items between Status/column values by a custom-field filter

`gh project item-list <NUM> --owner <ORG> --format json --limit 100` returns each item's custom field values flattened onto the item object (e.g. `.priority`, `.status`) alongside `.content.title`/`.content.number`. Filter with `jq` then loop `item-edit`:

```
gh project item-list 2 --owner ORG --format json --limit 100 \
  | jq -r '.items[] | select(.priority=="P1" or .priority=="P2") | .id' \
  | while read -r id; do
      gh project item-edit --id "$id" --project-id "$PROJECT_ID" \
        --field-id "$STATUS_FIELD_ID" --single-select-option-id "$BACKLOG_OPT_ID"
    done
```
Verify afterward with `... | jq -r '"\(.status)\t\(.priority)"' | sort | uniq -c` to confirm the split landed cleanly.
