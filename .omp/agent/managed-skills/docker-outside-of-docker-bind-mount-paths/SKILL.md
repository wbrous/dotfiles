---
name: docker-outside-of-docker-bind-mount-paths
description: "Use when a worker/agent process launches sibling Docker containers via the host's Docker daemon (Docker-outside-of-Docker, e.g. through docker-socket-proxy or a mounted /var/run/docker.sock) and container creation/start fails with any of: \"invalid mount path: ... mount path must be absolute\", \"bind source path does not exist\", or \"network name not found\" (esp. under Docker Compose). Also relevant when designing bind-mount source paths or network references for such a setup."
---

## Symptom family

A process (e.g. `worker`) launches sibling containers against the **host's** Docker daemon — either via a mounted `/var/run/docker.sock` or a proxy like `tecnativa/docker-socket-proxy`. This is Docker-outside-of-Docker (DooD): the daemon that actually creates/starts containers is the **host** daemon, not anything inside the launching process's own container. Every path or name the launching process hands to the Docker API is resolved by that host daemon, in the host's own namespace — never in the launching process's container filesystem or network view.

Three distinct failure modes from this single root cause, all seen in one real deployment:

### 1. `invalid mount path: './x' mount path must be absolute`
A relative bind-mount `source` was used. Fix: resolve to an absolute path *on the host*, not inside the launching container. If using Compose, pass it in via `${PWD}/...` interpolation (compose substitutes the host cwd at `docker compose up` time) — do NOT default to a relative path in code, since that silently "works" until DooD is added.

### 2. `bind source path does not exist`
Docker does **not** create bind-mount source directories itself, unlike named volumes. Even with an absolute host path, the directory must already exist before `containers.create`. Since the launching process can't `mkdir` a path in the *host's* namespace directly, `mkdir` it via the launching process's **own** bind-mounted view of the same underlying directory (e.g. if compose mounts `./data:/data` into the launcher, and the host-absolute bind-mount source for sibling containers is `${PWD}/data/logs/<job-id>`, the launcher creates `/data/logs/<job-id>` through its own `/data` mount — same inode, different path string, different mount namespace). This means you generally need **two** env vars / config values for "the same" directory: one host-absolute path (for the Docker API `source`) and one launcher-local path (for the launcher's own `open()`/`mkdir()` calls) — do not conflate them, and do not reuse the host path for both.

### 3. `network <name> not found` (Compose-specific)
Compose auto-prefixes network (and volume) names with the **project name** unless `name:` is set explicitly in the network's definition (e.g. `orgbot-agent-net` becomes `orgbot_orgbot-agent-net`). Code that references a network by a hardcoded bare string (`AGENT_NETWORK = "orgbot-agent-net"`) when launching sibling containers has no way to know or reconstruct that prefix — it's constructing the launch request itself, not going through Compose's own name resolution. Fix: pin every network (and volume, if referenced by hardcoded name elsewhere) referenced this way to an explicit bare `name:` in the compose file, so it's stable regardless of project name, directory rename, `-p` flag, or `COMPOSE_PROJECT_NAME`.

## Debugging checklist when you hit any DooD container-creation/start error
1. Read the error literally — Docker's messages for these three cases are specific and distinguishable (`must be absolute` / `does not exist` / `not found`).
2. Ask: "whose filesystem/network namespace does this daemon actually see?" — always the **host's**, never the launcher's own container.
3. `docker network ls` / `docker volume ls` on the host to see actual resolved names if Compose is in play — don't assume bare names from the compose file are literally what got created.
4. Fix by pinning explicit absolute host paths / bare names in the compose file or launch config, not by guessing prefixes in application code.
