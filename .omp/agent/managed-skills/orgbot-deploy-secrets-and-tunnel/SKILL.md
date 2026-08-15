---
name: orgbot-deploy-secrets-and-tunnel
description: "Use when deploying orgbot (the GitHub-org agent dispatcher built in orgbot-workspace/orgbot) — covers GH_REVIEW_PAT scope requirements, DASHBOARD_SESSION_SECRET generation, .env git-tracking hygiene, cloudflared reverse-proxy/tunnel setup for the receiver+dashboard split, model-provider API key wiring, and the config/repos.yml repo allowlist."
---

## GH_REVIEW_PAT must be a fine-grained PAT, not classic

`GH_REVIEW_PAT` (used by `gh-proxy` to post PR reviews without any code-push
capability) needs `Pull requests: Read and write` + `Contents: Read-only`.
Classic PATs have no per-resource scope split — `repo` scope bundles
contents-write in with everything else, so a classic token here would make
the "gh-proxy can't push code" guarantee purely code-enforced (gh-proxy just
never calls a push endpoint) rather than token-enforced. Create it manually
via GitHub → Settings → Developer settings → Fine-grained tokens, scoped to
the org's repos. This is separate from `CREDENTIAL_MODE`, which only
controls how per-job `SCOPED_TOKEN`s get minted.

## DASHBOARD_SESSION_SECRET

Just an HMAC-SHA256 key signing the OAuth `state` CSRF cookie
(`dashboard/app.py`) — session IDs themselves are opaque DB-backed tokens,
this secret doesn't sign/encrypt those. `openssl rand -hex 32` is fine. If
unset, `unsign()` explicitly rejects everything (`if not SESSION_SECRET:
return None`) — login loops forever rather than failing open, so never leave
it blank.

## .env git-tracking hygiene

Watch for `.env` being tracked in git with only placeholder (`changeme`)
values committed, while the actual working-tree copy has real secrets filled
in — a `git add .`/`git commit -a` at that point leaks real credentials into
history. Fix: `git rm --cached .env`, add `.env` to `.gitignore`. Treat any
credential that appeared in a `git diff` output during an agent session as
exposed — rotate it — even if it never made it into a commit.

## Cloudflare Tunnel (cloudflared) setup for receiver+dashboard split

Typical split: webhook receiver on one hostname → `localhost:8080`,
dashboard on another → `localhost:8082`. See the
`cloudflare-free-ssl-single-level-wildcard` skill for why the receiver
hostname must be only ONE level under the zone apex (e.g.
`foo-api.example.com`, not `api.foo.example.com`) — free Universal SSL only
covers one wildcard level, and going two levels deep produces
`SSL_ERROR_NO_CYPHER_OVERLAP` in-browser.

Setup sequence (Arch/Omarchy: `yay -S cloudflared`):
1. `cloudflared tunnel login` (interactive, opens browser, picks the zone)
2. `cloudflared tunnel create <name>` → writes
   `~/.cloudflared/<TUNNEL_ID>.json`; rename/reference it as
   `credentials-file` in `~/.cloudflared/config.yml`
3. `~/.cloudflared/config.yml`: `tunnel:`, `credentials-file:`, `ingress:`
   list of `hostname:`/`service:` pairs + a trailing catch-all
   `service: http_status:404`
4. `cloudflared tunnel route dns <name> <hostname>` per hostname — creates
   the CNAME
5. For a persistent systemd service: `sudo cloudflared service install`
   reads config from `/etc/cloudflared/`, NOT `~/.cloudflared/` (root's home,
   not the user's) — copy `config.yml` + the credentials JSON there and fix
   up the `credentials-file` path before installing, or the service fails
   with "Cannot determine default configuration path."
6. cloudflared sets `X-Forwarded-Proto: https` automatically, so
   cookie-secure-by-default backends (e.g. `DASHBOARD_COOKIE_SECURE=1`) work
   with no extra config.
7. Reverse-proxying a webhook receiver: the raw request body must reach it
   byte-for-byte — HMAC signature verification (`X-Hub-Signature-256`)
   breaks if any layer re-serializes/pretty-prints the JSON body. Plain
   passthrough proxies (cloudflared, nginx `proxy_pass`, Caddy
   `reverse_proxy`) are fine.

## Model-provider API keys: the ephemeral agent container starts with NONE

The spec/plan for this system never mentioned how the per-job `agent`
Docker container authenticates to an LLM provider — easy gap to miss when
implementing from spec, because it's genuinely absent from the source
document. The container has no home dir / `~/.omp` profile of its own, so
`omp` (which resolves provider keys from process env — see `omp --help` →
"Environment Variables": `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
`OPENROUTER_API_KEY`, `OPENCODE_API_KEY`, etc.) has nothing to authenticate
with unless the dispatcher explicitly forwards a key into the container's
env at launch. Fix pattern: the deploying worker/dispatcher process reads
its own `.env`-populated env for a fixed list of known provider-key var
names, and forwards whichever ones are actually set (never empty strings)
into `docker.containers.run(environment={...})` unchanged. A
`PROVIDER_OVERRIDE` env var (mapping to `omp`'s legacy `--provider` flag,
additive alongside `--model`, never a substitute) can be wired the same way
for deployments that need to pin a specific provider explicitly.

## config/repos.yml `repos:` list is a hard allowlist, not documentation

An empty `repos: []` means the receiver/worker accepts webhooks for NO
repos in the org — every event gets filtered out as `not_allowlisted`
before trigger evaluation ever runs. Every repo orgbot should act on must
be listed by `name:` under `repos:`. Per-repo `.orgbot.yml` (fetched from
each repo) still gates actual trigger behavior on top of this — allowlisting
a repo here without also adding `.orgbot.yml` in that repo leaves it
allowlisted but inert (fetch returns 404 → treated as disabled). The bot
account also needs write access granted on GitHub itself to each repo,
independent of both config files.
