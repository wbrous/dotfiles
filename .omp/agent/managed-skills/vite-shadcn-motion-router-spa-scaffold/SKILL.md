---
name: vite-shadcn-motion-router-spa-scaffold
description: "Use when scaffolding a fresh Vite + React + TS + Tailwind v4 + shadcn/ui + Motion (framer-motion successor) + react-router SPA, especially one with a shared-element layoutId morph between two routes, cross-tab state via localStorage+storage events, or a bun:test suite. Covers the recurring build-breaking gotchas: shadcn CLI's literal @ directory bug, missing @types/bun, motion/react import path, staggerChildren deprecation, AnimatePresence mode=\"sync\" requirement for layoutId morphs, and useSyncExternalStore conditional-hook violations."
---

## Context

These recur every time this exact stack combo (Vite + shadcn/ui + Motion + react-router, `bun` as package manager/test runner) is scaffolded from a fresh `bunx shadcn@latest init`-style repo. Each was hit and fixed live while building a five-route animated demo SPA.

## Gotchas, in the order you'll hit them

1. **shadcn CLI writes to a literal `@` directory at repo root** instead of `src/`. Root cause: the CLI resolves the `@/*` alias via `tsconfig-paths`, which reads *only* the root `tsconfig.json` — it does not follow `references` into `tsconfig.app.json`. If the root tsconfig is a solution-style file (`{ "files": [], "references": [...] }`) with no `compilerOptions.paths`, tsconfig-paths' match-all fallback resolves `@/components/ui/button` to `<root>/@/components/ui/button.tsx`.
   - Fix: add `"compilerOptions": { "paths": { "@/*": ["./src/*"] } }` to the **root** `tsconfig.json`, leaving `references` untouched. Do **not** add `baseUrl` — TypeScript 6 raises TS5101 for `baseUrl` without a reason to set it.
   - Keep the `paths` entry in `tsconfig.app.json` too — referenced projects don't inherit root `compilerOptions`, so both copies are required.
   - If a stray `@` directory already exists from a prior failed `shadcn add`, rescue by hand: `mkdir -p src/lib src/components/ui`, move the misplaced files in verbatim (they already import `@/lib/utils` correctly once the alias is fixed), then `rm -rf @`. Re-running `shadcn add` afterward should land everything in `src/` — if it doesn't, the alias fix wasn't applied correctly; don't keep moving files by hand.

2. **Motion (the framer-motion successor, npm package `motion`) React API imports from `motion/react`**, never bare `motion`. Install with `bun add motion` — `framer-motion` is just its implementation dependency, don't install it directly.

3. **`staggerChildren` is deprecated.** Use `transition: { delayChildren: stagger(0.07) }` (with `stagger` imported from `motion/react`) on the parent variant instead. This is an easy one for a subagent to miss when copy-pasting an older Motion pattern — grep for `staggerChildren` across route files before calling a build "done".

4. **`layoutId` shared-element morph requires `AnimatePresence mode="sync"`** (the default), never `mode="wait"`. With `"wait"` the exiting node leaves the shared-layout stack before the entering node registers, so the morph silently never fires. Pair this with absolutely-positioned, independently-scrolling route panes inside a fixed-height `overflow-hidden` container so the brief two-page overlap doesn't cause a layout jump. Also: set `borderRadius` via the `style` prop (not a Tailwind radius class) on the `layoutId` element, since layout animations distort `scale`/`borderRadius`/`boxShadow` on Tailwind-class-driven elements; wrap children in `<motion.div layout>` to correct scale distortion.

5. **`react-router-dom` stopped at v7** — the current major is the unified `react-router` package (v8+). Install `react-router`, not `react-router-dom`. Declarative mode: `<BrowserRouter>` + `<Routes>`/`<Route>`; `useNavigate`, `useParams`, `useLocation`, `Link`, `Outlet` all import from `"react-router"`.

6. **`bun:test` type declarations require `@types/bun` as a dev dependency**, and `tsconfig.app.json`'s `compilerOptions.types` array needs `"bun"` added alongside `"vite/client"` (i.e. `"types": ["vite/client", "bun"]`). Without both, `tsc -b` fails on any file importing `{ test, expect } from 'bun:test'` with `TS2307: Cannot find module 'bun:test'` even though `bun test` itself runs fine (bun's runtime doesn't need the type decls, but `tsc -b` as part of `vite build` does).

7. **`useSyncExternalStore` called behind a conditional guard is a `react-hooks/rules-of-hooks` violation**, even for a seemingly reasonable SSR-safety check like `if (typeof window === 'undefined') return EMPTY_STATE` placed before the hook call inside a custom hook (e.g. `useVouch()`). Fix: pass a `getServerSnapshot` as the third argument to `useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot)` and call the hook unconditionally — let `getServerSnapshot` return the empty/fallback state instead of branching before the hook.

8. **shadcn's generated `sonner.tsx` is Next.js-flavoured** — it imports `useTheme` from `next-themes`, which isn't installed in a plain Vite app and doesn't crash the build but is dead code that should be corrected: delete the `next-themes` import and `const { theme } = useTheme()` line, pass `theme="light"` (or whatever's appropriate) literally to `<Sonner>`. Don't install `next-themes` just to satisfy it.

9. **Vite's chunk-size-warning** (`(!) Some chunks are larger than 500 kB after minification`) is common once Motion + Radix primitives + multiple variable-weight fonts (`@fontsource-variable/*`) are bundled together, even for a small app. If the project's verification bar is "build passes with zero warnings," bump `build.chunkSizeWarningLimit` in `vite.config.ts` rather than chasing code-splitting for a demo/small app — it's an advisory, not a real problem, unless the app is meant to ship at scale.

## Cross-tab state pattern (localStorage + storage event)

For a module-level store synced across browser tabs without a backend:
- `let state` at module scope, a `Set<() => void>` of listeners, `getSnapshot()` returning a stable reference only replaced on real mutation (so `useSyncExternalStore` doesn't loop).
- Register exactly one `window.addEventListener('storage', ...)` handler at module scope (not per-subscriber) that re-reads localStorage and notifies all listeners — this is what makes tab B's write show up live in tab A without a reload.
- Hydration must be defensive: wrap `JSON.parse` in try/catch, validate shape, and on any failure fall back to a known-good empty state *and overwrite the bad key* so it self-heals on next load rather than erroring forever.
- Verify the cross-tab path with two real browser tool tabs (not just unit tests) — open tab A, generate something with a shareable code/link, open tab B on that link, mutate state in tab B, then re-inspect tab A **without reloading it** to confirin the `storage` event round-trip actually works end-to-end.
