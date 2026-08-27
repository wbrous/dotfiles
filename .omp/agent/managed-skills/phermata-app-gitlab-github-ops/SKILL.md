---
name: phermata-app-gitlab-github-ops
description: "Use when working with the phermata/app repo's GitLab (git.phermata.org, self-hosted gitlab-ee in Docker on root@107.172.77.113) and its GitHub push mirror (Phermata/phermata), including: stuck MR merge_status \"preparing\", force-pushing/syncing branches to the GitHub mirror when auto-mirror lags, pushing to protected branches like main, or Cloudflare Workers build/runtime failures for this repo (e.g. \".open-next/worker.js not found\", \"Node.js middleware is not currently supported\", \"Worker exceeded the size limit of 3 MiB\", \"Worker exceeded resource limits\", CSP blocking Clerk custom domain scripts, Convex sync websocket 404s)."
---

## Repo topology
- GitLab (source of truth): `git.phermata.org/phermata/app`, self-hosted gitlab-ee in Docker on `root@107.172.77.113` (container name `gitlab-ee`). SSH to git.phermata.org itself times out; go through `root@107.172.77.113` (user has the password interactively — ask them to run docker commands in their own shell if you lack key access).
- GitHub push mirror: `github.com/Phermata/phermata.git`. GitLab's built-in push-mirror auto-sync is unreliable (Sidekiq backlog) — don't trust it blindly, verify and force-push manually when needed.
- Branches: `main` (protected, protected against direct push), `dev`, `dev-bang`, `agent/patches`.
- Cloudflare Workers deploy: OpenNext + Next.js 16, deployed via `wrangler deploy` from `main`. `wrangler.jsonc` at repo root.
- Workflow pattern for every fix: commit to `dev` → merge `dev` into `main` (protected-branch dance below) → force-sync all 4 branches to the GitHub mirror. Repeat this full pipeline for each change, don't batch.

## Stuck MR merge_status "preparing" (405 on merge attempt)
GitLab's async "prepare MR" Sidekiq job died. Client-side (`glab mr merge`) always 405s, no client workaround exists.
Fix: `ssh root@107.172.77.113` (interactive password), then:
```
docker exec -it gitlab-ee gitlab-ctl restart sidekiq
```
Wait ~15s, recheck via `glab api projects/<owner>%2F<repo>/merge_requests/<iid> --hostname git.phermata.org`. Restarting Sidekiq usually also fires the queued mirror-sync job as a side effect — check `remote_mirrors` API afterward before assuming a manual mirror push is still needed.

## Verifying/fixing GitHub mirror drift
Never trust a bare-clone cache across multiple operations in one session — `git fetch origin` in an existing bare clone can silently fail to update local branch refs even though it reports success. Always do a **fresh** `git clone --bare` immediately before comparing/pushing, and verify with `git ls-remote` on both sides before force-pushing anything (force-pushing a stale local state will regress the target branch).

Push all branches at once (the standard sync step after every merge to main):
```
git clone --bare https://git.phermata.org/phermata/app.git /tmp/app-mirror
cd /tmp/app-mirror
git push https://github.com/Phermata/phermata.git \
  main:main dev:dev dev-bang:dev-bang agent/patches:agent/patches \
  --force --porcelain
```

## Pushing to protected `main` on GitLab
`main` has push_access_level=0 (no one). Temporarily unprotect, push, restore identical protection:
```
glab api -X DELETE projects/phermata%2Fapp/protected_branches/main --hostname git.phermata.org
git push origin main
glab api -X POST projects/phermata%2Fapp/protected_branches --hostname git.phermata.org \
  -f name=main -f push_access_level=0 -f merge_access_level=40 \
  -f unprotect_access_level=40 -f allow_force_push=false
```

