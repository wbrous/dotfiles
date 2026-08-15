---
name: pytest-import-time-env-pollution
description: "Use when running multiple pytest test files together (e.g. pytest a/test_x.py b/test_y.py) that each configure a FastAPI/Flask app via env vars before importing it, and tests pass individually but fail only when run together with errors like \"no such table\" / wrong config / wrong DB path."
---

## Symptom

Several test files, each structured like:

```python
os.environ["SOME_PATH"] = str(tmp_path)   # module level, before import
from myapp import app                      # app reads env var — sometimes at
                                             # import time, sometimes per-request
```

Each file's tests pass when run alone (`pytest a/test_x.py -q`) but fail when
run together (`pytest a/test_x.py b/test_y.py -q`), often with a low-level
error like `sqlite3.OperationalError: no such table: events` that looks
unrelated to the actual change under test.

## Root cause

pytest **collects (imports) every test file first**, then **runs** the
collected tests. If a module reads an env var at *request time* (e.g.
`os.environ.get("DB_PATH")` inside a route handler, not cached at import),
then whichever test module was imported *last* during collection wins that
env var — even though its own tests haven't run yet — because os.environ is
process-global. Test file A's handler then serves test file B's config
during file A's *test execution*, which happens after all collection is
already done.

This bites even when every individual file works standalone, because
standalone runs never expose the ordering-dependent cross-file mutation.

## Fix

Prefer resolving config/env vars **once at import time** into a module-level
constant, not per-request via `os.environ.get(...)` inside the handler:

```python
# do this once at import
DB_PATH = os.environ.get("ORGBOT_DB_PATH", "./data/orgbot.db")

@app.post("/thing")
async def handler():
    db = connect(DB_PATH)   # not os.environ.get(...) here
```

This mirrors how a startup-time secret (e.g. a webhook secret) is usually
already handled — treat every env-derived config value as a deployment-time
concern resolved once, not a live, mutable-mid-process one. It also happens
to make cross-file pytest runs order-independent for free, since each test
file's module-level env mutation now only affects that module's own already-
resolved constant, not a live read that a later import can clobber.

If a value genuinely must be re-read per request (rare), isolate it behind a
`monkeypatch`-based fixture scoped to that test function instead of a raw
module-level `os.environ[...] =` assignment, so it doesn't leak across test
files that share the same pytest process.

## Diagnostic shortcut

Bisect by running suspected-conflicting file pairs together
(`pytest a/test_x.py b/test_y.py -q`) rather than the full suite, to isolate
which later-imported module's `os.environ[...] =` at module scope is
clobbering the first module's config before the first module's tests
actually execute.
