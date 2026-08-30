---
name: vps-fork-subtree-sync-and-console-recovery
description: "Use when syncing a single subfolder of a forked git repo (e.g. python/robomp in a fork of can1357/oh-my-pi) with its upstream source while preserving local-only customizations to files in that folder (e.g. docker-compose.yml env vars/host overrides), especially over SSH password auth (see ssh-password-auth-without-sshpass) on a Docker-compose-based deployment. Also covers recovering SSH access to a VPS after a reboot when ssh/connection refused persists — diagnosing via VNC/console with systemctl (service may be named ssh not sshd on Debian/Ubuntu), checking ufw/iptables, and confirming containers with restart: unless-stopped come back on their own."
---

## Syncing one subfolder of a fork from upstream, preserving local edits

Scenario: a private/internal fork (e.g. `zep-dev-ai/oh-my-pi`) tracks a public
upstream (`can1357/oh-my-pi`), but only wants a specific subdirectory (e.g.
`python/robomp`) kept in sync — not a full-repo merge, which would risk
unrelated infra files diverging or crashing an in-production self-hosted setup.

Recipe (run in the target checkout, e.g. over SSH on the deployment VPS):

```bash
cd /path/to/fork/checkout

# 1. Commit any pending local changes first so nothing is lost/stashed.
git add path/to/subfolder && git commit -m "..."

# 2. Add upstream if not already present, fetch just the branch you need.
git remote add upstream https://github.com/<owner>/<repo> 2>&1  # ok if already exists
git fetch upstream main

# 3. Sanity check divergence scoped to the subfolder only, not the whole repo.
git log --oneline HEAD..upstream/main -- path/to/subfolder   # upstream-only commits
git log --oneline upstream/main..HEAD -- path/to/subfolder   # local-only commits
# If local-only commits are just re-authored copies of the same upstream
# commits (fork-sync bots often rewrite author), there's nothing to actually
# preserve beyond what upstream now has — don't try to cherry-pick them back.

# 4. Overwrite ONLY that subfolder with the upstream version. This never
#    touches any other file in the repo, unlike `git merge upstream/main`.
git checkout upstream/main -- path/to/subfolder
git status --short   # review the full list of touched files before committing

# 5. Reapply any *real* local customizations that lived inside that subfolder
#    (e.g. docker-compose.yml env var passthroughs, extra_hosts IP pins) —
#    diff the pre-sync version against the new upstream version, and
#    hand-reapply just the meaningful hunks. A python str.replace() one-liner
#    over SSH works fine for small, well-anchored edits.

git add path/to/subfolder && git commit -m "sync: update from upstream"
```

Verification before declaring done, scaled to what's actually runnable:
- `python3 -m py_compile` (or equivalent) on changed source files — catches
  syntax errors before a container build wastes time.
- `docker compose config -q` — validates compose YAML actually parses.
- Check any new env-var references introduced by the upstream diff
  (`grep -oE 'ROBOMP_[A-Z_]+' src/config.py`) have safe defaults, or fail the
  build/rebuild loudly and cheaply rather than surprise at runtime.
- Rebuild (`docker compose build`) and confirm the new image actually
  contains upstream's new files: `docker run --rm --entrypoint sh <image> -c
  'ls path/to/new/file; grep -c new_symbol path/to/file'`. BuildKit layer
  caching can make a build look instant even when it did pick up new
  content — verify by inspecting the built image, not just build-log noise.
- `docker compose up -d --force-recreate <service...>` to actually redeploy,
  then tail logs for clean startup and hit the real HTTP endpoint
  (`curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:<port>/`) as the
  smoke test — don't just trust "Started" from `docker ps`.

## Recovering VPS SSH access after a reboot ("connection refused")

Symptom: SSH client gets `Connection refused` on port 22 (not a timeout —
distinguishes it from a firewall dropping packets or the host being fully
down; the host itself is up and reachable via `ping`). This means nothing is
listening on 22 — either sshd isn't running yet, or it crashed, or it's
gated by a firewall that actively rejects instead of drops. If the user
reboots the box (e.g. via provider console) mid-session, this is expected to
flap for a bit and self-resolve; poll rather than escalate immediately, but
if it doesn't come back within a couple minutes have the user get on the
provider's VNC/serial console since network-based diagnosis is impossible
once SSH itself is the thing that's down.

Once on the console (logged in as root), don't assume the systemd unit name:

- Debian/Ubuntu-family: `systemctl status ssh` (NOT `sshd` — `systemctl
  status sshd` returns "Unit sshd.service could not be found" even when
  openssh-server is installed and running fine, because the unit is just
  named `ssh`).
- RHEL/Fedora-family: `systemctl status sshd` is correct there.

Diagnostic sequence:
```bash
systemctl status ssh              # or sshd — try the other name if "could not be found"
journalctl -u ssh -n 50 --no-pager
ss -tlnp | grep :22
systemctl restart ssh
ufw status verbose                 # active-with-no-22-rule, or default-deny, blocks even a running sshd
ufw allow 22/tcp && ufw reload     # if that's the culprit
iptables -L INPUT -n --line-numbers | head -30   # second firewall layer independent of ufw
```

Containers/services with `restart: unless-stopped` in their compose file
come back on their own after a host reboot without any manual `docker
compose up` — verify with `docker ps --format '{{.Names}}: {{.Status}}'`
rather than assuming they need to be restarted; only force-recreate the ones
you actually changed the image for.
