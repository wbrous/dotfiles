# Zitadel + Axum (Rust API Auth)

Covers standing up self-hosted Zitadel v4 via Docker Compose and building a Rust axum API that validates Zitadel JWTs and calls the Management API.

## Zitadel v4 Docker Compose dev setup

Two-service stack (Postgres + Zitadel), no reverse proxy, reachable on `localhost:8080`.

### Login V2 trap (the critical one)

Zitadel v4's default first-instance setup requires "Login V2" — a separate `zitadel-login` Next.js container behind a path-routing reverse proxy (Traefik/nginx/Caddy), because the core API redirects interactive sign-in to `/ui/v2/login` which only that container serves.

Fix: set on the `zitadel` service, **before first `docker compose up`** (one-time, first-instance-only setting — cannot be changed later via env var, only via Console/Admin API):

```yaml
ZITADEL_DEFAULTINSTANCE_FEATURES_LOGINV2_REQUIRED: "false"
```

This keeps the legacy login UI bundled in the main binary, served at `/ui/login` and `/ui/console` on port 8080. Verify with `curl -sf http://localhost:8080/ui/console` → HTTP 200 with `<title>ZITADEL • Management Console</title>`. Only fall back to adding the `zitadel-login` container + reverse proxy if the login page never comes up despite this flag — don't add it preemptively.

### Masterkey must actually yield 32 chars

`ZITADEL_MASTERKEY` must be exactly 32 characters (DB-level encryption at rest). BROKEN (yields only ~24-29 chars after stripping symbols):

```sh
openssl rand -base64 24 | tr -dc 'A-Za-z0-9' | head -c 32
```

CORRECT (larger source so filtering still leaves 32+):

```sh
openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | head -c 32; echo
```

Always verify length (`echo -n "$MK" | wc -c`) — silently short breaks first-instance setup with a cryptic error.

### Required config

- `command: start-from-init --masterkey "${ZITADEL_MASTERKEY}" --tlsMode disabled`
- `ZITADEL_EXTERNALDOMAIN: localhost`, `ZITADEL_EXTERNALPORT: 8080`, `ZITADEL_EXTERNALSECURE: "false"`, `ZITADEL_TLS_ENABLED: "false"`
- Postgres 14-18 supported; `postgres:16-alpine` works.
- `ZITADEL_FIRSTINSTANCE_ORG_HUMAN_PASSWORD` must satisfy default complexity: 8+ chars, upper, lower, digit, symbol — non-compliant fails first-instance setup at container startup (check `docker compose logs zitadel`).
- Healthcheck: `["CMD", "/app/zitadel", "ready"]` with `start_period: 20s` — first boot (schema migration + first-instance setup) takes ~20-40s.
- `depends_on: postgres: condition: service_healthy` — Zitadel crash-loops if it starts before Postgres accepts connections.

### Verification

```sh
docker compose up -d
docker compose ps   # both services healthy within ~60s
curl -sf http://localhost:8080/ui/console   # HTTP 200
```

_Migrated from: zitadel-docker-compose-dev-setup_

## Zitadel-issued JWT validation + Management API from axum

Context: Rust axum API skeleton against self-hosted Zitadel (docker-compose, Postgres + Zitadel v4.17.3) with JWKS-cached local JWT validation via a tower middleware, and a Management API v2 client with a service-account PAT to create Organizations (org-per-family model).

### Dependency version gotchas

- **sqlx 0.9.0** renamed runtime/TLS features. `runtime-tokio-rustls` no longer exists. Use `runtime-tokio` + `tls-rustls` (or `tls-rustls-aws-lc-rs` / `tls-native-tls`) as *separate* features:

  ```
  cargo add sqlx --features runtime-tokio,tls-rustls,postgres,uuid,chrono,migrate
  ```

  Verify exact feature names by reading the crate's own `Cargo.toml` from the registry cache (`~/.cargo/registry/src/*/sqlx-<ver>/Cargo.toml`) rather than memory — `cargo add --dry-run` also lists valid features when you overshoot.
