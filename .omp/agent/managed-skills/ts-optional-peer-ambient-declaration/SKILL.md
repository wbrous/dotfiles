---
name: ts-optional-peer-ambient-declaration
description: "Use when a TypeScript/bun library with an optional peerDependency fails tsc (TS2307 \"Cannot find module\") in CI or for consumers who don't install the peer — even though the code only uses dynamic import(). Fix: ambient declare module in a src/*.d.ts declaring only the used surface."
---

# Optional peer deps: tsc TS2307 fix via ambient declaration

## Symptom

A publishable TS library declares an optional peerDependency (e.g.
`@mherod/get-cookie`, `playwright`) that is loaded only via dynamic
`import()` at runtime. Locally `tsc --noEmit` passes (the peer is installed
in `node_modules`), but CI fails:

```
src/browser.ts(197,55): error TS2307: Cannot find module '@mherod/get-cookie' or its corresponding type declarations.
```

Cause: `tsc` resolves module specifiers at **compile time even for dynamic
`import()`** and for `import type`. In CI, `bun install --frozen-lockfile`
never installs optional peers → unresolved specifier → TS2307. (The same
error hits downstream consumers whose `.d.ts` references the peer.)

## Fix

Add an ambient module declaration so tsc knows the module exists regardless
of installation. Inside `src/` (must be in the tsconfig `include`):

`src/<peer>-env.d.ts`:

```ts
/**
 * Ambient declaration for `<peer>`, an *optional* peer dependency.
 * Satisfies tsc's compile-time specifier resolution when the peer is not
 * installed (e.g. CI); the runtime import() still throws if truly missing,
 * which the caller catches.
 */
declare module "<peer>" {
  // Declare ONLY the surface this library actually uses.
  export interface ExportedCookie { name: string; value: unknown; domain?: string }
  export class ChromiumCookieQueryStrategy {
    constructor(browser?: string);
    queryCookies(name: string, domain: string): Promise<ExportedCookie[]>;
  }
}
```

Then in the consumer module, import types from the declared module:

```ts
import type { ExportedCookie } from "<peer>"; // resolves via ambient decl
// dynamic import stays dynamic; cast only if needed
const mod = await import("<peer>");
```

## Rules that keep it clean

- **Use `import type` at top level** (ts-import-type rule) — no inline
  `import("pkg").Type` annotations.
- **Only reference the peer types in non-exported internals.** If an
  exported signature references the peer type, the emitted `dist/*.d.ts`
  contains the unresolved import and consumers without the peer break.
  Verify: `grep -n "<peer>" dist/<file>.d.ts` should match only comments.
- **Externalize in the bundler** so the runtime import stays dynamic:
  `bun build ./src/index.ts --external <peer> ...`.
- **Declare in package.json**: `peerDependenciesMeta.<peer>.optional = true`.

## Verification (the CI condition)

`tsc` passes locally with the peer installed, which proves nothing. Simulate
the fresh-checkout condition:

```bash
mv "node_modules/@scope/<peer>" /tmp/peer_stash   # or rm -rf
bun run typecheck
mv /tmp/peer_stash "node_modules/@scope/<peer>"    # restore immediately
```

Typecheck must pass in BOTH states. Also re-run `bun pm pack --dry-run` and
inspect the packed `.d.ts` files for stray peer references.

## Context

This exact failure hit `google-voice-client` (google-voice-ws repo) when its
CI ran `bun run typecheck` against `@mherod/get-cookie` (optional peer).
The ambient-declaration fix passed typecheck with the peer physically
removed from `node_modules`, and `dist/browser.d.ts` shipped no peer type
reference.
