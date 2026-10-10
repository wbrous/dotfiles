---
name: logto-fork-optic-ui-kit-theming
description: "Maintain the Optic UI kit theming of the optic-fyi Logto fork (experience + account): vendored packages/optic-ui sync script and pre-commit hook, Tailwind v4 without preflight, token-based restyling, and the CSS/pnpm gotchas hit while doing it."
---

## Layout
- Kit source: monorepo `packages/ui`. Fork copy: `apps/identity/logto/packages/optic-ui` (GENERATED, never edit; a symlink would dangle because the Docker context is only `apps/identity/logto`).
- `bun scripts/sync-optic-ui.ts [--check]` copies the files in `VENDORED_FILES`; it refuses if a listed TS file or relative CSS `@import` references an unlisted kit file. New kit file used by the fork => add it to the list.
- `.githooks/pre-commit` (enable once per clone: `bash scripts/install-git-hooks.sh`) re-syncs when `packages/ui/src` or the script is staged, chains the GLOBAL hook first (repo-local core.hooksPath replaces global), and blocks the commit if the submodule changed (commit in fork, then `git add apps/identity/logto`).

## Fork wiring
- Logto components stay; restyle via tokens: `experience/src/shared/scss/_colors.scss` (Logto `--color-*` names, Optic hex values), `_fonts.scss` (Nunito), plus Button/NotchedBorder/Checkbox/VerificationCode/AppLayout/account card scss. Kit vars (`--primary`, `--mint`, `--ring`...) are available in scss.
- `experience/src/shared/scss/optic-ui.css` imports Tailwind `theme.css` + `utilities.css` ONLY (no preflight), then `optic-ui-reset-colors.css`, then kit `vendor.css`, `shadcn.css`, `theme.css`, `tokens.css`. Account has `account/src/scss/optic-ui.css` importing the experience one + its own `@source`.
- Dark: set `class="dark"` on `<html>` (AppMeta + blocking script in both index.html) next to `data-theme`. Tenant brand-colour runtime override (use-color-theme + index.html script) was deliberately removed.

## Gotchas
- `@theme { --color-*: initial }` must come AFTER Tailwind theme and BEFORE the kit tokens; after them it erases the kit colours (utilities silently vanish). Needed because Tailwind's `--color-neutral-50/100` collide with Logto's names.
- Never `@import "shadcn/tailwind.css"` in the fork (pulls ~196 pkgs): kit ships a verbatim `shadcn.css` copy. Bare package imports (`tw-animate-css`) only resolve via pnpm hoisting from the fork apps; import `@optic-fyi/ui/styles/vendor.css` so they resolve from the kit's own node_modules.
- Kit `--input` border is ~1.4:1 on card; Logto originals were better. Dark input border token lifted to `#6a6275`; unchecked checkbox uses `--color-type-secondary`.
- Focus halo = spread `box-shadow` on the same fieldset (a second notched fieldset never lined up). Label and notch share `--label-inset`; zero fieldset `padding-inline`.
- `[tabindex='-1']:focus-visible {outline:none}` stops react-modal dialogs showing a ring.
- Undefined legacy token `--shadow-2` in account modals -> use `--color-shadow-2`.
- Jest is CJS: vite/@tailwindcss/vite are ESM-only, so the CSS test runs `compile-optic-ui.mjs` in a child process.
- `pnpm remove` does not accept `--ignore-scripts`. Frozen-lockfile `pnpm i` must pass (Docker uses it).
- eslint may show extra `no-unsafe-argument` errors in a long-lived working tree that vanish on a clean install; compare against a `git worktree` clean install before blaming your change (pre-existing: `import/order` in `Layout/AppLayout/index.tsx`).
- Fast loop for visual work: after the first docker build, `vite build` experience+account on the host and `docker cp dist/.` into the running verify container (~6s). Final check still needs a full `docker build`. See skill `logto-fork-visual-verify-isolated-stack` for the isolated stack.
