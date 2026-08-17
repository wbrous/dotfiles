---
name: shadcn-theme-accent-primary-collision-tailwind-v4
description: "Use when a shadcn/ui + Tailwind v4 app has icons or selected-state UI (e.g. bg-accent text-primary icon circles, border-primary bg-accent selected buttons/radio-like pills) that render invisibly or with near-zero contrast — check whether --accent and --primary resolve to the same color value in :root. Also covers registering custom brand/palette CSS variables (e.g. --color-brand-*) as real Tailwind v4 utilities via the @theme inline block, since plain :root custom properties are not auto-picked up as design tokens even when named --color-*."
---

## Symptom
Icon inside a circular badge (`bg-accent text-primary`) is invisible, or a
selected/active pill (`border-primary bg-accent`) shows no visible fill —
looks like the icon/asset failed to load, but the SVG is present and correct
in the DOM (check with `tab.evaluate` — width/height/children all populated).

## Root cause
In many shadcn `init` scaffolds, `--accent` and `--primary` get generated
with the **identical** OKLCH value in the light-mode `:root` block. Any
component using `bg-accent` as a background with `text-primary` as the
foreground (a very common shadcn pattern for icon badges and selected
states) ends up drawing the foreground in the exact same color as its own
background — invisible, not merely low-contrast.

Diagnostic: read `index.css`, find `--accent:` and `--primary:` in the same
`:root` block (or `.dark`), and diff the values. If identical, that's the bug.
Confirm live by reading the rendered `<svg>`'s computed stroke/fill color vs
its parent's background-color via `tab.evaluate`.

## Fix
Give `--accent` a genuinely distinct value — a pale tint of the brand hue
works well as an icon-badge/selected-state background (e.g. reuse or
approximate `--secondary`'s lightness/chroma but keep the brand hue angle).
Don't touch `--primary`; it's usually correct and used correctly elsewhere.
Check `.dark` too — it's often already fine since dark-mode accent tends to
diverge from primary by design, only light mode collides.

## Related: brand tokens declared but inert
A separate common miss in the same file: designers hand-off a palette as
`--color-brand-*: #hex` declared at the top of `:root` (following the
`--color-` naming convention), but Tailwind v4 **only** turns variables into
usable utility classes (`bg-brand-peach`, `text-brand-orange`, etc.) when
they're declared inside an `@theme` / `@theme inline` block. Plain `:root`
custom properties — even ones correctly prefixed `--color-*` — are invisible
to Tailwind's utility generator. Symptom: brand colors are defined but never
referenced anywhere in the codebase (grep for the token name turns up only
the declaration). Fix: move the declarations into `@theme inline { ... }`
(or add mirrored entries there). This instantly unlocks `bg-brand-x`,
`text-brand-x`, `border-brand-x/20` etc., including opacity-modifier syntax.

When editing an existing `@theme inline` block with an `edit` PUT-range op,
double check nothing legitimate at the boundary of the replaced range (e.g.
an adjacent unrelated `--color-sidebar-ring: var(--sidebar-ring);` entry)
gets silently dropped — re-read the file after the edit to confirm the full
original entry list survived.
