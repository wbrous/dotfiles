---
name: logto-fork-visual-verify-isolated-stack
description: "Visually verify UI changes to the optic-fyi Logto fork (experience/account) in a real browser without touching the user's live compose stack: isolated tagged image, throwaway compose project, reaching /register via the admin tenant OIDC flow, and the stale-image trap when editing source during a Docker build."
---

## When to use
You changed `apps/identity/logto/packages/experience` or `account` (SCSS, tokens, components) and need to SEE it rendered. The user's real `optic-fyi` compose stack is often running (Caddy on 80/443, `optic-fyi-app-1` on a real Postgres volume) -- NEVER `docker compose up --build` / recreate it for verification: a newer fork can crash-loop with "undeployed database alterations" and take down their dev login.

## Recipe (non-destructive)
1. Build under a distinct tag: `cd apps/identity/logto && docker build -t optic-logto-verify:ui .` (~2.5 min cold, pnpm layers cached after). This also verifies the frozen-lockfile `pnpm i` + `pnpm -r build` the real image needs.
2. Throwaway compose project in `/tmp/verify-stack/compose.yml` with `name: optic-logto-verify`, its own `postgres:17.11-alpine`, `image: optic-logto-verify:ui`, entrypoint `sh -c "npm run cli db seed -- --swe && npm start"`, `ENDPOINT=http://localhost:13001`, `ADMIN_ENDPOINT=http://localhost:13002`, ports bound to `127.0.0.1:13001/13002` (80/443/5432/8080 are taken). `docker compose up -d --wait`.
3. A fresh seed has NO applications in the `default` tenant; the only OIDC client is `admin-console` (tenant `admin`). Reach the real experience app by starting an auth request on the ADMIN endpoint:
   `http://localhost:13002/oidc/auth?client_id=admin-console&response_type=code&redirect_uri=http://localhost:13002/console/callback&scope=openid%20offline_access&code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM&code_challenge_method=S256&state=x&prompt=consent`
   It redirects to `/register` ("Create your account") on a fresh DB. The experience bundle is shared across tenants, so this is the same UI.
4. Drive with the `browser` eval helper; screenshot; inspect computed styles with `tab.evaluate`. Headless Chromium reports `prefers-color-scheme: dark`, so you see dark mode by default; emulate light via `tab.emulate({ colorScheme: 'light' })`.
5. Tear down: `docker compose down -v` in `/tmp/verify-stack`, `docker rmi optic-logto-verify:ui`, `rm -rf /tmp/verify-stack`.

## Traps
- STALE IMAGE: `COPY . .` snapshots the context at the START of the build. Editing source while `docker build` runs (it takes minutes) ships the OLD file even if the file's mtime is earlier than the image's Created time. Do not edit the fork tree during a build; rebuild after edits. Verify by grepping the built CSS inside the container (`docker compose exec app sh -c 'grep -c <rule> /etc/logto/packages/experience/dist/assets/index-*.css'`), not by timestamps.
- Logto injects styles through the JS bundle; `curl /register | grep .css` finds no `<link>`. Inspect `/etc/logto/packages/experience/dist/assets/` in the container instead.
- When selecting buttons in the page, `document.querySelector('button')` often hits the input's suffix icon button; match by text.
- Do not use `git stash` to get a baseline with lots of uncommitted work; use `git worktree add --detach /tmp/baseline HEAD`, `pnpm i --frozen-lockfile --filter "@logto/account..."`, and copy built `lib`/`dist` of shared workspace packages in.
- pnpm is not installed on this machine: `npm install --prefix /tmp/pnpm-bin pnpm@10`, then `PATH=/tmp/pnpm-bin/node_modules/.bin:$PATH`. Local Node is 26 vs required ^22.14 (only engine warnings). Run `pnpm --filter "@logto/experience^..." --filter "@logto/account^..." -r prepack` once so apps can typecheck.
