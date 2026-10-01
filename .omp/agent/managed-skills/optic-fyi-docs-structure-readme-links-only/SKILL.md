---
name: optic-fyi-docs-structure-readme-links-only
description: "Use when editing or adding docs in the optic-fyi monorepo: docs/ layout, link-only READMEs, no decisions docs, link/anchor verification."
---

# optic-fyi docs convention (user-stated preferences)

- All real documentation lives in `docs/`; bare-metal/setup guides are NOT in app READMEs.
- Every README (root, `apps/*`, `packages/*`, `test-server`, `infra/caddy`) contains ONLY a title plus links to the docs files, each with a short human-readable description. Relative links (`../../docs/...`).
- Docs are guides and structure, NOT decision/rationale/"future plan" docs. Do not create `decisions.md`, `design.md`, `future.md`.

## Layout
```
docs/README.md          index
docs/architecture.md    layout, topology, auth, source layouts, ports
docs/guides/            local-development, logto-setup, deployment, caddy, backups
docs/apps/              backend, identity, parent-dashboard, kid-dashboard
docs/packages/          api-client, ui
docs/test-server.md     UI showcase
```
All Caddy files live in `infra/caddy/` (Caddyfile, Dockerfile); no top-level `caddy/`.

## Procedure when changing docs
1. Update the matching `docs/` file, not the README.
2. Grep for stale pointers (`README`, old doc paths) in `.env.example`, `docker-compose.yml`, Caddyfile, scripts, source comments and retarget to `docs/...`.
3. Verify: script to check all relative markdown links + heading anchors; check every package.json script and env var is documented; `docker compose config -q` (needs all `:?` vars supplied) and `caddy validate` via `caddy:2-alpine` with `-e ROOT_DOMAIN=localhost`.

## Gotchas
- Mass `sed` on `caddy/` paths also mangles `/etc/caddy/Caddyfile`; re-grep for `etc/infra`.
- `git rm` of a dir with `infra/caddy/Caddyfile` removes the empty dir; `mkdir -p` before `git mv`.
- Root stack overrides Logto `ENDPOINT`/`ADMIN_ENDPOINT`; admin console is public at `admin.accounts.$ROOT_DOMAIN` (no SSH tunnel) in the root stack.
