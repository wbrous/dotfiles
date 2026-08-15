---
name: orgbot-agent-container-launch-gotchas
description: "Use when orgbot (ZepHangar/orgbot) job containers fail to launch or die instantly with \"mount path must be absolute\", \"bind source path does not exist\", \"network orgbot-agent-net not found\", \"Could not resolve host: github.com\", or internal:CalledProcessError — the Docker-outside-of-Docker + internal-network + egress-proxy wiring bugs that stack up in this specific deployment."
---

# orgbot agent-container launch gotchas

orgbot's `worker` launches ephemeral `orgbot/agent` containers **against the host Docker daemon** via `docker-socket-proxy` (Docker-outside-of-Docker / DooD). This creates four distinct, compounding failure modes that each surface as a separate 400/404/instant-death. Fix them all, not one at a time.

## 1. Bind-mount source must be host-absolute
`worker/dispatch.py:RESULTS_DIR` is the bind source for `data/logs/<job-id>`.
- The host daemon resolves this path, NOT `worker`'s own container filesystem.
- Relative (`./data/logs`) or worker-internal (`/data/logs`) paths are both wrong.
- `docker-compose.yml` sets `ORGBOT_RESULTS_DIR=${PWD}/data/logs` (host-absolute).
- Error: `invalid mount path: './data/logs/...' mount path must be absolute`.

## 2. Docker does not create bind-mount source dirs
`containers.create` 400s if `<results_dir>/<job-id>` doesn't exist yet.
- `worker` can't `mkdir` the host path (not in its mount namespace).
- It CAN `mkdir` via its own `./data:/data` mount — the SAME underlying dir.
- So `dispatch.py` has two paths: `results_dir` (host, for Docker bind source) and `local_results_dir` (worker's `/data/logs` view, for `os.makedirs` and for `_read_result`).
- `worker/main.py` must read `result.json` back via `local_results_dir`, never `results_dir` (host path invisible inside worker's container).
- Error: `bind source path does not exist: .../data/logs/<job-id>`.

## 3. Compose network name prefixing
Compose auto-prefixes bridge network names with the project name (`orgbot_orgbot-agent-net`) unless `name:` is pinned. `dispatch.py:AGENT_NETWORK` is a hardcoded bare string `"orgbot-agent-net"`.
- Pin explicit `name:` on all three networks in `docker-compose.yml`, or container creation 404s.
- Error: `failed to set up container networking: network orgbot-agent-net not found`.

## 4. internal:true network has no egress — proxy must be explicit
`orgbot-agent-net` is `internal: true`: no DNS, no default route. The ONLY internet path is the dual-homed squid `egress-proxy` (port 3128). Nothing auto-routes to it.
- `_build_env` MUST set `HTTP_PROXY`/`HTTPS_PROXY` (+ lowercase) → `http://egress-proxy:3128`, and `NO_PROXY` (+ lowercase) so `gh-proxy` on the same net isn't proxied.
- Overridable via `ORGBOT_EGRESS_PROXY` / `ORGBOT_NO_PROXY`.
- Error: agent dies instantly at `git clone` with `Could not resolve host: github.com` → `internal:CalledProcessError` (only `result.json` written, no transcript).

## 5. Model provider must be in squid allowlist
`egress-proxy/squid.conf` is deny-by-default (`dstdomain` ACL). `omp` resolves `--provider opencode-go` → `https://opencode.ai/zen/go/v1`, so `.opencode.ai` must be allowlisted or the agent can clone but can't reach the LLM. Add any new provider's domain here.

## Agent image build
`ghcr.io/can1357/oh-my-pi:latest` is a **private** image (anonymous pull 403). Build `orgbot/agent` from `node:20-slim` instead, and install `omp` from public npm (`@oh-my-pi/pi-coding-agent`, pinned to `17.3.2`). The image is NOT a compose service — build manually:
```
docker build -t orgbot/agent:latest orgbot/agent/
```
`omp`'s installed CLI entrypoint execs `bun`, so `bun` must also be installed (npm install alone leaves `env: 'bun': No such file or directory`). `ca-certificates` is needed or the bun.sh install curl intermittently fails a TLS cert check.

## Debugging a dead job
- The job container is `--rm`, so `docker logs` is gone after exit.
- Read the persisted result at host `data/logs/<job-id>/result.json`.
- Reproduce egress manually: `docker run --rm --network orgbot-agent-net --entrypoint sh orgbot/agent:latest -c 'curl -x http://egress-proxy:3128 https://github.com'` — direct (no `-x`) should fail DNS, proxied should be 200, non-allowlisted host should 403.
