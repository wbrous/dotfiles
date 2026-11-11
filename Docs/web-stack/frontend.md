# Frontend Scaffolds (Vite, shadcn, Next, Hono SPA)

Covers scaffolding Vite + shadcn + Motion + react-router SPAs, shadcn/Tailwind v4 setup, migrating Vite SPAs to Next.js App Router, host-based multi-tenancy, and wiring browser SPAs to Hono/Logto backends.

## Fresh Vite + shadcn + Motion + react-router SPA scaffold

Stack: Vite + React + TS + Tailwind v4 + shadcn/ui + Motion (`motion` package) + `react-router`, `bun` as package manager/test runner. Gotchas in the order you'll hit them:

1. **shadcn CLI writes to a literal `@` directory at repo root** instead of `src/`. Root cause: the CLI resolves `@/*` via `tsconfig-paths`, which reads *only* the root `tsconfig.json` — it doesn't follow `references` into `tsconfig.app.json`. If the root tsconfig is solution-style (`{ "files": [], "references": [...] }`) with no `compilerOptions.paths`, the match-all fallback resolves `@/components/ui/button` to `<root>/@/components/ui/button.tsx`.
   - Fix: add `"compilerOptions": { "paths": { "@/*": ["./src/*"] } }` to the **root** `tsconfig.json`, leaving `references` untouched. Do NOT add `baseUrl` — TypeScript 6 raises TS5101 for `baseUrl` without reason to set it. Keep the `paths` entry in `tsconfig.app.json` too — referenced projects don't inherit root `compilerOptions`.
   - If a stray `@` dir already exists: `mkdir -p src/lib src/components/ui`, move the misplaced files verbatim (they already import `@/lib/utils` correctly), `rm -rf @`. Re-running `shadcn add` should land in `src/`; if not, the alias fix wasn't applied.
2. **Motion's React API imports from `motion/react`**, never bare `motion`. `bun add motion` — `framer-motion` is its implementation dependency, don't install directly.
3. **`staggerChildren` is deprecated.** Use `transition: { delayChildren: stagger(0.07) }` (`stagger` from `motion/react`) on the parent variant. Grep for `staggerChildren` before calling a build done.
4. **`layoutId` shared-element morph requires `AnimatePresence mode="sync"`** (the default), never `mode="wait"`. With `"wait"` the exiting node leaves the shared-layout stack before the entering node registers, so the morph never fires. Pair with absolutely-positioned, independently-scrolling route panes inside a fixed-height `overflow-hidden` container to avoid layout jump during the brief two-page overlap. Set `borderRadius` via the `style` prop (not a Tailwind radius class) on the `layoutId` element; wrap children in `<motion.div layout>` to correct scale distortion.
5. **`react-router-dom` stopped at v7** — current major is the unified `react-router` package (v8+). Install `react-router`, not `react-router-dom`. `<BrowserRouter>` + `<Routes>`/`<Route>`; `useNavigate`, `useParams`, `useLocation`, `Link`, `Outlet`, `useSyncExternalStore` all from `"react-router"`.
6. **`bun:test` types need `@types/bun` as a devDependency**, and `tsconfig.app.json`'s `compilerOptions.types` needs `"bun"` alongside `"vite/client"` (`"types": ["vite/client", "bun"]`). Without both, `tsc -b` fails on any file importing `bun:test` with `TS2307` even though `bun test` itself runs fine.
7. **`useSyncExternalStore` called behind a conditional guard is a `react-hooks/rules-of-hooks` violation**, even for SSR-safety like `if (typeof window === 'undefined') return EMPTY_STATE` before the hook. Fix: pass `getServerSnapshot` as the third argument and call the hook unconditionally — let `getServerSnapshot` return the fallback state.
8. **shadcn's generated `sonner.tsx` is Next.js-flavoured** — it imports `useTheme` from `next-themes`, which isn't installed in a plain Vite app. Delete the import and `const { theme } = useTheme()` line, pass `theme="light"` (or appropriate) literally to `<Sonner>`. Don't install `next-themes` just for it.
9. **Vite chunk-size warning** (`Some chunks are larger than 500 kB`) is common once Motion + Radix + multiple variable-weight `@fontsource-variable/*` fonts bundle together, even for a small app. If the bar is "build passes with zero warnings," bump `build.chunkSizeWarningLimit` in `vite.config.ts` rather than code-splitting a demo — advisory, not a real problem at this scale.

