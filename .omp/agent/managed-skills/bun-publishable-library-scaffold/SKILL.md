---
name: bun-publishable-library-scaffold
description: "Use when scaffolding a new Bun/TypeScript library intended for npm publishing (as opposed to an app) — covers package.json exports/types setup, dual bun-build+tsc build pipeline, optional-peer externalization, and the GitHub-prep checklist (README, LICENSE, CI, pack verification)."
---

# Bun publishable library scaffold

Scaffolding a new Bun/TypeScript library meant for npm publishing (as opposed to an app). Covers the package.json exports/types setup, dual bun-build+tsc build pipeline for JS+.d.ts output, and the mise bun version activation gotcha.

## Prereqs

- `mise use -g bun@1.3.14` if the `bun` shim errors ("No version is set for shim: bun") — a `bun:test` import needs `@types/bun` installed.

## package.json

- `"type": "module"`, `"module"`, `"main"`, `"types"` all pointing at `dist/index.js` / `dist/index.d.ts`.
- `"exports": { ".": { "types": "./dist/index.d.ts", "import": "./dist/index.js" } }` — the `types` condition FIRST.
- `"files": ["dist"]` — npm auto-includes README/LICENSE regardless.
- `"sideEffects": false`, `"engines": { "node": ">=18" }`.
- `"publishConfig": { "access": "public" }` for scoped packages.
- `"prepublishOnly": "bun run typecheck && bun run test && bun run build"`.

## Build pipeline

- `"build": "rm -rf dist && bun build ./src/index.ts --outdir dist --target node --format esm && tsc"` — bun bundles JS; `tsc` emits `.d.ts`.
- tsconfig: `strict`, `declaration: true`, `emitDeclarationOnly: true`, `rootDir: src`, `outDir: dist`, `types: ["bun-types"]`.
- **Externalize optional peers** in the build: `--external playwright --external @mherod/get-cookie` — optional peers that are dynamically imported (e.g. Playwright for browser automation, @mherod/get-cookie for Chromium/Safari cookie decryption) must NOT be bundled. Mark them `peerDependencies` + `peerDependenciesMeta: { pkg: { optional: true } }`.
- Keep dynamic `import()` for optional peers; use local structural interfaces instead of their types so consumers without the peer stay type-safe (no missing-module errors in published `.d.ts`).

## Tests

- `bun:test` with `import { describe, expect, test } from "bun:test"`.
- Pure functions first (parsers, auth hashes, cookie extraction); avoid mocks.
- `bun test` runs `test/*.test.ts` automatically.

## CLI

- Scripts like `bin/refresh-cookies.ts` run via `"refresh-cookies": "bun run bin/refresh-cookies.ts"` — NOT shipped in `files` unless it's a real published CLI.

## GitHub-prep checklist

When making the repo GitHub-ready after the scaffold works:

1. `README.md` — setup, auth, API table, notable internals. This is the biggest gap; a publishable package with no docs looks unmaintained.
2. `LICENSE` — MIT matching the `license` field (package.json says MIT; add the file).
3. `.github/workflows/ci.yml` — `oven-sh/setup-bun@v2`, then `bun install --frozen-lockfile`, `typecheck`, `test`, `build` on push/PR.
4. `.gitignore` — `node_modules/`, `dist/`, `*.tsbuildinfo`, `.env`, `*.har`, `.gv-browser-profile/`, editor files.
5. `package.json` — add `repository` (placeholder URL; replace `USERNAME` before push) + `keywords`.
6. **Verify publish contents**: `bun pm pack --dry-run` — confirms only README/LICENSE/package.json/dist ship, and that `.env`/HARs/secrets stay out. (bun has no `npm pack --dry-run` equivalent; this is it.)
7. **Verify no secrets tracked**: `git add -A -n` (dry-run) + `git status` — confirm `.env`, `*.har` captures, browser profiles aren't listed. `git check-ignore .env` returns the path when ignored.
8. Stage BEFORE committing (`git add -A`) — a bare `git commit` with unstaged changes fails with "no changes added to commit".

## Gotchas

- `bun add <pkg>` puts new deps in `dependencies` — move optional ones to `peerDependencies` + `peerDependenciesMeta` manually if intended.
- Fingerprint-gated commits (GPG `commit.gpgsign=true`): run via `hub` PTY so the touch prompt surfaces; `git commit` in a plain bash tool hangs silently then times out.
- The autosync extension auto-commits managed skills to dotfiles — if gitleaks blocks (e.g. API keys in skill body), scrub the values (placeholders like `AIzaSy<voiceApiKey>`) rather than `GIT_ALLOW_SECRETS=1`.
