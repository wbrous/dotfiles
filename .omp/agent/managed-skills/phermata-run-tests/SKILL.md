---
name: phermata-run-tests
description: "Use when running the test suite in the phermata repo (convex-test based tests import.meta.glob require vite) — always run via bunx vitest run [path], never bun test."
---

## Symptom
`bun test convex/foo.test.ts` fails every test with:
```
TypeError: import.meta.glob is not a function.
```

## Cause
`convex/*.test.ts` files use `convex-test`, which relies on `import.meta.glob` — a Vite-only API. Bun's native test runner does not implement it. `package.json`'s `"test"` script is `vitest run`, not bun's runner.

## Fix
Always run tests with vitest, not `bun test`:
```
bunx vitest run                      # full suite
bunx vitest run convex/foo.test.ts   # single file
```

Typecheck separately with `bunx tsc --noEmit -p tsconfig.json` (no dedicated `typecheck` npm script exists in this repo).