**Cross-tab state pattern (localStorage + storage event):** module-level `let state`, a `Set<() => void>` of listeners, `getSnapshot()` returning a stable reference only replaced on real mutation (so `useSyncExternalStore` doesn't loop). Register exactly one `window.addEventListener('storage', ...)` at module scope (not per-subscriber) that re-reads localStorage and notifies all listeners. Hydration: try/catch `JSON.parse`, validate shape, on failure fall back to known-good empty state *and overwrite the bad key* so it self-heals. Verify cross-tab with two real browser tabs (open tab A, generate something with a shareable link, open tab B on that link, mutate in B, re-inspect A without reloading).

_Migrated from: vite-shadcn-motion-router-spa-scaffold_

## shadcn init prerequisites on a fresh Vite scaffold

**Symptom.** `shadcn init` against a fresh `vite --template react-ts` scaffold fails preflight: `No Tailwind CSS configuration found ...` / `Could not find valid path aliases or package imports for init.`

**Fix:**

1. `bun add tailwindcss @tailwindcss/vite` (no separate `tailwind.config.js` needed for v4).
2. `vite.config.ts` — plugin + `@` alias in one shot:

   ```ts
   import path from 'node:path'
   import { defineConfig } from 'vite'
   import react from '@vitejs/plugin-react'
   import tailwindcss from '@tailwindcss/vite'

   export default defineConfig({
     plugins: [react(), tailwindcss()],
     resolve: {
       alias: {
         '@': path.resolve(import.meta.dirname, './src'),
       },
     },
   })
   ```

   Use `import.meta.dirname`, NOT `__dirname` — `__dirname` triggers a Vite warning under `configLoader: 'native'` (planned future default).
3. `src/index.css` — prepend `@import "tailwindcss";`.
4. `tsconfig.app.json` — add `"paths": { "@/*": ["./src/*"] }` under `compilerOptions`. Do NOT add `"baseUrl": "."` — with `moduleResolution: "bundler"` it's unnecessary and modern TS (5.9+/6.x) throws **TS5101** (`Option 'baseUrl' is deprecated`) as a `tsc -b` build error.
5. Re-run `shadcn init` — preflight passes both checks.

**Verify:** `bun run build` (`tsc -b && vite build`) completes with zero errors/warnings.

_Migrated from: shadcn-vite-init-prereqs_

## shadcn `--accent` / `--primary` collision + inert brand tokens (Tailwind v4)

**Symptom.** A shadcn/ui pattern like `<span className="rounded-full bg-accent text-primary"><Icon/></span>` or a selected state `border-primary bg-accent` renders invisibly — the icon/foreground is painted the exact same color as the background. The SVG is present and correct in the DOM (verify computed stroke/fill vs parent background); `stroke="currentColor"` / `text-primary` just matches `bg-accent`.

**Cause.** Scaffolded/hand-written `:root` blocks sometimes duplicate the primary brand color into `--accent` verbatim (often light-mode only; dark mode frequently diverges by design). `--accent` is meant to be a *soft background tint* distinct from `--primary` (a saturated brand color). Since many shadcn init scaffolds generate identical OKLCH values for both in light-mode `:root`, every `bg-accent` + `text-primary` combination (icon badges, selected pills) draws foreground in its own background color.

**Fix:** grep `--accent` vs `--primary` in the same `:root` (and `.dark`) block; if identical, change `--accent` to a distinct paler tint of the same hue (bump lightness to ~0.9+, drop chroma) — e.g. reuse/approximate `--secondary`'s lightness/chroma but keep the brand hue angle. Don't touch `--primary`. Rebuild and screenshot the affected components — `tsc`/lint can't catch a visual-only bug.

**Related: brand tokens declared but inert.** Designers hand off `--color-brand-*: #hex` declared at the top of `:root` — but Tailwind v4 only turns variables into usable utilities (`bg-brand-peach`, `text-brand-orange`, `border-brand-x/20` incl. opacity modifiers) when declared inside an `@theme` / `@theme inline` block. Plain `:root` custom properties — even correctly prefixed `--color-*` — are invisible to Tailwind's utility generator: the class silently fails to apply (no error, just no style). Fix: move them into `@theme inline { ... }` (mirroring the existing `--color-*` entries; follow the `var(--x)` pattern for tokens needing light/dark switching, literal values for static brand colors). Also inert for the same reason: `@theme { --color-*: initial }` must come AFTER the Tailwind theme and BEFORE kit tokens — placed after the kit tokens it erases kit colours and utilities silently vanish (needed because Tailwind's `--color-neutral-50/100` collide with Logto-style `--color-*` names).

Editing tip: when editing an existing `@theme inline` block with a range op, double-check nothing at the range boundary (e.g. an adjacent `--color-sidebar-ring` entry) gets silently dropped — re-read after the edit.

_Migrated from: shadcn-tailwind-v4-accent-primary-collision, shadcn-theme-accent-primary-collision-tailwind-v4_
