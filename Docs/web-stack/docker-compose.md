# Docker Compose, Proxies, and TLS

Covers compose env-var quoting, single-edge Caddy routing (incl. Logto endpoints), Docker-outside-of-Docker paths, root-owned bind-mount leftovers, `.local` dev proxies, private localhost mirrors, and Cloudflare single-level wildcard TLS.

## `${VAR:?message}` with a colon must be quoted

**Symptom.** A compose file using the required-env-var guard with a human-readable message:

```yaml
environment:
  POSTGRES_USER: ${POSTGRES_USER:?Set POSTGRES_USER in .env: the Postgres role Logto connects as}
```

`docker compose config` fails with `go-yaml load error in scanner at L7.C64: mapping values are not allowed in this context`. The colon inside the unquoted scalar is parsed by YAML as a mapping separator — YAML parses the raw file *before* compose does variable interpolation.

**Fix.** Quote every `${VAR:?message}` value containing a colon:

```yaml
environment:
  POSTGRES_USER: "${POSTGRES_USER:?Set POSTGRES_USER in .env: the Postgres role Logto connects as}"
```

Applies anywhere the pattern appears — `DB_URL: "postgres://${USER:?...}:${PASS:?...}@host/${DB:?...}"` needs it doubly (the URL itself has colons). Verify via `docker compose config` directly, or write a test that unsets each required var one at a time and asserts `config` fails *and* the error mentions that var name.

**Related (no-sudo shellcheck install):** if `sudo pacman -S shellcheck` hangs waiting on a fingerprint touch in a headless/agent session, fetch the static release binary instead:

```bash
mkdir -p ~/.local/bin && cd /tmp
curl -fsSL https://github.com/koalaman/shellcheck/releases/download/v0.11.0/shellcheck-v0.11.0.linux.x86_64.tar.xz -o sc.tar.xz
tar xf sc.tar.xz
cp shellcheck-v0.11.0/shellcheck ~/.local/bin/
chmod +x ~/.local/bin/shellcheck
```

_Migrated from: docker-compose-required-env-var-colon-quoting_

## Single edge Caddy, ROOT_DOMAIN-driven subdomain routing

One Caddy container is the *only* thing publishing host ports (`:80`/`:443`); every other service (backend, Logto `app`, static SPA builds) is reachable only on the internal Docker network. `caddy/Caddyfile` uses Caddy's `{$ROOT_DOMAIN}` env-var substitution per site block instead of hardcoded domains/ports, so changing one `ROOT_DOMAIN` var in `.env` moves the whole stack.

