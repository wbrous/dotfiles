---
name: private-localhost-site-proxy-docker-node
description: "Proxy/mirror an external website to localhost:PORT via a Node server in Docker, private to the host (loopback-only); includes port-conflict check and verification."
---

# Private localhost proxy of an external site (Node + Docker)

Reference implementation: `~/Projects/node-website-proxy/` (server.js, Dockerfile, docker-compose.yml) proxying https://www.makemkv.com/ to localhost:8080. Copy and change `UPSTREAM_HOST` / `UPSTREAM_BARE`.

## Steps
1. **Check the port first**: `ss -ltnp | grep ':PORT '` and `docker ps --format '{{.Names}}\t{{.Ports}}'`. In this workstation 8080 was held by `accounts-zitadel-1` (compose project `accounts`, dir `~/Projects/optic.fyi/apps/accounts`). Ask the user what to stop. Never stop containers unasked. Map containers to projects with `docker compose ls -a`, then `docker compose -p <name> stop` (keeps data). "optic" stuff = projects `optic-fyi` and `accounts`.
2. **Zero-dependency Node `server.js`** (node:http/https/zlib):
   - Fixed upstream host; never derive target from the request (no open proxy).
   - Allow only `Host: localhost:PORT` / `127.0.0.1:PORT` (403 otherwise, blocks DNS rebinding).
   - GET/HEAD only (405 otherwise).
   - Do not forward cookie/referer/origin; drop `set-cookie`, HSTS, nel/report-to from the response; add `X-Robots-Tag: noindex`.
   - Request `accept-encoding: gzip, deflate, br`. For text/json/xml/js types, buffer, decompress, regex-rewrite `(https?:)?//(www.)?host` to `http://localhost:PORT`, delete `content-encoding` and `etag`, and set a new `content-length`. Rewrite `Location` headers. Pipe everything else (images etc.) untouched.
3. **Dockerfile**: `node:22-alpine`, `USER node`, copy server.js only.
4. **Compose**: publish `"127.0.0.1:PORT:PORT"` (the 127.0.0.1 prefix is what keeps it private), `read_only: true`, `cap_drop: [ALL]`, `no-new-privileges`, `tmpfs: /tmp`, `restart: unless-stopped`.
5. `docker compose up -d --build`.

## Verify (all done in the original run)
- `curl localhost:PORT/` returns 200 and the right `<title>`, with 0 remaining upstream-domain refs.
- Compare proxy vs upstream status on real links scraped from the home page. Don't guess paths: a guessed `/download.php` 404ed upstream too.
- `curl -H 'Host: evil.com' http://127.0.0.1:PORT/` returns 403. POST returns 405.
- LAN IP (`ip -4 route get 1.1.1.1`) on PORT fails; `ss -ltn` shows `127.0.0.1:PORT`.
- `docker inspect` shows non-root user, read-only rootfs, caps dropped.

## Notes
- Stop with `docker compose down` in the project dir.
- Restarting a stopped Zitadel on the same port conflicts. Its postgres (5432) and zitadel (8080) were published on 0.0.0.0, so suggest binding them to 127.0.0.1.
