# Backend Env Config Pitfalls + Daytona Sandbox Testing

Covers the pytest import-time env-pollution trap (FastAPI/Flask services reading `os.environ`), and end-to-end deployment testing on Daytona sandboxes via REST.

## Import-time env caching vs per-request reads (FastAPI/Flask + pytest)

**Problem.** A service module reads a config value via `os.environ.get("SOME_PATH", default)` *inside* a request handler (per-request), while a sibling value (e.g. a secret) is read once at import time into a module-level constant. Invisible in normal deployment (env set once at process start) but breaks when multiple pytest test files share a process, or anything in-process mutates `os.environ` after startup.

**Symptom.** Several test files, each structured like:

```python
os.environ["SOME_PATH"] = str(tmp_path)   # module level, before import
from myapp import app
```

Each file's tests pass alone (`pytest a/test_x.py -q`) but fail together (`pytest a/test_x.py b/test_y.py -q`), often with a low-level error like `sqlite3.OperationalError: no such table: events` pointing at a *different valid* tmp path/resource — the path got silently swapped, not deleted.

**Root cause.** pytest **collects (imports) every test file first**, then **runs** the collected tests. If a module reads an env var at *request time* (`os.environ.get("DB_PATH")` inside a route handler, not cached at import), the test file imported *last* during collection wins that var — even though its own tests haven't run yet — because `os.environ` is process-global. Test file A's handler then serves test file B's config during A's *execution*, which happens after all collection is done. Standalone runs never expose this ordering-dependent cross-file mutation.

**Fix.** Resolve every env-derived config value **once, at module import time**, into a module-level constant — the same way secrets are typically already handled — and have handlers read the constant, never `os.environ` directly:

```python
# at module scope, right after app = FastAPI(...)
DB_PATH = os.environ.get("ORGBOT_DB_PATH", "./data/orgbot.db")

@app.post("/thing")
async def handler(...):
    db = lib.db.connect(DB_PATH)   # not os.environ.get(...) here
```

Env vars are a startup-time deployment concern, not a per-request one. This also makes cross-file pytest runs order-independent: each test file's module-level env mutation now only affects its own already-resolved constant, not a live read a later import can clobber.

**If you can't touch the service source:** move the test file's env mutation into a `pytest.fixture` (function- or module-scoped, `monkeypatch.setenv` preferred — auto-restores) instead of bare module-top-level code, so it runs at test-execution time rather than collection/import time. Only works if the app already reads the var per-request rather than caching at import — check first, since many apps intentionally cache secrets at import and need the resolve-once fix regardless.

**Diagnosing:** all per-file suites pass individually but some fail only together; failure is "file/table/resource not found" pointing at a plausible-but-wrong path; grep for `os\.environ\[.*\]\s*=` at column 0 (module top-level, not inside a fixture/function) across the combined test files — the ones setting the same key at import time are the culprits, last-imported wins. Grep the app source for `os.environ.get(` inside a route handler/function body (vs module top-level right after `app = FastAPI(...)`) to find the asymmetric read that lets pollution matter. Bisect by running suspected-conflicting file pairs together (`pytest a/test_x.py b/test_y.py -q`).

_Migrated from: fastapi-service-env-var-import-time-caching, pytest-import-time-env-pollution_

## Daytona sandbox REST deployment test

Use when running a real end-to-end deployment/provisioning test (e.g. a `bootstrap-ubuntu.sh`, systemd service install, or Docker Compose stack) against a Daytona sandbox via its REST API.

**Setup:**

1. `POST https://app.daytona.io/api/sandbox` with `{"snapshot": "<name>"}` — pass `"autoStopInterval": 0` if the sandbox must stay up for a human afterward (default auto-stops after 15 min idle).
2. Poll `GET https://app.daytona.io/api/sandbox/{id}` until `"state":"started"`.
3. Upload files: `POST https://proxy.app.daytona.io/toolbox/{sandboxId}/files/upload?path=<dest>` with `-F "file=@<local path>"`. Uploads are occasionally flaky (curl exit/HTTP code `000` with no error text) — always check the HTTP code and retry the specific file once; don't assume the whole batch failed.
4. Run commands: `POST https://proxy.app.daytona.io/toolbox/{sandboxId}/process/execute` with `{"command": "...", "timeout": <seconds>}`. `timeout` in the JSON caps server-side execution; also set `curl --max-time` a bit higher. Long installs (apt, `docker compose pull`) routinely take 30-90s.
5. Container-class sandboxes have `PID 1 = daytona`, not systemd (`ls /run/systemd/system` → no such file). Any script step doing `systemctl enable --now X` fails with `System has not been booted with systemd ... Can't operate.` — expected on this sandbox class, not a script bug. Docker installs fine via apt; start it manually: `nohup dockerd >/tmp/dockerd.log 2>&1 & disown; sleep 4; docker version`. Nested Docker (compose inside the sandbox) works fine this way.
6. Teardown: `docker compose down -v` inside the sandbox first (if you care about clean removal), then `DELETE https://app.daytona.io/api/sandbox/{id}?force=true`.

**Exposing the deployed service for live human interaction.** The app typically binds `127.0.0.1:<port>` inside the sandbox's compose network — reachable via `curl http://localhost:<port>` inside, but not from the outside internet. Daytona's preview URL mechanism exposes it:

- **Standard preview URL** (`GET /api/sandbox/{id}/ports/{port}/preview-url`): returns a URL + sandbox-wide token sent via `x-daytona-preview-token` header. The token authenticates *every* port on the sandbox (web terminal, toolbox API, …) — treat as a full sandbox credential, never hand to the end user as a link.
- **Signed preview URL** (`GET /api/sandbox/{id}/ports/{port}/signed-preview-url?expiresInSeconds=<n>`): embeds auth in the *hostname* (`https://{port}-{token}.{daytonaProxyDomain}`). No header needed — safe to hand to a human, scoped to one port, revokable/expires independently. Max 86400s (24h); always set explicitly (default 60s).

**Critical gotcha:** if the deployed app makes its own internal self-referencing HTTP calls using a "public URL" config value (e.g. Logto's `ENDPOINT`, used for OIDC discovery self-consistency, JWKS, etc.), that value **must be set to the exact signed preview URL**, not `http://localhost:<port>` and not a plain public-looking placeholder. With `localhost`, the app's emitted URLs (issuer, discovery doc) won't match what the external caller used → breaks clients validating issuer match. With a *standard* (non-signed) preview URL, the app's own outbound self-calls get rejected by Daytona's proxy (401/warning page, no `x-daytona-preview-token` header on internal calls). The **signed** URL fixes both: token baked into the hostname, so internal fetches and the human's browser hit the same already-authenticated URL — verified end-to-end (`curl` from outside to `/oidc/.well-known/openid-configuration` → 200, issuer = signed preview hostname).

Concrete flow: get the signed preview URL for the port *before* writing the app's `.env`/config → write it into the public-endpoint config (e.g. `sed -i 's|^ENDPOINT=.*|ENDPOINT=<signed url>|' .env`) → bring the stack up → verify from outside (plain `curl`, no special headers) that the service responds and self-reported URLs match the signed hostname → hand the plain signed URL to the user. Also tell the user explicitly: which ports are intentionally *not* exposed (e.g. an admin console meant to stay private), the token's expiry, and that `autoStopInterval:0` prevents idle death but won't survive a Daytona-side outage — recreate from scratch rather than recovering a stale ID.

_Migrated from: daytona-sandbox-rest-api-deployment-test_
