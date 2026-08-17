---
name: shadcn-vite-init-prereqs
description: "Use when running shadcn init (or bunx --bun shadcn@latest init) against a fresh Vite+React+TS scaffold and it fails with \"No Tailwind CSS configuration found\" and/or \"Could not find valid path aliases\" — covers wiring Tailwind v4 + the @ path alias into vite.config.ts/tsconfig, plus the TS5101 baseUrl deprecation error and the __dirname vite-native-config-loader warning this setup commonly triggers."
---

## Problem
Fresh `vite --template react-ts` scaffold has no Tailwind CSS and no `@` import alias. `shadcn init` requires both and fails preflight with:
```
No Tailwind CSS configuration found ...
Could not find valid path aliases or package imports for init.
```

## Fix
1. Install Tailwind v4 + its Vite plugin (no separate `tailwind.config.js` needed):
   ```
   bun add tailwindcss @tailwindcss/vite
   ```
2. `vite.config.ts` — add the plugin and the `@` alias in one shot:
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
3. `src/index.css` (or main CSS entry) — prepend:
   ```css
   @import "tailwindcss";
   ```
4. `tsconfig.app.json` — add `paths` under `compilerOptions` (mirrors the Vite alias):
   ```json
   "paths": {
     "@/*": ["./src/*"]
   }
   ```
   Do NOT add `"baseUrl": "."` alongside it — with `moduleResolution: "bundler"` it's unnecessary and modern TS (5.9+/6.x) throws **TS5101** ("Option 'baseUrl' is deprecated") as a build error via `tsc -b`, not just a warning-in-editor. `paths` alone resolves fine without it.
5. Re-run `shadcn init` (same command/preset) — preflight now passes both checks.

## Verify
`bun run build` (`tsc -b && vite build`) must complete with zero errors/warnings — confirms both the alias and Tailwind wiring are structurally sound, not just accepted by shadcn's preflight.
