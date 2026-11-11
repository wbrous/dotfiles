# Vercel Web Interface Guidelines checklist

Scope: Vercel's web UI rules, used as a build/review checklist for React/Next.js or plain HTML/CSS/JS. Canonical sources: https://vercel.com/design/guidelines and https://github.com/vercel-labs/web-interface-guidelines. Review output: group by file, `file:line - issue`, terse findings, no explanation unless the fix is non-obvious; sacrifice grammar for brevity.

## Accessibility

**Symptom:** UI fails assistive-technology or keyboard use.

**Fix (checklist):** icon-only buttons need `aria-label`; form controls need `<label>` or `aria-label`; interactive elements need keyboard handlers (`onKeyDown`/`onKeyUp`); `<button>` for actions, `<a>`/`<Link>` for navigation (never `<div onClick>`); images need `alt` (`alt=""` if decorative); decorative icons `aria-hidden="true"`; async updates (toasts, validation) need `aria-live="polite"`; semantic HTML before ARIA; hierarchical `<h1>`–`<h6>` with a skip link for main content; `scroll-margin-top` on heading anchors.

## Focus states

Interactive elements need visible focus (`focus-visible:ring-*` or equivalent); never `outline-none` without a focus replacement; `:focus-visible` over `:focus`; group focus with `:focus-within` for compound controls.

## Forms

Inputs need `autocomplete` and meaningful `name`; correct `type` (`email`, `tel`, `url`, `number`) and `inputmode`; never block paste; labels clickable (`htmlFor` or wrapping); disable spellcheck on emails/codes/usernames; checkbox/radio label+control share one hit target; submit stays enabled until the request starts with a spinner during it; errors inline next to fields with focus moved to the first error on submit; placeholders end with `…` showing an example pattern; `autocomplete="off"` on non-auth fields to avoid password-manager triggers; warn before navigation with unsaved changes.

## Animation

Honor `prefers-reduced-motion`; prefer CSS > Web Animations API > JS libraries, avoid main-thread JS animation; animate `transform`/`opacity` only, never `width`/`height`/`top`/`left`; never `transition: all` — list properties; correct `transform-origin`; SVG transforms on a `<g>` wrapper with `transform-box: fill-box; transform-origin: center`; animations interruptible by user input; animate only to clarify cause/effect or add deliberate delight, no autoplay.

## Typography and copy

`…` not `...`; curly quotes, not straight; non-breaking spaces (`10&nbsp;MB`, `⌘&nbsp;K`, brand names); loading states end with `…`; `font-variant-numeric: tabular-nums` for number columns; `text-wrap: balance`/`text-pretty` on headings. Active voice ("Install the CLI"); Title Case headings/buttons (Chicago); numerals for counts ("8 deployments"); specific button labels ("Save API Key", not "Continue"); errors include fix/next step; second person, avoid first; `&` where space-constrained; menu items opening a follow-up end with `…` ("Rename…"); name things by what people control, not system internals; action name consistent through the flow (button "Publish" → toast "Published"); empty states invite action; errors don't apologize and are specific.

## Content, images, performance

Long content: `truncate`, `line-clamp-*`, or `break-words`; flex children need `min-w-0` for truncation; handle empty states explicitly; anticipate short/average/very long user-generated content. `<img>` needs explicit `width`/`height` (prevent CLS); below-fold `loading="lazy"`, above-fold critical `priority`/`fetchpriority="high"`. Virtualize large lists (>50 items); no layout reads in render (`getBoundingClientRect`, `offsetHeight`, `scrollTop`); batch DOM reads/writes; prefer uncontrolled inputs (controlled inputs cheap per keystroke); `<link rel="preconnect">` for CDN/asset domains; preload critical fonts with `font-display: swap`.

## Navigation, touch, layout, theming, i18n, hydration, hover

- **Navigation & state:** URL reflects state (filters, tabs, pagination, expanded panels — nuqs or similar); links use `<a>`/`<Link>`; deep-link all `useState`-backed stateful UI; destructive actions need confirmation or undo; Back/Forward restores scroll; accurate `<title>`; no dead ends.
- **Touch & interaction:** `touch-action: manipulation`; `-webkit-tap-highlight-color` intentional; `overscroll-behavior: contain` in modals/drawers/sheets; during drag disable text selection, `inert` on dragged elements; `autoFocus` sparingly (desktop only, single primary input — rarely mobile, keyboard shifts layout); hit targets ≥24px desktop / ≥44px mobile even if the visual is smaller; no dead zones; tooltips delay the first in a group only; never disable browser zoom; mobile `<input>` font-size ≥16px (prevents iOS auto-zoom).
- **Safe areas & layout:** full-bleed layouts use `env(safe-area-inset-*)`; fix overflow, don't hide it; flex/grid/intrinsic over JS measurement; optical alignment ±1px when perception beats geometry; every element aligns deliberately; balance icon+text lockups; verify mobile, laptop, ultra-wide (zoom to 50%).
- **Dark mode:** `color-scheme: dark` on `<html>`; `<meta name="theme-color">` matches background; native `<select>` gets explicit `background-color`/`color` (Windows dark mode).
- **Locale & i18n:** `Intl.DateTimeFormat` / `Intl.NumberFormat`, never hardcoded; language from `Accept-Language`/`navigator.languages`, never IP/GPS; `translate="no"` on brand names/code/identifiers; internationalize shortcuts for non-QWERTY, show platform symbols.
- **Hydration safety:** inputs with `value` need `onChange` (or `defaultValue`); guard date/time rendering against server/client mismatch; `suppressHydrationWarning` only where truly needed; inputs must not lose focus/value after hydration.
- **Hover:** buttons/links need `hover:` state; hover/active/focus increase contrast over rest.

## Anti-patterns (flag in review)

`user-scalable=no`/`maximum-scale=1`; `onPaste` + `preventDefault`; `transition: all`; `outline-none` without focus-visible replacement; inline `onClick` navigation without `<a>`; `<div>`/`<span>` click handlers instead of `<button>`; images without dimensions; large `.map()` without virtualization; unlabeled form inputs; icon buttons without `aria-label`; hardcoded date/number formats; unjustified `autoFocus`.

_Migrated from: vercel-web-interface-guidelines_
