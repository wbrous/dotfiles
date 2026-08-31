---
name: bun-publishable-library-scaffold
description: "Use when scaffolding a new Bun/TypeScript library intended for npm publishing (as opposed to an app) — covers the package.json exports/types setup, dual bun-build+tsc build pipeline for JS+.d.ts output, and mise bun version activation gotcha."
---

## Symptom / trigger
User asks to "set up a bun library that can be imported and published to npm."

## Gotcha: bun not on PATH via mise
`bun --version` may fail with `mise ERROR No version is set for shim: bun` even though bun is available via mise. Fix: `mise use -g bun@<version>` (check `~/.config/mise/config.toml` for a pinned version first) before running any bun commands.

## Scaffold layout
```
src/index.ts        # entry point, real exports go here
test/index.test.ts  # bun:test smoke test
tsconfig.json        # declaration-only emit, strict
package.json
.gitignore
```

## Key package.json shape
- `"type": "module"`, `"main"`/`"module"`: `dist/index.js`, `"types"`: `dist/index.d.ts`
- `"exports"`: `{ ".": { "types": "./dist/index.d.ts", "import": "./dist/index.js" } }`
- `"files": ["dist"]` — don't publish src
- `"publishConfig": { "access": "public" }` — required if package name ends up scoped (`@org/name`)
- `devDependencies`: `@types/bun`, `typescript`
- scripts:
  - `"build": "rm -rf dist && bun build ./src/index.ts --outdir dist --target node --format esm && tsc"`
    (bun build bundles JS; bun does NOT emit `.d.ts` files — need a separate `tsc` pass)
  - `"typecheck": "tsc --noEmit"`
  - `"test": "bun test"`
  - `"prepublishOnly": "bun run typecheck && bun run test && bun run build"`

## tsconfig.json essentials
```json
{
  "compilerOptions": {
    "target": "ESNext", "module": "ESNext", "moduleResolution": "bundler",
    "types": ["bun-types"], "strict": true, "declaration": true,
    "emitDeclarationOnly": true, "outDir": "dist", "rootDir": "src",
    "skipLibCheck": true, "esModuleInterop": true, "isolatedModules": true
  },
  "include": ["src"]
}
```
`emitDeclarationOnly: true` is the key line — lets `tsc` only produce `.d.ts` while `bun build` handles the actual JS bundle, avoiding duplicate/conflicting JS output.

## .gitignore
`node_modules/`, `dist/`, `*.log`, `.DS_Store` — keep `bun.lockb`/`bun.lock` tracked for reproducibility (don't ignore it).

## Verification sequence
`bun install` → `bun run typecheck` → `bun run test` → `bun run build` → check `dist/index.js` + `dist/index.d.ts` both exist.

## Before actually publishing
Confirm the chosen package name is available on npm (or scope it `@org/name`) — don't assume an unscoped name is free.
