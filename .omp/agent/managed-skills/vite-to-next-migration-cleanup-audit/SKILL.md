---
name: vite-to-next-migration-cleanup-audit
description: "After a Vite SPA is ported to Next App Router (esp. optic-fyi apps/dashboard): audit leftovers, add Next conventions, verify rewritten multi-tenant routes."
---

## Audit checklist
Read bundled docs at `node_modules/next/dist/docs/01-app` (version-specific; Next 16.4 differs from memory).

Vite leftovers to remove:
- `.oxlintrc.json`: drop `react/only-export-components` (Fast Refresh rule; flags `metadata` exports in every layout). Add `"nextjs"` plugin.
- `.gitignore` copied from Vite template -> trim to `node_modules .next next-env.d.ts *.tsbuildinfo .env`.
- `components.json`: `"rsc": true`.
- Hook-using components lacking `"use client"` (relying on importer) -> add explicitly.
- Render-prop gates + `XPage.tsx` wrapper files (needed because functions can't cross server->client) -> replace with a route-group `(group)/layout.tsx` taking `children` + context hook.
- `useEffect(()=>setState(localStorage...))` -> `useSyncExternalStore` with server snapshot `"unknown"`.

Add: `app/error.tsx` (Next 16.3+: prop `retry`, not `reset`), `app/not-found.tsx`, root `title: {default, template: "%s | site"}`.

## Gotchas
- `typedRoutes: true` fails every `href`/`router.push` when public URLs are proxy rewrites of `/tenant/...` (e.g. `/children` vs `/parent/children`). Don't enable; revert. After toggling, `rm -rf .next/types` or stale generated types mislead typecheck.
- Server-side auth (`@logto/next`) needs a Logto *traditional web* app + secret + cookie; not possible with the SPA registration. Treat as separate task.
- No `loading.tsx` value when all fetching is client-side.

## Smoke test standalone multi-tenant build
`NEXT_PUBLIC_*=x bun run build`, then run `PORT=3199 HOSTNAME=127.0.0.1 node .next/standalone/apps/dashboard/server.js` as a background service (plain `&` in bash got killed -> curl code 000). `curl -H "Host: kids.localhost:3199"` / `dashboard.localhost:3199` per route; expect bare `localhost` 404, `/kid/*` direct 404, cross-tenant path 404.
