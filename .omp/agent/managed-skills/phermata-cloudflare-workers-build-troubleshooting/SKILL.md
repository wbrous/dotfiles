---
name: phermata-cloudflare-workers-build-troubleshooting
description: "Use when a Cloudflare Workers Build (OpenNext + Next.js 16) for the phermata/app repo fails during bun run build:cf / wrangler deploy, especially errors: \"ERROR Node.js middleware is not currently supported\", \".open-next/worker.js was not found\", or \"Your Worker exceeded the size limit of 3 MiB\". Also covers the general pattern of diagnosing/shrinking an OpenNext Cloudflare Worker bundle."
---

## Context

phermata/app: Next.js 16 + OpenNext (`@opennextjs/cloudflare`) deployed as a Cloudflare Worker. Cloudflare's dashboard Build settings run `bun run build:cf` (→ `opennextjs-cloudflare build`) then `npx wrangler deploy`, per `package.json` scripts. `wrangler.jsonc` sets `"main": ".open-next/worker.js"`.

## Error 1: "ERROR Node.js middleware is not currently supported. Consider switching to Edge Middleware."

Root cause: Next.js 16 renamed `middleware.ts` → `proxy.ts`. `proxy.ts` is **Node.js-runtime-only and cannot be configured to use Edge Runtime** (per Next's own v16 upgrade docs). OpenNext's Cloudflare adapter can't bundle Node.js-runtime middleware (Workers doesn't support it) — tracked upstream at `cloudflare/workers-sdk#13937`, unresolved as of Next 16.2.6 / `@opennextjs/cloudflare` 1.16–1.20.

Fix: rename `proxy.ts` back to `middleware.ts` (same code/default-export convention). Classic `middleware.ts` still gets Edge Runtime, which is what OpenNext needs. Update all doc/comment references (AGENTS.md, MD/CLAUDE.md, page-level comments) that mention the filename. Revert to `proxy.ts` only once OpenNext/Wrangler ship support.

## Error 2: ".open-next/worker.js was not found"

Cloudflare dashboard **Build command** is misconfigured — running plain `next build` (or default `npm run build`) instead of the OpenNext-aware script. `wrangler.jsonc`'s `main` points at `.open-next/worker.js`, which is only produced by `opennextjs-cloudflare build`.

Fix: In Cloudflare dashboard → Workers & Pages → the Worker → Settings → Build: set **Build command** to `bun run build:cf` (this repo's script that runs `opennextjs-cloudflare build`). Also verify **Package manager** dropdown is set to `bun` (repo uses `bun.lock`).

## Error 3: "Your Worker exceeded the size limit of 3 MiB" (Workers Free plan)

Official Cloudflare/OpenNext troubleshooting docs (opennext.js.org/cloudflare/troubleshooting) state the ONLY sanctioned fix for the 3 MiB case is upgrading to Workers Paid (10 MiB limit) — but real, safe reductions ARE possible without paying:

1. **`"minify": true` in `wrangler.jsonc`** — official esbuild-backed wrangler config field. One known case (GH issue) went from over-limit to just-under with `--minify` alone. In phermata/app this cut gzip from 3422.54 KiB → 3104.38 KiB (~318 KiB saved) — still not enough alone here.
2. **Bump `@opennextjs/cloudflare` to latest** — upstream actively works on bundle-size reduction (see closed issue opennextjs/opennextjs-cloudflare#659, referencing PRs #700/#702). Bumping 1.16.5 → 1.20.2 was a major contributor to the final fix.
3. **`experimental.optimizePackageImports` in `next.config.ts`** for barrel-import packages actually in use — THE key fix here. phermata/app imports from the `radix-ui` meta-package (single package aggregating all `@radix-ui/react-*` primitives, not scoped `@radix-ui/react-dialog` etc.) across 17+ files. Without `optimizePackageImports`, esbuild/Turbopack can't cleanly tree-shake unused primitives out of SSR chunks, and each component using floating-ui-backed primitives (Popover/Select/Tooltip/DropdownMenu) risked duplicated floating-ui code (visible as repeated esbuild `[WARNING] Duplicate key "options" in object literal` pointing at floating-ui internals). Config:
   ```ts
   experimental: {
     optimizePackageImports: ["radix-ui", "lucide-react"],
   },
   ```
   Combined with the version bump, this took gzip from 3104.38 KiB → **2386.78 KiB** (718 KiB additional savings), comfortably under the 3072 KiB (3 MiB) free-tier cap.

Do NOT attempt to strip/alias `@vercel/og`/`resvg.wasm` internals — OpenNext bundles this unconditionally as core infrastructure (`patch-vercel-og-library.js`) regardless of whether the app uses `next/og`/`ImageResponse`. It's real remaining weight but hacking around it means patching `@opennextjs/cloudflare` internals directly — fragile, unsupported, breaks on version bumps. Prefer the two levers above; only recommend the Paid plan if those genuinely aren't enough.

## Verifying size fixes locally without deploying

```bash
# Fake env vars sufficient to get `next build` past prerender (Clerk/Convex need *some* value):
export NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY="pk_test_ZmFrZS1rZXktZm9yLWxvY2FsLWJ1aWxkLXZlcmlmaWNhdGlvbi5jbGVyay5hY2NvdW50cy5kZXYk"
export CLERK_SECRET_KEY="sk_test_fake_key_for_local_build_verification_only"
export NEXT_PUBLIC_CONVEX_URL="https://fake-verify.convex.cloud"
bun install --frozen-lockfile
bun run build:cf
npx wrangler deploy --dry-run --outdir /tmp/wrangler-out   # prints "Total Upload: X KiB / gzip: Y KiB" without deploying
```
`--dry-run` skips the actual Cloudflare API size-validation call, so it won't print the "5 largest dependencies" diagnostic (that only appears when the real API rejects an oversized deploy) — but the gzip total it reports is accurate and sufficient to confirm you're under/over the limit before pushing.

For deeper bundle analysis: `.open-next/server-functions/default/handler.mjs.meta.json` is an esbuild metafile —
```bash
jq '.outputs[".open-next/server-functions/default/handler.mjs"].inputs | to_entries | sort_by(.value.bytesInOutput) | reverse | .[0:20] | map({path:.key, bytes:.value.bytesInOutput})' handler.mjs.meta.json
```
Note: wasm modules (like `resvg.wasm`) are bundled by wrangler's own build step, not OpenNext's esbuild pass, so they won't appear in this metafile — only visible in the real deploy's "5 largest dependencies" error output.
