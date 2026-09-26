---
name: hono-backend-browser-spa-cors-and-logto-spa-setup
description: "Use when wiring a new browser SPA (Vite/React) to a Hono+Logto backend in a Bun workspace monorepo: CORS 404/blocked preflight, Logto oidc.invalid_target, shadcn init prompts, or bun add failing on unpublished workspace packages."
---

## Context

Building a new browser-based frontend (Vite SPA) against an existing Hono backend + Logto auth in a Bun workspace monorepo (pattern seen in optic-fyi: `apps/backend` + `packages/api-client` + `apps/*-dashboard`). Several non-obvious gotchas surface only when you actually exercise the app in a browser — build/typecheck passing is not enough.

## Gotcha 1: Hono backend has no CORS by default

A Hono backend built for a same-origin or server-to-server consumer typically has zero CORS middleware. The moment a browser SPA on a different port calls it, every preflight `OPTIONS` request 404s (Hono has no route for it) and the browser blocks the real request even if the server would have returned 200.

**Symptom**: `curl -X OPTIONS ... -H "Origin: http://localhost:5173"` returns `404 Not Found` instead of `204` with `Access-Control-Allow-Origin`.

**Fix**: add `hono/cors` to the root app:
```ts
import { cors } from "hono/cors";
app.use("*", cors({
  origin: env.CORS_ALLOWED_ORIGINS, // string[], from a comma-separated env var
  allowHeaders: ["Content-Type", "Authorization"],
  allowMethods: ["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
}));
```
Add `CORS_ALLOWED_ORIGINS` to the env schema (comma-separated, `.transform(v => v.split(",").map(s=>s.trim()).filter(Boolean))`, sensible dev default), wire it through docker-compose `environment:`, and document it in the README. Rebuild+restart the backend container after adding — code changes need `docker compose up -d --build <service>`.

## Gotcha 2: Logto SPA sign-in needs `resources` in LogtoConfig, not just at getAccessToken time

If you call `getAccessToken(API_RESOURCE)` for a resource that wasn't declared in the *original sign-in request*, Logto returns `oidc.invalid_target` / "resource indicator is missing, or unknown" — repeatedly, in a way that can spin the UI forever on "Loading...".

**Fix**: declare every resource the app will ever request in `LogtoConfig` itself:
```ts
export const logtoConfig: LogtoConfig = {
  endpoint, appId,
  resources: [API_RESOURCE], // NOT just passed to getAccessToken later
};
```
After fixing, existing browser sessions/tokens from before the fix are stale — clear storage (`tab.clearStorage("local")` + `tab.clearStorage("session")`, or just sign out) and sign in again.

## Gotcha 3: `bun add <workspace-package>` fails for unpublished internal packages

`bun add @scope/internal-pkg` inside a freshly-scaffolded app tries npm registry first and 404s, even though it's a sibling workspace member. Fix: add the dependency manually to `package.json` as `"@scope/internal-pkg": "workspace:*"`, then run `bun install` from the **repo root** (not the app dir) to resolve/link it.

## Gotcha 4: shadcn CLI `-b <base>` alone isn't enough non-interactively

`shadcn init -y -t vite -b radix --no-monorepo` still prompts interactively for a preset (Nova/Vega/Maia/...) despite `-y`. Combine a preset name with the base flag instead: `shadcn init -y -t vite -p nova -b radix --no-monorepo`. Presets are theme names (nova, vega, maia, lyra, mira, luma, sera, rhea), separate from `-b`.

## Gotcha 5: New workspace app breaks other services' Docker builds via lockfile drift

Adding new workspace apps changes `bun.lock` (new entries). Any other service's Dockerfile that does `bun install --frozen-lockfile` after copying only *some* workspace `package.json` files will fail with "lockfile had changes, but lockfile is frozen" — because the lockfile now references packages whose `package.json` wasn't copied into that build context. Fix: add `COPY apps/<new-app>/package.json apps/<new-app>/package.json` to every Dockerfile that does a frozen-lockfile install, even if that image never uses the new app.

## Gotcha 6: Radix/shadcn Tabs triggers can silently no-op on a raw `.click()` in headless browser automation

A plain `element.click()` or DOM `.click()` on a Radix `Tabs.Trigger` (`button[role="tab"]`) sometimes doesn't switch tabs in headless CDP automation — Radix listens for pointer events, not just `click`. If a tab switch appears to do nothing (screenshot unchanged), dispatch a full pointer sequence instead:
```js
const rect = btn.getBoundingClientRect();
const opts = { bubbles: true, cancelable: true, clientX: rect.x+rect.width/2, clientY: rect.y+rect.height/2, pointerId: 1, pointerType: 'mouse', isPrimary: true, button: 0 };
btn.dispatchEvent(new PointerEvent('pointerdown', opts));
btn.dispatchEvent(new MouseEvent('mousedown', opts));
btn.dispatchEvent(new PointerEvent('pointerup', opts));
btn.dispatchEvent(new MouseEvent('mouseup', opts));
btn.dispatchEvent(new MouseEvent('click', opts));
```
Plain `<button>` elements (not Radix primitives) usually work fine with a direct `.click()`.

## General lesson

"No backend changes needed" is an assumption, not a fact, whenever a plan adds a *browser-based* consumer to a backend that previously only had server-to-server or same-origin clients. Verify CORS explicitly (a raw `curl -X OPTIONS` with an `Origin` header) before assuming the API surface is browser-ready.
