---
name: zitadel-rust-axum-api-integration
description: "Use when building a Rust (axum) API that validates Zitadel-issued JWTs via JWKS and/or calls Zitadel's Management API v2 with a service-account PAT — e.g. optic.fyi's apps/api against apps/accounts' self-hosted Zitadel. Covers sqlx 0.9 feature-name changes, jsonwebtoken 11's required CryptoProvider feature, exposing Postgres to the host for a non-containerized API, fixing a mis-configured Zitadel OIDC Application via the Management API instead of re-asking a human, and testing device-authorization-grant login headlessly when the default admin has WebAuthn 2FA."
---

## Context

Built a Rust axum API skeleton (`apps/api`) against a self-hosted Zitadel
instance (`apps/accounts`, docker-compose, Postgres + Zitadel v4.17.3) with:
JWKS-cached local JWT validation via a tower middleware, and a Zitadel
Management API v2 client authenticated with a service-account PAT to create
Organizations (org-per-family model).

## Dependency version gotchas (current crates.io versions as of this task)

- **sqlx 0.9.0** renamed runtime/TLS features. `runtime-tokio-rustls` (used
  in older tutorials/docs) no longer exists. Use `runtime-tokio` +
  `tls-rustls` (or `tls-rustls-aws-lc-rs` / `tls-native-tls`) as *separate*
  features:
  ```
  cargo add sqlx --features runtime-tokio,tls-rustls,postgres,uuid,chrono,migrate
  ```
  Verify exact feature names by reading the crate's own `Cargo.toml` from
  the registry cache (`~/.cargo/registry/src/*/sqlx-<ver>/Cargo.toml`)
  rather than guessing from memory or older docs — `cargo add --dry-run`
  also lists valid features when you overshoot.

- **jsonwebtoken 11.x** requires exactly one of the `aws_lc_rs` /
  `rust_crypto` crypto-provider features enabled, or `jsonwebtoken::decode`
  panics at runtime (not at compile time!) with:
  ```
  Could not automatically determine the process-level CryptoProvider from
  jsonwebtoken crate features.
  ```
  This is easy to miss because the crate compiles fine and only crashes on
  the *first actual JWT decode call* in production traffic. Add explicitly:
  ```
  cargo add jsonwebtoken --features aws_lc_rs
  ```
  (matches what `reqwest`'s rustls stack already pulls in, avoiding a
  second crypto backend).

- **CREATE DATABASE cannot run inside an implicit transaction.** A
  Postgres `docker-entrypoint-initdb.d/*.sh` script (or any single
  `psql -c "stmt1; stmt2;"` invocation) that mixes `CREATE USER` +
  `CREATE DATABASE` in one heredoc/command fails with "CREATE DATABASE
  cannot run inside a transaction block" — and because the whole batch is
  one implicit transaction, the `CREATE USER` gets rolled back too, so the
  role silently doesn't exist. Fix: issue each DDL statement as its own
  separate `psql -c "..."` invocation.

## Docker networking gotcha

A docker-compose Postgres service with no `ports:` mapping (only reachable
from other containers in the compose network, e.g. by a sibling `zitadel`
service) is NOT reachable from a Rust API running directly on the host via
`localhost:5432` — `sqlx::PgPoolOptions::connect` hangs and eventually
returns `PoolTimedOut` (not a clear "connection refused", since the health
check itself times out silently). Fix: add `ports: ["5432:5432"]` to the
Postgres service. Diagnose with a plain `psql -h localhost -p 5432 ...`
outside the app first — much faster feedback than watching the Rust binary
retry-and-time-out.

## Fixing a mis-configured Zitadel OIDC Application via API instead of re-asking the human

If a human-created-in-Console OIDC Application doesn't match required
settings (e.g. plan needs `authMethodType: NONE` + Device Authorization
Grant enabled, but Console setup left it as `PRIVATE_KEY_JWT` +
authorization-code-only — visible via
`device_authorization` returning `{"error":"invalid_client","error_description":"empty client assertion"}`),
and you already hold a service-account PAT with IAM Owner, you can inspect
and fix it yourself via the Management API rather than looping back to the
human:

```sh
# find org -> project -> app id
curl -s -X POST -H "Authorization: Bearer $PAT" \
  http://localhost:8080/v2/organizations/_search -d '{}'
curl -s -X POST -H "Authorization: Bearer $PAT" -H "x-zitadel-orgid: $ORG_ID" \
  http://localhost:8080/management/v1/projects/_search -d '{}'
curl -s -X POST -H "Authorization: Bearer $PAT" \
  http://localhost:8080/management/v1/projects/$PROJECT_ID/apps/_search -d '{}'

# fix it
curl -s -X PUT -H "Authorization: Bearer $PAT" -H "Content-Type: application/json" \
  http://localhost:8080/management/v1/projects/$PROJECT_ID/apps/$APP_ID/oidc_config \
  -d '{"redirectUris":[...],"responseTypes":["OIDC_RESPONSE_TYPE_CODE"],
       "grantTypes":["OIDC_GRANT_TYPE_AUTHORIZATION_CODE","OIDC_GRANT_TYPE_DEVICE_CODE"],
       "appType":"OIDC_APP_TYPE_NATIVE","authMethodType":"OIDC_AUTH_METHOD_TYPE_NONE",
       "postLogoutRedirectUris":[...],"accessTokenType":"OIDC_TOKEN_TYPE_JWT"}'
```

## Testing device-authorization-grant login headlessly (Computer Use / browser tool)

`curl -X POST {issuer}/oauth/v2/device_authorization` returns
`{device_code, user_code, verification_uri_complete, ...}`. Opening
`verification_uri_complete` in a persistent headless browser tab can land
you on a *cached SSO session* for a different, already-logged-in user (e.g.
the Zitadel instance's own `admin@zitadel.localhost`) whose account has
WebAuthn/passkey 2FA enrolled — which cannot be completed headlessly and
will dead-end the flow. Fix:

1. Explicitly clear cookies on the tab before navigating
   (`page.target().createCDPSession()` then
   `Network.clearBrowserCookies` + `Network.clearBrowserCache`), or open a
   genuinely fresh tab/profile.
2. If the *intended* test account also has 2FA required, create a
   throw-away human user via the Management API with
   `"password": {"password": "...", "changeRequired": false}` and no MFA
   requirement, instead of trying to bypass 2FA on an existing account.
3. Login flow via the aria-snapshot browser tool needs `.press("Enter")`
   after `.fill(...)` on the username field — a plain `.click()` on "Next"
   sometimes doesn't register the just-typed value in time; Enter reliably
   submits.
4. The 2FA *setup* step during a fresh user's first login is skippable
   ("Skip" button) — don't skip past it into an infinite loop, click Skip
   once, then continue to the consent ("Allow"/"Deny") screen.
5. **The device_code is single-use** — every `/oauth/v2/token` exchange
   attempt against it (success or failure) consumes it. If you need to
   retry the token exchange, get a brand new `device_authorization` +
   redo the browser approval; don't reuse an old `device_code`.

## sqlx query_as with runtime SQL vs sqlx::query! macro

This project intentionally avoids the `sqlx::query!` compile-time macro
(reproducible builds without a live DB at compile time — see also
`axum-sqlx-scaffold-gotchas`), using `sqlx::query_as::<_, T>(sql).bind(...)`
instead, which requires the `T: sqlx::FromRow` derive and works fine with
`postgres`+`uuid`+`chrono`+`migrate` features (no extra offline-mode setup
needed since no macro is used).
