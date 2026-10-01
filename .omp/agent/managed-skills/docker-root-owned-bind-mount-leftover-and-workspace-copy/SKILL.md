---
name: docker-root-owned-bind-mount-leftover-and-workspace-copy
description: "Root-owned dir at repo root blocks git switch/revert (cannot rmdir ... Permission denied) after moving a compose bind-mounted file; or docker build fails 'Workspace dependency not found' after adding a Bun workspace package."
---

## Root-owned leftover from a compose bind mount

Symptom: `git revert`/`switch`/`cherry-pick` fails with `fatal: cannot rmdir 'X/File': Permission denied`; `ls -la` shows a root-owned *directory* where a file used to be.

Cause: compose bind-mounted `./X/File`; the path was missing at container start, so Docker created it as a root-owned directory. The old container still holds that mount, so deleting the dir alone is undone the next time the container is touched.

Fix (no sudo needed if user is in the `docker` group; check `sudo -n true` and `id -nG`):
1. Confirm the dir holds no files and nothing is tracked: `find X -mindepth 1 ! -type d`, `git ls-files X`.
2. Find containers still mounting it: `docker inspect $(docker ps -aq) --format '{{.Name}} {{range .Mounts}}{{.Source}} {{end}}' | grep X`.
3. `docker rm <container>` (named volumes survive, so certs/data are kept).
4. `docker run --rm -v "$PWD:/repo" <any local image> rm -rf /repo/X` (mount only the parent, name only the one path).
5. `docker compose up -d --build <svc>` from the new layout; confirm the dir does not reappear.

While the dir blocks git in the main checkout, do history surgery in a `git worktree add /tmp/x` instead.

## Adding a Bun workspace package: update every Dockerfile

Dockerfiles that run `bun install --frozen-lockfile` against the root `bun.lock` must `COPY <workspace>/package.json` for EVERY workspace in the lockfile, or the build fails with `Workspace dependency "<name>" not found`. This stays hidden while the running containers predate the change. After adding a package, run `docker compose build` for every service that has a deps stage. Packages that ship TypeScript source (no build step) also need their `src/` copied before a consumer's Vite build.
