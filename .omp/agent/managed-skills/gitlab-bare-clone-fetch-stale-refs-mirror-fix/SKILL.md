---
name: gitlab-bare-clone-fetch-stale-refs-mirror-fix
description: "Use when using a git clone --bare (or --mirror) checkout as a scratch working copy to sync/force-push branches between GitLab and GitHub (or any two remotes) — especially when re-running git fetch origin in that bare clone appears to succeed (\"branch HEAD - FETCH_HEAD\") but local branch refs (main, dev, etc.) silently stay stale, causing a subsequent force-push to the destination remote to regress branches to older commits. Also covers diagnosing/recovering a stuck self-hosted GitLab (Docker gitlab-ee) push mirror via Sidekiq restart and manual API sync trigger."
---

## Problem
A plain `git clone --bare <url> dir` does NOT configure `remote.origin.fetch` with the
standard `+refs/heads/*:refs/remotes/origin/*` refspec the way a normal clone does.
Because it's bare, local `refs/heads/*` ARE the "remote" copy — but a bare clone's default
fetch refspec often only updates `FETCH_HEAD`, not the local branch refs, on a later
`git fetch origin` with no explicit refspec. Symptom: `git fetch origin` prints only
`* branch  HEAD -> FETCH_HEAD` (no `branchname -> origin/branchname` lines), and
`git rev-parse main dev ...` still shows old SHAs even though the real remote has moved on.

If you then force-push those stale local refs to a second remote (e.g. mirroring
GitLab -> GitHub), you silently **regress** the destination branches to older commits.

## Fix / safe pattern
- NEVER trust refs in a bare clone after a bare `git fetch origin` with no refspec.
- Before any cross-remote sync push, re-verify against ground truth:
  `git ls-remote <source-url>` and compare SHAs to your bare clone's `git rev-parse <branches>`.
- Safest approach: delete and re-clone `--bare` fresh right before the sync push, rather than
  reusing + fetching an existing bare clone. A fresh `--bare` clone's initial ref set IS
  accurate (the staleness only appears on a *subsequent* `fetch origin` in that same clone).
- After pushing to the destination remote, confirm with
  `git ls-remote <dest-url> refs/heads/<branch>...` and diff against the source ls-remote output.

## Related: stuck GitLab push mirror (self-hosted, Docker gitlab-ee)
Symptom: pushed to GitLab, but the "auto mirror" (Settings > Repository > Mirroring
Repositories, or `GET /projects/:id/remote_mirrors`) shows `update_status: finished` with a
`last_update_at` timestamp OLDER than your latest push — the mirror sync job never re-ran.
- Trigger manually: `POST /projects/:id/remote_mirrors/:mirror_id/sync` (via `glab api -X POST`).
  If the timestamp still doesn't move after several seconds, the Sidekiq queue itself is stuck.
- Restart Sidekiq in the container: `docker exec -it gitlab-ee gitlab-ctl restart sidekiq`.
- If that alone doesn't clear a stuck MR `detailed_merge_status: preparing` (same underlying
  Sidekiq backlog class of issue), see skill `gitlab-mr-stuck-preparing-fix-sidekiq-restart`.
- If the mirror job is still slow/queued and you need the destination remote updated NOW,
  bypass the mirror: fresh `--bare` clone the source, then
  `git push <dest-url> branch1:branch1 branch2:branch2 ... --force --porcelain` and verify with
  `ls-remote` on both sides as above.
