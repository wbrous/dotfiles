---
name: logto-fork-submodule-build-from-source
description: "Use when working on optic-fyi monorepo's apps/identity Logto stack: changing the Logto fork (optic-fyi/logto submodule) UI/branding, bumping the submodule, deploying the Logto image, or diagnosing manifest unknown / unauthorized pulls / crash-loop with \"Found undeployed database alterations\"."
---

## Setup (current: prebuilt GHCR image, no build on server)

`apps/identity/logto` is a git submodule of `optic-fyi/logto` (fork of logto-io/logto, tracks its own `master`).

- The fork has `.github/workflows/optic-image.yml`: on every push to `master` it builds the root Dockerfile (amd64, ~6 min cold) and pushes `ghcr.io/optic-fyi/logto:sha-<full commit>` and `:latest` using only `GITHUB_TOKEN`.
- `apps/identity/compose.yml` `app` service uses `image: ghcr.io/optic-fyi/logto:${LOGTO_IMAGE_TAG:?...}` (no `build:`).
- `apps/identity/scripts/pin-logto-image.sh` writes `LOGTO_IMAGE_TAG=sha-<submodule gitlink commit>` into `apps/identity/.env` (reads `git ls-tree HEAD logto`; submodule need not be checked out).
- `test-required-env.sh` covers LOGTO_IMAGE_TAG.

## Changing the fork / bumping

1. Edit under `apps/identity/logto/`, commit + push in the fork (wait for the "Optic image" run to succeed: `gh run list -R optic-fyi/logto --workflow "Optic image"`).
2. `git add apps/identity/logto` in the monorepo, commit, push.
3. On the server: `git pull && bash apps/identity/scripts/pin-logto-image.sh && docker compose up -d --build`.

## Gotchas

- New GHCR packages are created PRIVATE. Pull gives `unauthorized`/`denied` until the package is set Public (org -> Packages -> logto -> settings) or the server does `docker login ghcr.io` with a `read:packages` token. The dev's gh token lacks package scopes, so it can't check/flip this via API.
- `manifest unknown` = the image for that pinned commit isn't published yet (workflow running/failed).
- Pointer bumped before fork commit is pushed => image never exists. Push fork first.
- DB alteration mismatch: if a new image has newer migrations than the volume, app crash-loops with "Found undeployed database alterations". The compose entrypoint now runs `db seed --swe && db alteration deploy next && npm start`, so bumps self-migrate; back up first. Local throwaway fix: `docker compose down -v`.
- Local previews: build under a separate tag (`docker build -t optic-logto-verify:ui .` in the fork) and run as a separate compose project; don't change the real stack's tag.
