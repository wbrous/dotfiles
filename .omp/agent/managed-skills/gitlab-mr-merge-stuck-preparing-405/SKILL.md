---
name: gitlab-mr-merge-stuck-preparing-405
description: "Use when glab mr merge (or GitLab merge_requests/:iid/merge API) returns \"405 Method Not Allowed\" on a self-hosted GitLab instance, and the MR's detailed_merge_status is stuck at \"preparing\" / merge_status \"checking\" with prepared_at null — indicates a stuck server-side Sidekiq background job, not a client-fixable condition (not draft, no conflicts, discussions resolved)."
---

## Symptom
`glab mr merge <iid> --repo <url> --yes` (or raw `PUT .../merge_requests/:iid/merge`) fails:
```
PUT .../merge_requests/11/merge: 405 {message: 405 Method Not Allowed}
```

## Diagnose
```bash
glab api projects/<owner>%2F<repo>/merge_requests/<iid> --hostname <host> \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['merge_status'], d['detailed_merge_status'], d['prepared_at'])"
```
If output is `checking preparing None` — GitLab has not finished computing whether the MR can be merged. This is an async server-side job (MR "prepare" worker via Sidekiq). `draft`, `has_conflicts`, `blocking_discussions_resolved` may all look fine; that's irrelevant, the 405 is purely because prep never completed.

## What does NOT fix it (client-side, all no-ops observed)
- Retrying `glab mr merge` after waiting (even 30s+)
- Hitting `GET merge_requests/:iid/changes` to force diff computation
- `glab mr update` (title/description edit) to nudge a recompute
- No `glab` flag bypasses `detailed_merge_status` gating

## Actual fix
Server-side only — needs GitLab instance admin access:
- Restart Sidekiq (`gitlab-ctl restart sidekiq` or equivalent) on the instance
- Check Sidekiq queue backlog/dead jobs for the merge-request prepare worker
- If self-hosted via Docker/omnibus, check container health/logs for stuck job processing

## When reporting to user
State clearly: this is not fixable via glab/API from the client; requires instance-side Sidekiq restart or backlog investigation. Don't keep retrying the merge call after confirming `prepared_at: null` persists — it won't change without server intervention.