- **jsonwebtoken 11.x** requires exactly one of the `aws_lc_rs` / `rust_crypto` crypto-provider features, or `jsonwebtoken::decode` panics at runtime (not compile time) with `Could not determine the process-level CryptoProvider from jsonwebtoken crate features.` Add explicitly: `cargo add jsonwebtoken --features aws_lc_rs` (matches what `reqwest`'s rustls stack already pulls in).

### Docker networking gotcha

A compose Postgres service with no `ports:` mapping is NOT reachable from a Rust API running on the host via `localhost:5432` — `sqlx::PgPoolOptions::connect` hangs and returns `PoolTimedOut` (not "connection refused"). Fix: add `ports: ["5432:5432"]` to the Postgres service. Diagnose with plain `psql -h localhost -p 5432 ...` first — faster than watching the Rust binary retry-and-time-out.

### CREATE DATABASE cannot run inside a transaction

A Postgres `docker-entrypoint-initdb.d/*.sh` script (or single `psql -c "stmt1; stmt2;"`) mixing `CREATE USER` + `CREATE DATABASE` fails with `CREATE DATABASE cannot run inside a transaction block` — and the whole batch's implicit transaction rolls back, so the role silently doesn't exist either. Fix: issue each DDL statement as its own separate `psql -c "..."` invocation.

### Fixing a mis-configured Zitadel OIDC app via API

If a human-created OIDC Application doesn't match requirements (e.g. needs `authMethodType: NONE` + Device Authorization Grant, but Console setup left it `PRIVATE_KEY_JWT` + authorization-code-only — visible via `device_authorization` returning `{"error":"invalid_client","error_description":"empty client assertion"}`), and you hold a service-account PAT with IAM Owner, fix it via the Management API:

```sh
curl -s -X POST -H "Authorization: Bearer $PAT" \
  http://localhost:8080/v2/organizations/_search -d '{}'
curl -s -X POST -H "Authorization: Bearer $PAT" -H "x-zitadel-orgid: $ORG_ID" \
  http://localhost:8080/management/v1/projects/_search -d '{}'
curl -s -X POST -H "Authorization: Bearer $PAT" \
  http://localhost:8080/management/v1/projects/$PROJECT_ID/apps/_search -d '{}'

curl -s -X PUT -H "Authorization: Bearer $PAT" -H "Content-Type: application/json" \
  http://localhost:8080/management/v1/projects/$PROJECT_ID/apps/$APP_ID/oidc_config \
  -d '{"redirectUris":[...],"responseTypes":["OIDC_RESPONSE_TYPE_CODE"],
       "grantTypes":["OIDC_GRANT_TYPE_AUTHORIZATION_CODE","OIDC_GRANT_TYPE_DEVICE_CODE"],
       "appType":"OIDC_APP_TYPE_NATIVE","authMethodType":"OIDC_AUTH_METHOD_TYPE_NONE",
       "postLogoutRedirectUris":[...],"accessTokenType":"OIDC_TOKEN_TYPE_JWT"}'
```

### Testing device-authorization-grant login headlessly

`curl -X POST {issuer}/oauth/v2/device_authorization` returns `{device_code, user_code, verification_uri_complete, ...}`. Opening `verification_uri_complete` in a persistent headless browser can land on a *cached SSO session* for a different logged-in user (e.g. `admin@zitadel.localhost`) with WebAuthn/passkey 2FA enrolled — dead-ends the flow. Fix:

1. Explicitly clear cookies on the tab before navigating (CDP `Network.clearBrowserCookies` + `Network.clearBrowserCache`), or open a fresh tab/profile.
2. If the intended test account also has 2FA, create a throwaway human via the Management API with `"password": {"password": "...", "changeRequired": false}` and no MFA, instead of bypassing 2FA on an existing account.
3. Login flow via aria-snapshot browser tool: `.press("Enter")` after `.fill(...)` on the username field — a plain `.click()` on "Next" sometimes doesn't register the just-typed value; Enter reliably submits.
4. The 2FA *setup* step during a fresh user's first login is skippable ("Skip") — click Skip once, then continue to consent ("Allow"/"Deny").
5. **The `device_code` is single-use** — every `/oauth/v2/token` exchange attempt (success or failure) consumes it. For a retry, get a brand new `device_authorization` + redo the browser approval; don't reuse an old `device_code`.

### sqlx query_as with runtime SQL

This project intentionally avoids the `sqlx::query!` compile-time macro (reproducible builds without a live DB at compile time), using `sqlx::query_as::<_, T>(sql).bind(...)` with `T: sqlx::FromRow` instead — works with `postgres`+`uuid`+`chrono`+`migrate` features, no offline-mode setup needed.

_Migrated from: zitadel-rust-axum-api-integration_

## axum + sqlx scaffold gotchas

**axum-server 0.6.0 incompatible with axum 0.7 / hyper 1.x.** Pulling `axum-server = "0.6"` alongside `axum = "0.7"` (hyper 1.x) fails to compile: `error[E0277]: the trait bound ...BodyData: Buf is not satisfied` (`TokioExecutor to implement Http2ServerConnExec`). Fix: bump to `axum-server = "0.8"` (features `tls-rustls`). Check `cargo info axum-server` for current latest before pinning.

**`SqlitePoolOptions::connect` does not create the DB file.** Fails at runtime with `unable to open database file (code: 14)`. `connect()` alone never creates a missing file. Fix:

```rust
let connect_options: SqliteConnectOptions = database_url
    .parse::<SqliteConnectOptions>()?
    .create_if_missing(true);
let pool = SqlitePoolOptions::new().connect_with(connect_options).await?;
```

**Avoid `sqlx::query!`/`query_as!` compile-time macros in scaffolds.** They require a live `DATABASE_URL` (or `sqlx-cli`-generated `.sqlx/` offline cache) at *build* time, breaking reproducible builds for reviewers/CI. Use runtime `sqlx::query(...)`/`query_as::<_, T>(...)` with manual `#[derive(FromRow)]` structs. Document with a one-line comment above `sqlx::migrate!(...).run(&pool)` in `main.rs` so maintainers don't "fix" it back.

**Trait-based placeholder pattern for deliberately-unresolved integrations.** When a spec scopes something down (e.g. "auth verification real, but token issuance is a placeholder"), don't half-implement — make the boundary a first-class trait with zero registered implementations, and return real `501 Not Implemented` with a docs pointer:

```rust
pub trait AuthProvider: Send + Sync {
    fn verify(&self, token: &str) -> Result<Claims, AppError>;
}
// AppState holds Option<Arc<dyn SomeProvider>>; None by default.
```

This keeps middleware/extractors/handlers working against the trait/`Claims` shape, so wiring a real implementation later touches one `main.rs` construction line plus the placeholder route body. Ship a `docs/<NAME>.md` naming the trait, the file to edit, and the registration point. For local testing, a `cargo run --example mint_dev_token` binary that signs tokens directly is the sanctioned workaround — keep it out of the server binary.

**Verifying encrypted-at-rest fields end-to-end:** don't stop at a cipher unit test. POST through the real HTTP route with a device-scoped token, then GET back through the parent-scoped route, and assert the returned plaintext matches byte-for-byte.

_Migrated from: axum-sqlx-scaffold-gotchas_
