---
name: shadcn-tailwind-v4-accent-primary-collision
description: "Use when a shadcn/ui + Tailwind v4 app has icons or selected-state UI (e.g. bg-accent text-primary badges, icon circles, radio-like selected buttons with border-primary bg-accent) that render invisibly or with near-zero contrast — check whether --accent and --primary resolve to the same color value in :root. Also covers registering custom brand/palette CSS variables as real Tailwind v4 utilities via the @theme inline block (plain :root custom properties, even ones named --color-*, are NOT auto-picked up as design tokens unless mirrored inside @theme inline)."
---

## Symptom
A shadcn/ui component pattern like:
```tsx
<span className="rounded-full bg-accent text-primary">
  <Icon />
</span>
```
or a selected/active state like `border-primary bg-accent` renders with the icon/foreground apparently missing, or barely visible. It's not actually missing — `stroke="currentColor"` / `text-primary` is painting the exact same color as the `bg-accent` background.

## Root cause
Scaffolded or hand-written `:root` blocks in `index.css` sometimes duplicate the primary brand color into `--accent` verbatim (a copy-paste artifact, often only in light mode — dark mode frequently has a genuinely distinct `--accent`). Since `--accent` is meant to be a *soft background tint* distinct from `--primary` (a saturated foreground/brand color), this collision silently breaks every place accent-as-background + primary-as-foreground is combined.

## Fix
1. Grep for the token values: confirm `--accent` and `--primary` in `:root` (light mode) are literally the same `oklch(...)`/hex value.
2. Change `--accent` to a distinct, paler tint of the same hue (e.g. bump lightness to ~0.9+, drop chroma) so it reads as a tint, not a duplicate. Don't touch `--primary`.
3. Rebuild and screenshot the affected components (icon circles, selected pills) to confirm visible contrast — this is a visual-only bug, `tsc`/lint won't catch it.

## Related gotcha: custom palette tokens not becoming Tailwind utilities
Tailwind v4 only turns CSS custom properties into usable utility classes (`bg-brand-peach`, `text-brand-orange`, etc.) if they're declared *inside* an `@theme` (or `@theme inline`) block. Declaring `--color-brand-peach: #eca77a;` directly under `:root` does NOT register it as a design token — the class `bg-brand-peach` will silently fail to apply (no error, just no style, since Tailwind never generates the utility).

Fix: move such declarations into the existing `@theme inline { ... }` block:
```css
@theme inline {
  --color-brand-green-dark: #285c2c;
  --color-brand-orange: #de522e;
  --color-brand-peach: #eca77a;
  /* ...existing --color-* mappings that reference :root vars via var() */
}
```
If other theme entries in the same block use `var(--x)` to reference a plain `:root` variable of a *different* name, keep that pattern for tokens that need light/dark mode switching. For static brand colors with no dark-mode variant, it's fine to inline the literal value directly in `@theme inline`.
