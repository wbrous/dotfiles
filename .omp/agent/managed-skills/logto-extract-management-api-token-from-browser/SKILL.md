---
name: logto-extract-management-api-token-from-browser
description: Need a Logto M2M token or Management API access for smoke tests without a saved admin API client; console already logged in via browser.
---

When you need to call Logto's Management API (create applications, resources, roles) but have no saved M2M credentials for it, and there's a browser session already logged into the Logto Admin Console (`http://localhost:3002/console` in a typical local dev setup, core OIDC on `:3001`), you can bootstrap access without a UI click-marathon:

1. Open/reuse the console tab (`browser.open({name, url, persist: true})`), confirm it's authenticated (not redirected to sign-in).
2. Extract the console's own cached Management API access token straight out of `localStorage`:
   ```js
   const mgmtToken = await tab.run(async ({page}) => page.evaluate(() =>
     JSON.parse(localStorage.getItem("logto:admin-console:accessToken"))["@https://default.logto.app/api"].token
   ));
   ```
   The key is `logto:<app-id>:accessToken`, and it's a JSON map keyed by resource indicator (`@` = base scopes, `@https://default.logto.app/api` = Management API, `@#t-<org>` = org-scoped).
3. Call the Management API directly from server-side `fetch` (not from inside the page) using `Authorization: Bearer ${mgmtToken}` against the **core** service port (`http://localhost:3001/api/...`), not the console's own port (3002) — 3002 is the static console frontend/proxy and returns 401 for direct API calls.
4. Useful endpoints: `GET /api/applications`, `GET /api/resources` (list API resources + ids), `POST /api/applications` (create), `GET /api/applications/:id/secrets` (client secret — not returned on the base GET).
5. To mint an M2M client-credentials token for one of your own API resources, you do NOT need to assign a role/permission first if you just need *some* valid token with the right `aud` for testing auth wiring — Logto will happily issue a token via:
   ```
   POST /oidc/token
   grant_type=client_credentials&client_id=...&client_secret=...&resource=<your-resource-indicator>
   ```
   Only skip role-assignment when you're testing generic bearer-auth acceptance, not scope-based authorization.
6. Clean up afterward: `DELETE /api/applications/:id` on the temporary M2M app.

This avoids grinding through Logto's "Create application" → "Assign roles" modal UI via brittle DOM clicks, which is flaky (buttons don't always register clicks on the first `.click()` call in headless Puppeteer — re-observe and retry via `tab.id(n).click()` if a `text/...` selector click silently no-ops).