## Cloudflare Workers build/deploy failures for this repo
- **`.open-next/worker.js not found`**: Cloudflare dashboard Build command is set to plain `next build` instead of `opennextjs-cloudflare build`. Fix in dashboard: Workers & Pages → project → Settings → Build → Build command → `bun run build:cf` (or whatever package.json script wraps `opennextjs-cloudflare build`).
- **"Node.js middleware is not currently supported"**: Next.js 16 renamed `middleware.ts` → `proxy.ts`, which forces Node.js runtime; OpenNext's Cloudflare adapter can't bundle that yet (needs Edge Runtime, cloudflare/workers-sdk#13937). Fix: rename the file back to `middleware.ts` (same content) — gets Edge Runtime again, which OpenNext needs. Revert once workers-sdk adds support. Update all doc/comment references to the old `proxy.ts` filename too (grep `proxy\.ts` across `.md` and code comments).
- **"Worker exceeded the size limit of 3 MiB"** (Workers Free plan gzip cap): fix stack, in order of effect:
  1. Add `"minify": true` to `wrangler.jsonc` — real, documented, immediate (esbuild minify). ~300 KiB win in this repo.
  2. Bump `@opennextjs/cloudflare` to latest — upstream has been actively shipping size-reduction fixes (opennextjs-cloudflare#659/#700/#702 territory). Check `npm view @opennextjs/cloudflare version` vs installed.
  3. If the app uses the `radix-ui` unified meta-package (not scoped `@radix-ui/react-*` packages) or `lucide-react`, add to `next.config.ts`:
     ```ts
     experimental: { optimizePackageImports: ["radix-ui", "lucide-react"] }
     ```
     This alone cut ~700 KiB gzipped in this repo — the meta-package barrel import was pulling every primitive into every SSR chunk (visible as `grep -rn 'from "radix-ui"' components/` hits, and as repeated esbuild "Duplicate key options in object literal" warnings from floating-ui internals getting inlined multiple times). Verify via `npx wrangler deploy --dry-run --outdir /tmp/x 2>&1 | grep "Total Upload"` (gzip figure is what counts against the 3072 KiB cap) — do NOT need real CF credentials for `--dry-run`.
  4. Cloudflare's own troubleshooting docs state the 3 MiB free-tier cap has no other sanctioned fix besides Workers Paid ($5/mo, 10 MiB cap) — don't chase further unsupported hacks (aliasing/stubbing `@vercel/og`/resvg.wasm internals) once 1–3 land you comfortably under budget (aim for real headroom, not just squeaking under).
- **"Worker exceeded resource limits"** (runtime, not deploy): this is the Free plan's **10 ms CPU-per-request hard cap**, not a quota — it does NOT reset, it fires on every over-budget request forever. Only fixes: cut actual CPU work per request below 10ms (rarely realistic for SSR+auth+DB), or upgrade to Workers Paid (30s default, configurable to 5min via `limits.cpu_ms` in wrangler.jsonc). Don't confuse this with the separate 100k-requests/day quota (that one does reset at 00:00 UTC) — different error class (429 vs "exceeded resource limits").
- **CSP blocking Clerk scripts** (`script-src-elem` blocked at `clerk.<yourdomain>.org/npm/@clerk/...`): app uses a custom Clerk proxy domain in production, not just `*.clerk.accounts.dev`/`*.clerk.com`. Add the custom domain to `script-src`, `img-src`, `connect-src`, `frame-src` in the CSP directives (see `next.config.ts` CSP_DIRECTIVES). Also: Clerk's production bundle (`clerk.browser.js`) genuinely uses `eval()` internally — if CSP blocks `unsafe-eval` in production (some setups only allow it in dev for Turbopack/HMR), Clerk breaks with cascading `ReferenceError`s downstream (e.g. `e is not defined` in unrelated-looking pages — that's fallout from Clerk's partial init, not an app bug). `unsafe-eval` needs to be unconditional, not dev-only, for Clerk to function.
- **CSP blocking `static.cloudflareinsights.com`**: Cloudflare auto-injects its Web Analytics beacon at the edge for any zone with Web Analytics enabled — not app code, but the CSP still has to allow it (or the setting turned off in the Cloudflare dashboard). Add to `script-src` and `connect-src`.
- **Convex sync websocket 404** (`wss://...convex.cloud//api/.../sync`, double slash): `NEXT_PUBLIC_CONVEX_URL` env var deployed to the Worker has a trailing slash, and `ConvexReactClient` concatenates its sync path onto the URL verbatim. Fix defensively in code regardless of upstream env config: `new ConvexReactClient(process.env.NEXT_PUBLIC_CONVEX_URL.replace(/\/+$/, ""))`. This breaks every Convex-backed page silently (data just never loads, stuck on skeleton) with no obvious error pointing at the cause except the raw websocket 404 in devtools.
