---
name: bun-test-jsx-dev-runtime-cwd-sensitivity
description: "Use when bun test fails with \"Cannot find module 'react/jsx-dev-runtime'\" (or similar jsx-runtime resolution error) in leetcode-discord-bot's bot/src/cv2/elements.test.tsx, or when bun test results seem flaky/inconsistent between invocations in this repo."
---

## Symptom

`bun test` fails on `bot/src/cv2/elements.test.tsx` with:

```
error: Cannot find module 'react/jsx-dev-runtime' from '.../bot/src/cv2/elements.test.tsx'
```

Other tests in the same run may still pass, making it look like flaky/contaminated test state.

## Root cause

`bun test`'s tsconfig discovery (and thus `jsxImportSource` resolution) is **cwd-relative, not file-relative**. This repo (`leetcode-discord-bot`) has no root-level `tsconfig.json` or `package.json` — configuration lives only in `bot/tsconfig.json`, which maps `jsxImportSource: "#cv2"` to the local cv2 JSX runtime.

Running `bun test` from the **repo root** cannot find `bot/tsconfig.json`, so bun falls back to the default `react/jsx-dev-runtime`, which isn't installed — hence the error.

## Fix / correct invocation

Always run tests from inside `bot/`:

```bash
cd bot && bun test
```

This matches `bot/package.json`'s `"test": "bun test"` script, which assumes `bot/` as cwd.

## Verification performed

- `cd bot && bun test` × 5 consecutive runs → 55/55 pass every time, no flakiness.
- `bun test` from repo root → reliably reproduces the `react/jsx-dev-runtime` failure.

## Takeaway

If a `bun test` failure in this repo looks unrelated to your actual change (e.g. a JSX/cv2 module resolution error you didn't touch), first check invocation cwd before suspecting test pollution or flakiness.
