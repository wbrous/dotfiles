---
name: fastapi-service-env-var-import-time-caching
description: "Use when writing or debugging FastAPI/Flask-style services (or their pytest suites) that read config from os.environ — especially when multiple services/test modules share a process (e.g. running several test_*.py files together with pytest) and env-var-derived DB paths, secrets, or config paths seem to silently change between requests or between test files."
---

## Problem

A service module reads a config value via `os.environ.get("SOME_PATH", default)`
*inside* a request handler (per-request), while a sibling value (e.g. a secret) is
read once at import time into a module-level constant. This asymmetry is invisible
in normal deployment (env is set once at process start and never changes) but breaks
in two situations:

1. **pytest running multiple test files together.** pytest *imports* (collects) all
   test modules before running any test function. If two different test files each
   set `os.environ["SOME_PATH"] = <their own tmp path>` at *import time* (module
   top-level, not inside a fixture), the last-imported file's value wins for every
   test that reads that var per-request — even tests in a file that imported first
   and set its own value. Symptom: a test suite passes standalone but fails
   (`sqlite3.OperationalError: no such table: ...`, wrong file read, etc.) only when
   run alongside other suites in one pytest invocation.
2. Any long-lived process where something else in-process mutates `os.environ` after
   startup (rare in prod, common in test harnesses / notebooks / multi-app test
   runners).

## Fix

Resolve every env-derived config value **once, at module import time**, into a
module-level constant — the same way secrets are typically already handled — and
have request handlers read the constant, never `os.environ` directly:

```python
# at module scope, right after app = FastAPI(...)
DB_PATH = os.environ.get("ORGBOT_DB_PATH", "./data/orgbot.db")

@app.post("/thing")
async def handler(...):
    db = lib.db.connect(DB_PATH)   # not os.environ.get(...) here
```

This is strictly better even outside testing: env vars are a startup-time
deployment concern, not a per-request one, and re-reading `os.environ` on every
request only invites exactly this class of bug.

## Diagnosing it

- All the per-file test suites pass individually but some subset fails only when
  run together (`pytest a/test_x.py b/test_y.py` fails, `pytest a/test_x.py` alone
  passes).
- Failure mode is "file/table/resource not found" pointing at what should be a
  correct tmp path — i.e. the path got silently swapped for a *different* valid tmp
  path/resource, not a nonexistent one.
- Grep for `os\.environ\[.*\]\s*=` at column 0 (module top-level, not inside a
  fixture/function) across the test files being combined; whichever ones set the
  same key at import time are the culprits — the last one imported wins process-wide.
- Grep the app/service source for `os.environ.get(` inside a route handler / function
  body (vs. at module top level right after `app = FastAPI(...)`) to find the
  asymmetric read that lets the pollution matter.

## Also acceptable (if you can't touch the service source)

Move the test file's env mutation into a `pytest.fixture` (function- or
module-scoped, `monkeypatch.setenv` preferred over raw `os.environ[...] = ...` since
it auto-restores) instead of bare module-top-level code, so it runs at test-execution
time rather than at collection/import time. This only works if the app under test
already reads the var per-request rather than caching it — check that first, since
many apps intentionally cache secrets at import and would need the "resolve once"
fix above regardless.
