---
name: logto-connector-feature-not-supported
description: Diagnose Logto self-hosted connector save failing with feature_not_supported (token storage vs SECRET_VAULT_KEK)
---

# Logto Self-Hosted: `feature_not_supported` on Social Connector Save

## When to use
Adding or updating a social connector (e.g. Google OAuth) in Logto Admin Console fails with 3 identical toasts: `This feature is not supported in the current environment.` Only for self-hosted / OSS Logto (fork submodule builds).

## Root cause (most likely)
`Store tokens for persistent API access` (token storage) is ON but `SECRET_VAULT_KEK` is unset. The connector route guards on it:

- `packages/core/src/routes/connector/index.ts` (~line 321): `if (enableTokenStorage) assertThat(EnvSet.values.secretVaultKek, new RequestError({ code: 'request.feature_not_supported', status: 422 }))`
- `EnvSet.values.secretVaultKek` reads env `SECRET_VAULT_KEK` (`packages/shared/src/node/env/GlobalValues.ts`).
- The triple toast is the Console retrying parallel requests, not three separate bugs.
- Other `feature_not_supported` throw sites exist (`routes/system.ts` requires `isCloud`, `routes/admin-user/basics.ts`) but those do not fire on the connector add/update path.

## Fix — pick one
### Option A: turn OFF token storage (default; plain sign-in only)
1. Admin Console → Connectors → Google → Settings → `Store tokens for persistent API access` OFF → Save.
2. No env change, no rebuild. Correct when the backend does not call Google APIs with stored access/refresh tokens.

### Option B: keep token storage (backend needs Google API tokens)
1. Generate key: `openssl rand -hex 32`.
2. Add to `apps/identity/.env`: `SECRET_VAULT_KEK=<hex>`.
3. Pass through in `apps/identity/compose.yml` under `app.environment`: `SECRET_VAULT_KEK: "${SECRET_VAULT_KEK:?Set SECRET_VAULT_KEK in .env}"`.
4. Restart: `docker compose up -d` (runtime env; rebuild not required).
5. Google connector has `isTokenStorageSupported: true` (`packages/connectors/connector-google/src/constant.ts`), so save succeeds once the KEK is set.

## Rule of thumb
Plain `Sign in with Google` → Option A. Only take Option B (another secret to manage) if the backend exchanges stored Google tokens for Calendar/Gmail/etc. API calls.
