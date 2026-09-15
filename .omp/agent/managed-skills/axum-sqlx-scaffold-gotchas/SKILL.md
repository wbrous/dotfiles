---
name: axum-sqlx-scaffold-gotchas
description: "Use when scaffolding a Rust axum + sqlx (SQLite or Postgres) HTTP API from scratch — covers the axum-server 0.6 + hyper 1.x incompatibility (Buf trait not satisfied on TokioExecutor), sqlx SqlitePoolOptions::connect not auto-creating the DB file, avoiding sqlx::query! compile-time macros for reproducible builds, and the trait-based provider pattern (real verification/schema route + documented 501 placeholder route) for splitting an unresolved integration (auth issuance, LLM provider) from otherwise-complete scaffolding."
---

## axum-server 0.6.0 incompatible with axum 0.7 / hyper 1.x

Pulling `axum-server = "0.6"` alongside `axum = "0.7"` (which pulls hyper 1.x
transitively) fails to compile with:

```
error[E0277]: the trait bound `...BodyData: Buf` is not satisfied
  --> axum-server-0.6.0/src/server.rs: TokioExecutor to implement Http2ServerConnExec
```

Fix: bump to `axum-server = "0.8"` (features = ["tls-rustls"]). Check
`cargo info axum-server` for the current latest before pinning — 0.6 is
stale relative to axum 0.7's hyper 1.x dependency.

## sqlx SqlitePoolOptions::connect does not create the DB file

```rust
SqlitePoolOptions::new().connect(&database_url).await
```

fails at runtime with `unable to open database file (code: 14)` even though
the docs suggest a fresh SQLite file should just work. `connect()` alone
never creates a missing file. Fix: parse the URL into `SqliteConnectOptions`
and set `.create_if_missing(true)` explicitly, then `connect_with(...)`:

```rust
let connect_options: SqliteConnectOptions = database_url
    .parse::<SqliteConnectOptions>()?
    .create_if_missing(true);
let pool = SqlitePoolOptions::new().connect_with(connect_options).await?;
```

## Avoid sqlx::query!/query_as! compile-time macros in scaffolds

They require a live `DATABASE_URL` (or `sqlx-cli`-generated `.sqlx/`
offline cache) at *build* time, which breaks reproducible builds for
reviewers/CI who haven't set up a database yet. Use runtime
`sqlx::query(...)`/`sqlx::query_as::<_, T>(...)` with manual `#[derive(FromRow)]`
structs instead — costs a bit of manual struct-mapping but the crate
`cargo build`s standalone with zero DB setup. Document this decision with a
one-line comment right above the `sqlx::migrate!(...).run(&pool)` call in
`main.rs` so future maintainers don't "fix" it by adding macros back.

## Trait-based placeholder pattern for deliberately-unresolved integrations

When a spec explicitly scopes down a piece (e.g. "auth verification must be
real, but token issuance is a placeholder" or "LLM schema is real but no
model provider is wired since hosting is undecided"), don't half-implement
it — make the boundary a first-class trait with zero registered
implementations, and have the route return a real `501 Not Implemented`
with a message pointing at a docs file explaining how to complete it:

```rust
pub trait AuthProvider: Send + Sync {
    fn verify(&self, token: &str) -> Result<Claims, AppError>;
}
// AppState holds Option<Arc<dyn SomeProvider>>; None by default.
// The placeholder route checks it and returns 501 with a docs pointer.
```

This keeps the rest of the codebase (middleware, extractors, downstream
handlers) working against the trait/`Claims` shape, so wiring in a real
implementation later touches exactly one `main.rs` construction line plus
the placeholder route body — nothing else. Ship a `docs/<NAME>.md` naming
the exact trait, the exact file to edit, and the exact registration point.
For local testing against an unimplemented issuance route, a `cargo run
--example mint_dev_token` binary that signs tokens directly is the
sanctioned workaround — keep it out of the server binary itself.

## Verifying encrypted-at-rest fields end-to-end

Don't stop at a unit test for the cipher. POST through the real HTTP route
with a device-scoped token, then GET back through the parent-scoped route,
and assert the returned plaintext field matches byte-for-byte — this proves
the encrypt-on-write / decrypt-on-read wiring in the actual handlers, not
just the crypto primitive.