- Bind-mount `caddy/Caddyfile` (don't bake it into the image) so pure routing edits take effect via `docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile` — no rebuild, no downtime. Only rebuild when adding a new *static* site (new Dockerfile build stage) or changing Vite build-time `ARG`s.
- `*.localhost` (including multi-level, e.g. `admin.accounts.localhost`) resolves to loopback automatically per RFC 6761 on modern OSes/browsers — confirmed via `getent hosts` — no `/etc/hosts` editing for local dev. Caddy detects non-public hostnames and issues certs from its own internal CA instead of ACME.
- Persist `caddy-data`/`caddy-config` as named volumes so certs survive restarts.
- For browser automation against these self-signed local domains: launch a system Chromium binary directly with `app: { path: "/usr/bin/chromium", args: ["--ignore-certificate-errors", "--allow-insecure-localhost"] }` — the default managed browser's `ignore_https_errors` tab option is not sufficient for `net::ERR_CERT_AUTHORITY_INVALID`. If `browser.open` times out after switching binaries, `pkill -f chromium` first (stale profile lock).

**Logto ENDPOINT/ADMIN_ENDPOINT: separate origins, never a shared path.** The Admin Console **cannot** be routed as a path under `ENDPOINT` (e.g. `accounts.example.com/admin`). Verified live: Caddy can proxy `accounts.$ROOT_DOMAIN/admin/*` to the admin console container and the initial `index.html`/JS loads fine, but the console SPA's client-side router has no `/admin` basename concept — it renders "404 Not Found" for its own default route the moment React Router takes over. Not a proxy-config problem; not fixable by setting `ADMIN_ENDPOINT` with a path suffix. Logto's docs also gate `ADMIN_ENDPOINT` on an *exact-origin* CORS check ("If ADMIN_ENDPOINT is specified, only requests from the origin of ADMIN_ENDPOINT will be allowed"). Fix: a dedicated subdomain for the admin console, e.g. `admin.accounts.$ROOT_DOMAIN` — one more Caddy site block (`reverse_proxy app:3002`), one more `ADMIN_ENDPOINT` env value. Confirmed end-to-end: correct redirect to `/sign-in?app_id=admin-console`, correct "Logto Console" title, real sign-in form, no router 404.

_Migrated from: docker-compose-single-edge-caddy-reverse-proxy_

## Docker-outside-of-Docker: bind-mount paths and network names

When a process (e.g. `worker`) launches sibling containers against the **host's** Docker daemon — via mounted `/var/run/docker.sock` or `tecnativa/docker-socket-proxy` (Docker-outside-of-Docker, DooD) — every path/name handed to the Docker API is resolved by the **host** daemon in the **host's** namespace, never in the launching container's filesystem/network view. Three distinct failures, one root cause:

### `invalid mount path: './x'` — mount path must be absolute

A relative bind-mount `source` was used. Fix: resolve to an absolute path *on the host*, not inside the launching container. With Compose, pass it via `${PWD}/...` interpolation (compose substitutes the host cwd at `up` time) — don't default to a relative path in code.

### `bind source path does not exist`

Docker does **not** create bind-mount source directories (unlike named volumes). Even absolute, the directory must exist first. Since the launcher can't `mkdir` in the *host's* namespace directly, `mkdir` it via the launcher's **own** bind-mounted view of the same underlying directory (e.g. compose mounts `./data:/data` into the launcher, and the host-absolute source for siblings is `${PWD}/data/logs/<job-id>` — the launcher creates `/data/logs/<job-id>` through its own `/data` mount; same inode, different path string/mount namespace). So you generally need **two** env vars for "the same" directory: one host-absolute (handed to Docker), one container-view (used by the launcher itself).

### `network <name> not found` (Compose-specific)

Compose auto-prefixes network (and volume) names with the **project name** unless `name:` is set explicitly (e.g. `orgbot-agent-net` becomes `orgbot_orgbot-agent-net`). Code referencing a hardcoded bare string (`AGENT_NETWORK = "orgbot-agent-net"`) when launching siblings can't reconstruct that prefix. Fix: pin every network (and volume, if referenced by hardcoded name) referenced this way to an explicit bare `name:` in the compose file, stable regardless of project name, directory rename, `-p` flag, or `COMPOSE_PROJECT_NAME`.

**Debugging checklist:** read the error literally (the three messages are distinguishable); ask "whose filesystem/network namespace does this daemon see?" (always the host's); `docker network ls` / `docker volume ls` on the host to see actually-created names; fix by pinning explicit absolute paths/bare names in compose or launch config, not by guessing prefixes in code.

_Migrated from: docker-outside-of-docker-bind-mount-paths_

## Root-owned leftover from a compose bind mount + workspace Dockerfile rule

**Symptom.** `git revert`/`switch`/`cherry-pick` fails with `fatal: cannot rmdir 'X/File': Permission denied`; `ls -la` shows a root-owned *directory* where a file used to be.

**Cause.** Compose bind-mounted `./X/File`; the path was missing at container start, so Docker created it as a root-owned directory. The old container still holds that mount, so deleting the dir alone is undone the next time the container is touched.

**Fix (no sudo needed if in the `docker` group; check `sudo -n true` and `id -nG`):**

1. Confirm the dir holds no files and nothing is tracked: `find X -mindepth 1 ! -type d`, `git ls-files X`.
2. Find containers still mounting it: `docker inspect $(docker ps -aq) --format '{{.Name}} {{range .Mounts}}{{.Source}} {{end}}' | grep X`.
3. `docker rm <container>` (named volumes survive, so certs/data are kept).
4. `docker run --rm -v "$PWD:/repo" <any local image> rm -rf /repo/X` (mount only the parent, name only the one path).
5. `docker compose up -d --build <svc>` from the new layout; confirm the dir does not reappear.

While the dir blocks git in the main checkout, do history surgery in a `git worktree add /tmp/x` instead.

**Adding a Bun workspace package: update every Dockerfile.** Dockerfiles running `bun install --frozen-lockfile` against the root `bun.lock` must `COPY <workspace>/package.json` for EVERY workspace in the lockfile, or the build fails with `Workspace dependency "<name>" not found`. Stays hidden while running containers predate the change. After adding a package, run `docker compose build` for every service with a deps stage. Packages shipping raw TypeScript source (no build step) also need their `src/` copied before a consumer's Vite build.

_Migrated from: docker-root-owned-bind-mount-leftover-and-workspace-copy_

## Temporary `.local` reverse proxy for local dev (Caddy + /etc/hosts)

Use when a browser must reach services via friendly hostnames (`foo.local`, `foo-admin.local`) instead of `localhost:PORT` — e.g. testing a multi-service app where one service's Admin/Web-Crypto UI needs a secure context, or an app's own OIDC/backend config hardcodes an internal self-referential URL that the proxied hostname must match.

**Gotcha 1: `.local` is mDNS-reserved.** On many systemd/Arch systems `/etc/nsswitch.conf` has `hosts: mymachines mdns_minimal [NOTFOUND=return] resolve files myhostname dns` — `mdns_minimal` runs *before* `files`, and `[NOTFOUND=return]` means: mDNS says "not found" → stop, `/etc/hosts` never consulted for `.local` names. Symptom: you add `127.0.0.1 foo.local` to `/etc/hosts`, but `getent hosts foo.local` returns nothing. Fix (temporary, back up first):

```bash
sudo cp /etc/nsswitch.conf /etc/nsswitch.conf.backup
sudo sed -i 's/^hosts:.*/hosts: files mymachines resolve myhostname mdns_minimal [NOTFOUND=return] dns/' /etc/nsswitch.conf
# ... test ...
sudo mv /etc/nsswitch.conf.backup /etc/nsswitch.conf   # revert when done
```

**Gotcha 2: browsers auto-upgrade `http://` to `https://`.** If Caddy serves a temp domain over plain HTTP, Firefox HTTPS-Only Mode / Chrome's default upgrade silently tries HTTPS → `SSL received a record that exceeded the maximum permissible length`. Don't fight the browser — serve every temp hostname over real (self-signed) HTTPS via Caddy's `tls internal`, on non-privileged high ports:

```caddyfile
{
	auto_https disable_redirects
}

https://foo.local:18080 {
	tls internal
	reverse_proxy 127.0.0.1:3001
}
```

Self-signed = one click-through warning per domain; don't try to trust it system-wide for a throwaway test.

**Gotcha 3: app-internal self-calls need the container to resolve your fake hostname too.** If the app makes its own HTTP calls to its externally-configured public URL (e.g. Logto's `ENDPOINT`, used as browser-facing issuer AND for OIDC-discovery self-checks) and runs in Docker, the container's DNS has no idea what `foo.local` means — only the host's `/etc/hosts` does. Symptom: app fails to start / times out on startup self-checks. Fix: `extra_hosts` on that service via a *separate temporary compose override* (don't touch the committed `compose.yml`), pointing at `host-gateway`, with Caddy binding all interfaces (default) so the container reaches it via the bridge gateway:

```yaml
# override.yml
services:
  app:
    extra_hosts:
      - "foo.local:host-gateway"
```

```bash
docker compose -f compose.yml -f override.yml up -d --wait
```

**Gotcha 4 (architectural): an app validating redirect/callback URLs against its OWN literal endpoint CANNOT be proxied under a different hostname.** Example: Logto's Admin Console SPA computes its OIDC `redirect_uri` client-side as `window.location.origin + /console/callback`. The OIDC server only accepts it if it matches the literally-configured `ADMIN_ENDPOINT` (e.g. `http://localhost:3002`) — and `ADMIN_ENDPOINT` must stay literal `localhost`, because Logto's own internal admin-token-validation self-calls break (`ECONNREFUSED`) otherwise. So proxying the admin console through `admin.foo.local` 400s with `oidc.invalid_redirect_uri` the moment you sign in / create an account, even though the login page loads fine. You can still render the *page* via the proxy by rewriting `Host`, `X-Forwarded-Host`, `X-Forwarded-Proto`, `X-Forwarded-Port` on that route (Caddy `reverse_proxy { header_up ... }`; Logto's admin-vs-core routing reads `X-Forwarded-Host`, not raw `Host`, when `TRUST_PROXY_HEADER=1`) — but that fixes rendering only, never the OIDC flow, which is bound to `window.location.origin`. Diagnose fast: `curl -L` the exact `/oidc/auth?...redirect_uri=...` once with the proxied hostname (expect `400 oidc.invalid_redirect_uri`) and once with the literal endpoint (expect `303` into sign-in). Correct answer: don't proxy this kind of service at all — access it via its literal `http://localhost:PORT`. Real production deployments keep the admin surface on `localhost` + SSH tunnel for the same reason.

**Cleanup (temporary means temporary):** stop the Caddy process; `rm -rf` the temp Caddyfile/override dir; remove the `/etc/hosts` lines (`sudo sed -i '/foo\.local/d' /etc/hosts`); restore `/etc/nsswitch.conf` from backup. If asked to "keep the server running as-is" while tearing down only the `.local` plumbing: do NOT recreate/restart the app container to reset a stale `ENDPOINT` back to `localhost` — leave it and tell the user the OIDC issuer will report the stale hostname until they ask for that follow-up. Each `/etc/hosts`/`nsswitch.conf` step needs `sudo`; on fingerprint-gated sudo, expect a physical touch per command.

_Migrated from: local-dot-local-hostname-caddy-dev-proxy_

## Private localhost-only mirror of an external site (Node + Docker)

Reference implementation: `~/Projects/node-website-proxy/` (`server.js`, `Dockerfile`, `docker-compose.yml`) proxying e.g. `https://www.makemkv.com/` to `localhost:8080`. Copy and change `UPSTREAM_HOST` / `UPSTREAM_BARE`.

1. **Check the port first:** `ss -ltnp | grep ':PORT '` and `docker ps --format '{{.Names}}\t{{.Ports}}'`. Map containers to projects with `docker compose ls -a`, then `docker compose -p <name> stop` (keeps data). Ask the user what to stop; never stop containers unasked. "optic" stuff = projects `optic-fyi` and `accounts`.
2. **Zero-dependency Node `server.js`** (node:http/https/zlib): fixed upstream host (never derive target from the request — no open proxy); allow only `Host: localhost:PORT` / `127.0.0.1:PORT` (403 otherwise, blocks DNS rebinding); GET/HEAD only (405 otherwise); don't forward cookie/referer/origin; drop `set-cookie`, HSTS, nel/report-to; add `X-Robots-Tag: noindex`. Request `accept-encoding: gzip, deflate, br`. For text/json/xml/js types, buffer, decompress, regex-rewrite `(https?://)?(www.)?host` to `http://localhost:PORT`, delete `content-encoding` and `etag`, set new `content-length`. Rewrite `Location` headers. Pipe everything else (images etc.) untouched.
3. **Dockerfile:** `node:22-alpine`, `USER node`, copy `server.js` only.
4. **Compose:** publish `"127.0.0.1:PORT:PORT"` (the `127.0.0.1` prefix is what keeps it private), `read_only: true`, `cap_drop: [ALL]`, `no-new-privileges`, `tmpfs: /tmp`, `restart: unless-stopped`. `docker compose up -d --build`.
5. **Verify:** `curl localhost:PORT/` → 200, right `<title>`, 0 remaining upstream-domain refs. Compare proxy vs upstream status on real links scraped from the home page (don't guess paths — a guessed `/download.php` 404ed upstream too). `curl -H 'Host: evil.com' http://127.0.0.1:PORT/` → 403. POST → 405. LAN IP on PORT fails; `ss -ltn` shows `127.0.0.1:PORT`. `docker inspect` shows non-root user, read-only rootfs, caps dropped.
6. **Stop:** `docker compose down` in the project dir. Note: a stopped Zitadel sharing the port conflicts; its postgres (5432) and zitadel (8080) were published on `0.0.0.0`, so suggest binding them to `127.0.0.1`.

_Migrated from: private-localhost-site-proxy-docker-node_

## Cloudflare free Universal SSL covers only one subdomain level

**Symptom.** A hostname two+ levels below a Cloudflare zone apex (zone `example.com`, hostname `api.foo.example.com`) fails TLS: Firefox/Zen `SSL_ERROR_NO_CYPHER_OVERLAP`; curl `TLS connect error ... ssl/tls alert handshake failure`; `openssl s_client` → `SSL alert number 40`, no peer certificate. DNS resolves fine, `cloudflared tunnel route dns` succeeds — purely no valid edge cert covers the hostname.

**Cause.** Free Universal SSL issues a cert covering the apex + `*.example.com` (one wildcard level) only. `api.foo.example.com` (two levels) is NOT covered. Covering it needs a paid Advanced Certificate Manager add-on.

**Fix (free):** restructure to exactly one level below the apex — e.g. `foo-api.example.com` instead of `api.foo.example.com`. Both covered by the same free `*.example.com` wildcard. Migrating an existing cloudflared tunnel ingress hostname:

1. `cloudflared tunnel route dns <tunnel-name> <new-one-level-hostname>` — adds the new CNAME (doesn't remove the old).
2. Edit `~/.cloudflared/config.yml` AND `/etc/cloudflared/config.yml` (the systemd service reads `/etc/cloudflared/`, not `~/.cloudflared/`, when installed via `cloudflared service install` — no symlink by default; keep both in sync manually) — change the `ingress:` hostname.
3. `sudo systemctl restart cloudflared`.
4. Verify: `curl -sS -o /dev/null -w '%{http_code}\n' https://<new-hostname>/<path>` → real HTTP status, not curl exit 35.
5. The old two-level CNAME is now orphaned (no ingress rule matches) — harmless; delete via the Cloudflare dashboard DNS records if tidy. `cloudflared tunnel route dns` has no delete/remove.

**Diagnostic shortcut:** `openssl s_client -connect <host>:443 -servername <host> </dev/null 2>&1` — "SSL alert number 40" / "no peer certificate available" with a clean TCP connect = this depth-of-subdomain cert issue, not tunnel/DNS/config. Don't waste time re-checking ingress rules or DNS propagation first.

_Migrated from: cloudflare-free-ssl-single-level-wildcard_
