---
name: nextjs-host-based-multi-tenant-proxy-rewrite
description: "Next.js 16 single app serving multiple tenants by Host header via proxy.ts rewrite; 404/500 on every page behind Caddy, forged Host/internal prefix access, Vite-to-Next migration in a bun monorepo."
---

# Host-based multi-tenant Next 16 app (proxy.ts rewrite)

## Next 16 specifics
- `middleware.ts` is renamed `proxy.ts` (export `proxy`). Docs ship in the npm tarball: `npm pack next@latest`, read `dist/docs/01-app/...`.
- Tenant routes live in `src/app/<tenant>/`; public URLs stay clean via rewrite (`/children` -> `/parent/children`).

## Gotchas (each cost a debug cycle)
1. **Next re-runs proxy on the rewritten path**, and on that pass `request.nextUrl.host`/Host is the server's own `localhost:<port>`, not the client's. A naive "resolve tenant from Host" then 404s every valid page.
2. **Do NOT rewrite to a URL with the original Host set** (`url.host = hostHeader`): it passes `next start` locally but behind Caddy Next treats it as an external proxy fetch -> 500 `ECONNREFUSED` to the public port. Keep rewrites same-origin (`nextUrl.clone()` + new pathname).
3. Carry tenant across the re-entry with request headers via `NextResponse.rewrite(url, { request: { headers } })`: a tenant header plus a per-process random proof (`crypto.randomUUID()`, optional `PROXY_PROOF_SECRET`). A tenant header alone is forgeable; client-sent Host must never unlock `/parent/*`, `/kid/*`.
4. Put the policy in a pure `decideRouting()` (tested) and keep `proxy.ts` as glue; the re-entry bug was only caught end to end, so test through the real reverse proxy.
5. Subdomain resolution: first DNS label only, use `Object.hasOwn` (prototype keys like `constructor`), strip port, lowercase. `*.localhost` resolves to loopback in Chromium, so dev uses `dashboard.localhost:3100`.

## Migration notes (Vite -> Next, bun workspace)
- `import.meta.env.VITE_X` -> `process.env.NEXT_PUBLIC_X` (inlined at build; pass as Docker build ARGs).
- Hooks/browser APIs need `"use client"`; keep `page.tsx` server thin, render client views. Functions can't be props from server pages: wrap in a client component.
- `localStorage` auth: use a hook with an `"unknown"` first state to avoid SSR/hydration flash.
- Shared `@/` alias collides across merged apps: rewrite to `@/tenants/<t>/...`.
- `next.config.ts`: `output: "standalone"`, `outputFileTracingRoot` = monorepo root, `transpilePackages` for raw-TS workspace pkgs. Standalone server at `.next/standalone/apps/<app>/server.js`; copy `.next/static` beside it.
- Tailwind v4: `@tailwindcss/postcss` + `postcss.config.mjs`; add `@source` for tenant dirs.
- Caddy: one site block `a.{$ROOT_DOMAIN}, b.{$ROOT_DOMAIN} { reverse_proxy app:3100 }`; never `header_up Host`.
- Update docker-compose, backend CORS defaults, Logto redirect URIs, docs.

## Tool note
Background `setsid node server.js &` dies in the bash tool; run servers via the managed service (`ready` option) and kill by pid before restarting on a rebuild (stale server serves old build).
