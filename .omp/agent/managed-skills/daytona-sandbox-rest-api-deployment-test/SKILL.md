---
name: daytona-sandbox-rest-api-deployment-test
description: "Use when running a real end-to-end deployment/provisioning test (e.g. a bootstrap-ubuntu.sh, systemd service install, or Docker Compose stack) against a Daytona sandbox via its REST API — creating a sandbox from a named snapshot, uploading files, executing commands, and tearing down. Also covers the key gotcha: Daytona's default \"container\"-class sandboxes have no init system (PID 1 is daytona, not systemd), so any script step using systemctl will fail there even though apt/Docker/Postgres/etc. install and run fine — this is an environment limitation of the sandbox class, not a bug in the script being tested, and nested Docker (dockerd started as a plain background process) works without systemd."
---

## Context

Daytona (https://app.daytona.io) exposes a REST API for creating ephemeral Linux sandboxes and running commands/files inside them — useful for a genuine smoke-test of a deployment script (e.g. `bootstrap-ubuntu.sh`) on a fresh OS instead of just trusting it will work.

Auth: `Authorization: Bearer dtn_...` on every call.

## Workflow

1. **Find/confirm the snapshot name** (don't guess — list them):
   ```bash
   curl -s 'https://app.daytona.io/api/snapshots' --header "Authorization: Bearer $TOKEN"
   ```
   Look for `"name"` and `"sandboxClass"` (`container`, `vm`, etc.) in the returned items.

2. **Create a sandbox from a snapshot:**
   ```bash
   curl -s 'https://app.daytona.io/api/sandbox' \
     --request POST \
     --header 'Content-Type: application/json' \
     --header "Authorization: Bearer $TOKEN" \
     --data '{"snapshot": "ubuntu-small"}'
   ```
   Returns an `id` immediately with `"state":"creating"`. Poll:
   ```bash
   curl -s "https://app.daytona.io/api/sandbox/$SID" --header "Authorization: Bearer $TOKEN" \
     | python3 -c 'import sys,json;print(json.load(sys.stdin)["state"])'
   ```
   until it's `started` (usually near-instant for container snapshots).

3. **Execute commands** via the Toolbox proxy (NOT the main app.daytona.io host):
   ```bash
   curl -s "https://proxy.app.daytona.io/toolbox/$SID/process/execute" \
     --request POST \
     --header "Authorization: Bearer $TOKEN" \
     --header 'Content-Type: application/json' \
     --data '{"command": "whoami && cat /etc/os-release", "timeout": 15}'
   ```
   Response is `{"exitCode":N,"result":"<stdout+stderr combined>"}`. The `timeout` field is seconds; default 10s if omitted — set it generously (e.g. 180-270) for apt/docker-pull-heavy commands, and also pass `curl --max-time` slightly higher than that so the HTTP client doesn't cut it off first. Long-running installs (apt + Docker + image pulls) can take 30-90s; if your bash tool call itself risks the harness's own timeout, run it as a background job and wait on it rather than polling with `sleep`.

4. **Upload files** (no tar/zip needed for a handful of files, just multipart per-file):
   ```bash
   curl -s -X POST "https://proxy.app.daytona.io/toolbox/$SID/files/upload?path=/opt/myapp/script.sh" \
     --header "Authorization: Bearer $TOKEN" \
     -F "file=@/local/path/script.sh"
   ```
   Directories must be pre-created with a `mkdir -p` exec call first — upload does not auto-create parent dirs. `chmod +x` after upload via another exec call (uploaded files are not executable by default).

5. **Verify uploads and run the target script** exactly as documented for production, then run any smoke-test/round-trip scripts that already exist in the repo (`smoke-test.sh`, `test-backup-restore.sh`, etc.) unmodified against the sandbox — this is the actual value of the test: proving the *documented deployment steps*, not a hand-adapted version of them.

6. **Clean up**: tear down anything you started (`docker compose down -v`, etc.) inside the sandbox via exec, then delete the sandbox:
   ```bash
   curl -s -X DELETE "https://app.daytona.io/api/sandbox/$SID?force=true" --header "Authorization: Bearer $TOKEN"
   ```

## Critical gotcha: no systemd in container-class sandboxes

Daytona's default `container`-class snapshots (e.g. `ubuntu-small`, `daytona-small`) are plain Docker containers, not VMs. `ps -p 1 -o comm=` / `cat /proc/1/comm` reports `daytona`, not `systemd`, and `/run/systemd/system` doesn't exist. Any script step calling `systemctl` (e.g. `systemctl enable --now docker`, `systemctl reload caddy`, `ufw enable` relying on netfilter/systemd-managed state) will fail with `System has not been booted with systemd as init system (PID 1). Can't operate.` / `Failed to connect to bus: Host is down`.

This is **not a bug in the script under test** if the script's real target is a genuine VPS/VM (which does run systemd) — it's a structural limitation of this sandbox class. Confirm the rest of the script is sound by:
- Letting the apt/package-install portion run and complete normally (it will).
- Manually starting the daemon the systemd unit would have managed, as a plain background process, e.g. `nohup dockerd >/tmp/dockerd.log 2>&1 &` then `sleep N; docker version` to confirm it's usable — nested Docker-in-Docker works fine in these sandboxes without systemd.
- Continuing the rest of the deployment (Compose stack, app-level smoke tests) manually from that point, and reporting the systemd-dependent steps as "unverified in this sandbox class, requires a real VM/VPS" rather than treating the failure as a script defect.

If a true systemd-capable test is required, request/verify a VM-class snapshot (`sandboxClass: "vm"`, e.g. names like `*-vm-small`) instead of a container-class one — not verified whether VM-class sandboxes actually boot systemd, but they are the correct next thing to try if this matters.
