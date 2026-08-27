---
name: gitlab-mr-stuck-preparing-fix-sidekiq-restart
description: "Use when a self-hosted GitLab (Docker/gitlab-ee container) merge request is stuck with merge_status \"checking\" / detailed_merge_status \"preparing\" (prepared_at null) indefinitely, and glab/API merge attempts return 405 Method Not Allowed — restarting Sidekiq inside the gitlab-ee container clears the stuck background job. Also covers verifying branch ancestry with git before force-pushing to avoid destroying already-merged work, and checking GitLab push-mirror status via the remote_mirrors API."
---

## Symptom
- `glab mr merge <N>` or the GitLab web UI merge button hangs on "Your merge request is almost ready!" indefinitely.
- API check shows:
  ```
  glab api projects/<owner>%2F<repo>/merge_requests/<N> --hostname <host> \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['merge_status'], d['detailed_merge_status'], d['prepared_at'])"
  ```
  returns `checking preparing None` and stays that way across retries/nudges (editing title, posting a note, fetching `/changes`) — none of that unsticks it. Direct merge attempts (`glab mr merge` or `PUT .../merge`) return `405 Method Not Allowed`.
- Not draft, no conflicts, discussions resolved, no unmet approval rule — it's a stuck GitLab background job (MR "preparing" worker), not a real merge blocker.

## Fix (self-hosted GitLab in Docker/gitlab-ee container)
On the host running the container (find via `docker ps | grep -i gitlab`, container is commonly named `gitlab-ee`):
```
docker exec -it gitlab-ee gitlab-ctl restart sidekiq
```
Wait ~15-30s, then re-check merge_status via the API call above. If GitLab itself becomes briefly slow/unresponsive right after (SSH banner timeouts, API calls hanging) that's normal load-related — wait 1-2 min for it to settle, it usually clears the "preparing" state once Sidekiq catches up and often auto-merges the MR if merge-on-success was set, or becomes mergeable via the normal merge button/API.

If `gitlab-rails runner` commands (e.g. to inspect Sidekiq::Queue sizes) are needed for deeper diagnosis, expect a 30-90s cold Rails boot — that's normal, not itself evidence of a hang.

## Critical safety check before any "force push branch X onto main" request
NEVER force-push based on the assumption that a feature/working branch is "ahead" of main without verifying ancestry first — the assumption is often wrong (e.g. an MR merged in the background while you were investigating something else, making main already contain everything from the branch plus more).

```
git clone --bare https://<host>/<owner>/<repo>.git /tmp/repo-mirror
cd /tmp/repo-mirror
git log --oneline main..<branch> | wc -l   # commits unique to <branch>, not yet in main
git log --oneline <branch>..main | wc -l   # commits main has that <branch> lacks
git merge-base --is-ancestor <branch> main && echo "already merged into main"
```
If `main..<branch>` is 0 and `<branch>` is an ancestor of `main`, there is nothing to force-push — main is already the more advanced branch, and a force push would be a no-op at best or destroy newer main-only commits at worst. Report this back instead of proceeding blindly, even under user pressure to "just force push it."

Credential note: if `glab auth login` was used, git already has a credential helper wired per-host (check `git config --global --get-regexp credential`) — plain `git clone https://<host>/<owner>/<repo>.git` works non-interactively without manually extracting the PAT from `~/.config/glab-cli/config.yml`.

## Verifying an auto push-mirror after resolving
```
glab api projects/<owner>%2F<repo>/remote_mirrors --hostname <host>
```
Check `update_status: "finished"`, `last_error: null`, and `last_successful_update_at` is recent — confirms the mirror (e.g. GitLab → GitHub) picked up the change without needing manual intervention.
