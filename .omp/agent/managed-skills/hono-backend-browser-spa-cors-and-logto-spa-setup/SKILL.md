---
name: hono-backend-browser-spa-cors-and-logto-spa-setup
description: "Use when wiring a new browser SPA (Vite/React) to a Hono+Logto backend in a Bun workspace monorepo: CORS 404/blocked preflight, Logto oidc.invalid_target, or Docker frozen-lockfile failures after adding a workspace app."
---

## Symptom: browser SPA can't reach a Hono backend cross-origin

If a Hono backend has no `hono/cors` middleware, every cross-origin browser
request fails: preflight `OPTIONS` returns 404 (not 204), and the browser
blocks the real request even if the server would return 200. `curl` from a
non-browser context looks fine, which masks this — always test with
`curl -i -X OPTIONS <url> -H "Origin: <spa-origin>" -H "Access-Control-Request-Method: GET"`
to confirm.

Fix: add `hono/cors` to the root `Hono()` chain, driven by an env var
(comma-separated allowed origins, parsed via zod `.transform(s => s.split(","))`),
not hardcoded — different dashboards/deploys need different origins.

```ts
import { cors } from "hono/cors";
app.use("*", cors({
  origin: env.CORS_ALLOWED_ORIGINS,
  allowHeaders: ["Content-Type", "Authorization"],
  allowMethods: ["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
}));
```

Wire the env var through `docker-compose.yml`'s service `environment:` block
and `.env.example` too, or the container won't pick it up.

## Symptom: Logto `oidc.invalid_target` / infinite "Loading…" after sign-in

`useLogto().getAccessToken(resource)` throws `oidc.invalid_target` if the
`resource` wasn't declared on the **LogtoConfig itself** — passing it only
to a `signIn()` call is not enough for `@logto/react`. Fix:

```ts
export const logtoConfig: LogtoConfig = {
  endpoint, appId,
  resources: [API_RESOURCE], // must list every resource getAccessToken() will ever request
};
```

After fixing this, existing sign-in sessions from before the fix are stale —
clear local/session storage (or sign out) and sign in again; the error
won't self-heal on hot reload alone.

## Symptom: `api-client`'s `headers` option can't be async

If a typed Hono RPC client's `ApiClientOptions.headers` is
`Record<string,string> | (() => Record<string,string>)` (synchronous only)
but your auth flow needs `await getAccessToken(...)`, inject the token via
the `fetch` override instead, not `headers`:

```ts
createApiClient({
  baseUrl,
  fetch: (async (input, init) => {
    const token = await getAccessToken(resource);
    const headers = new Headers(init?.headers);
    if (token) headers.set("Authorization", `Bearer ${token}`);
    return fetch(input, { ...init, headers });
  }) as typeof fetch, // cast needed: Bun's `typeof fetch` includes extra members like `preconnect`
});
```

For plain bearer-token auth (already have a stored token, no async mint
step), the synchronous `headers: () => ({...})` option is fine — just make
sure the return type is exactly `Record<string, string>` (no optional/
undefined values) or TS rejects it.

## Symptom: Docker build fails `lockfile had changes, but lockfile is frozen` after adding a new Bun workspace app

A Dockerfile's `deps` stage that does `COPY <selected-package.json-files> && bun install --frozen-lockfile`
must copy **every** workspace member's `package.json` referenced in the root
`bun.lock`, not just the ones the image actually needs at runtime. Adding a
new `apps/*` workspace member (even one irrelevant to a given service's
image) changes `bun.lock`, and any other service's Docker build that doesn't
also `COPY` that new app's `package.json` will fail the frozen-lockfile
install. Fix: add a `COPY apps/<new-app>/package.json apps/<new-app>/package.json`
line to every Dockerfile in the monorepo when adding a workspace app.

## shadcn CLI on a fresh Vite scaffold

`shadcn init -y -b radix` alone still prompts interactively for a *preset*
(a theme name like `nova`, `vega`, ...) even with `-y`. Use
`-p <preset> -b <base>` together, e.g. `-p nova -b radix`, to fully skip
prompts. Presets are separate from `-b`/base library choice.

Also: `bun add <workspace-package-name>` fails with a 404 against the npm
registry for internal `workspace:*` deps that aren't published — it won't
auto-resolve them from the monorepo. Add every other dep with `bun add`
first, then hand-edit `package.json` to add `"@scope/pkg": "workspace:*"`,
and run `bun install` from the repo root to link it.

## Radix/shadcn `Tabs` triggers sometimes ignore a plain `element.click()`

Radix's `TabsTrigger` listens for pointer events, not just `click`. In
automated/headless testing, a bare `btn.click()` can silently no-op on a
`button[role="tab"]` while working fine on ordinary `<Button>`s. If a tab
switch doesn't visibly happen after `.click()`, dispatch the full sequence
instead:

```js
const rect = btn.getBoundingClientRect();
const opts = { bubbles: true, cancelable: true, clientX: rect.x+rect.width/2, clientY: rect.y+rect.height/2, pointerId: 1, pointerType: 'mouse', isPrimary: true, button: 0 };
btn.dispatchEvent(new PointerEvent('pointerdown', opts));
btn.dispatchEvent(new MouseEvent('mousedown', opts));
btn.dispatchEvent(new PointerEvent('pointerup', opts));
btn.dispatchEvent(new MouseEvent('mouseup', opts));
btn.dispatchEvent(new MouseEvent('click', opts));
```
