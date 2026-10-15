---
name: fingerprint-website-auth-provider
description: Use when asked what auth/identity system a site uses (in-house vs Clerk/Auth0/Better Auth/Keycloak/etc.) from its login or settings URL.
---

# Fingerprint a website's auth provider

Goal: decide in-house vs OSS/vendor auth from outside, with evidence.

## Steps (run independent ones in parallel)
1. `read <url>:raw` — SPA pages are mostly one inline module script; note framework (Solid/React/Vue), meta tags. `read` truncates at ~1.9KB per chunk, so download the full HTML with curl instead.
2. Probe well-known/vendor endpoints with `curl -sSi -m 10`:
   - `/.well-known/openid-configuration`, `/.well-known/jwks.json`, `/.well-known/oauth-authorization-server`
   - Better Auth: `/api/auth/get-session`, `/api/auth/ok`
   - Then print the OIDC discovery JSON (grant types, signing algs, scopes, endpoints) and `/api/config` if present (often lists providers, passkeys, allowed return origins).
3. Download the page to a file and grep the bundle:
   - Vendor names: better-auth, supabase, clerk, auth0, workos, stytch, firebase, keycloak, zitadel, logto, kratos, hanko, lucia, authjs, next-auth, simplewebauthn, hono.
   - API paths: `grep -oE '"/(api|auth|oauth)[A-Za-z0-9_/.-]*' file | sort -u`
   - Error-code strings in the client reveal bespoke flows.
4. Judge: bespoke `/api/login/*`, `/api/me/*` routes + custom error codes + no vendor strings + own OIDC discovery => in-house. Vendor route layouts (`/api/auth/*`, `/realms/`, `/auth/v1/`) => that product.

## Gotchas
- Python `urllib` gets 403 from Cloudflare-fronted sites (default UA); use `curl`.
- Backend libs (JOSE, SimpleWebAuthn, Hono) are invisible from outside; state as caveat, weak signals = guess.
- Report what was observed vs inferred; you can't see backend source.
