---
name: bun-install-private-github-git-dependency-fails
description: "bun install fails \"git clone for X failed\" / api.github.com tarball 404 on a git+https dependency pointing at a private GitHub repo (e.g. @optic/ui from optic-fyi/design), though plain git clone works."
---

## Symptom
`bun install` -> `error: "git clone" for "@optic/ui" failed` (migrated from package-lock.json), or after removing the lockfile `GET https://api.github.com/repos/<org>/<repo>/tarball/<sha> - 404`.

## Diagnosis (verified in optic repo)
1. `package-lock.json` `resolved` is `git+ssh://git@github.com/...` -> bun uses SSH; no SSH key on GitHub = `Permission denied (publickey)`.
2. Without the lockfile, bun fetches the API tarball over HTTPS **unauthenticated**. Private repo -> 404. Setting GITHUB_TOKEN / GH_TOKEN / GITHUB_API_TOKEN / BUN_CONFIG_GITHUB_TOKEN from `gh auth token` did NOT help (same token gets 302 via curl).
3. Confirm privacy: `gh repo view <org>/<repo> --json visibility,viewerPermission`; `git ls-remote https://...` works via gh credential helper.

## Working workaround (verified)
Clone the dep repo locally (plain `git clone` works through gh), then point the dep at it: `bun pm pkg set 'devDependencies.@optic/ui=file:./design'` + `bun install`. Gitignore the clone. This changes package.json permanently, so ask user first.

## Unverified options (offer, say untested)
- `npm install` (shells out to git, uses gh creds) after `git config --global url."https://github.com/".insteadOf ssh://git@github.com/`.

## Pitfalls
- In optic, `css/vendor/` is TRACKED (output of `bun run sync:ui`). Never `rm -rf` it when cleaning up experiments; use `git checkout -- css/vendor` to restore.
- Back up package.json / package-lock.json before experiments and restore after.
