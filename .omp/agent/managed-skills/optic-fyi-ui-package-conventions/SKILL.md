---
name: optic-fyi-ui-package-conventions
description: "optic-fyi @optic-fyi/ui (packages/ui) shared shadcn theme: adding components, DataTable tanstack v9, bg-grid cn conflict, app builds."
---

# @optic-fyi/ui conventions (optic-fyi monorepo)

The package ships TS source only, with no build step. Apps consume it like this:
- CSS: `@import "@optic-fyi/ui/styles.css"; @source "./";`
- Components are imported per file: `@optic-fyi/ui/components/<name>` or `components/{layout,marketing,dashboard,window}/<name>`. There are no barrel files.
- Helpers: `@optic-fyi/ui/lib/{utils,tone,format}`.

## Adding or restyling components
- Add shadcn components from inside the package: `cd packages/ui && bunx shadcn@latest add <name>`. Its `components.json` aliases point at `@optic-fyi/ui/*`, so no `@/` imports should appear.
- Apply the house recipe:
  - Pressables: `shadow-ledge`, colored by `[--ledge-color:var(--X-deep)]`, with hover lift and a flush press.
  - Surfaces: `rounded-2xl border-2 border-border-strong bg-card shadow-block`.
  - Never use blur, decorative gradients, or `shadow-xs..2xl`.
  - Add a JSDoc comment on every export.
- Look up tone classes in `lib/tone.ts` (`toneClasses`). Never build class names by string interpolation.
- The palette is in `src/styles/theme.css`, as hex only. `src/styles/theme.test.ts` parses it and checks WCAG ≥ 4.5 contrast.
- Verify with `cd packages/ui && bun run typecheck && bun test`.

## Gotchas
- `cn` uses tailwind-merge, which treats the custom `bg-grid`/`bg-dots` utilities as background colours. In `cn(bg-mint/20, bg-grid)` one class is silently dropped. For tinted grid canvases, use arbitrary-property backgrounds (`[background-color:color-mix(...)]`, `[background-image:...]`).
- `@tanstack/react-table` installs as v9, which has no `useReactTable` or `getCoreRowModel`.
  - `dashboard/data-table.tsx` is built on `tableFeatures()` + `createTableHook()`, with `filterFns`/`sortFns` registered by name. Without that registration, filtering and sorting silently do nothing.
  - Build columns with `createDataTableColumnHelper<Row>()` and type the array as `DataTableColumn<Row>[]`.
- `ScheduleGrid` drag-paint: do not call `setPointerCapture`, because it stops `pointerenter` from reaching sibling cells.
- The root scripts `bun run parent-dashboard:build` / `kid-dashboard:build` use `bun --cwd`, which only prints the script list with the current bun. Build from each app's own directory instead: `cd apps/<app> && bun run build`.
- The shadcn `sonner` component was changed to take a `theme` prop instead of using `next-themes`, so do not re-add `next-themes`.
- Browser smoke tests of kid-dashboard `/lock` and `/home` need a device token. `/` (Connect) and a throwaway `/__gallery` route work without one; delete the gallery route afterwards.
