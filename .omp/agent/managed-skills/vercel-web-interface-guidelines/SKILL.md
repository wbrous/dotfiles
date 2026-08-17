---
name: vercel-web-interface-guidelines
description: "Use when building or reviewing web UI (React/Next.js or plain HTML/CSS/JS) for compliance with Vercel's Web Interface Guidelines — accessibility, focus states, forms, animation, typography, content handling, images, performance, navigation/state, touch/interaction, safe areas/layout, dark mode, i18n, hydration safety, hover states, and copy/content rules. Triggers: \"web interface guidelines\", \"vercel design guidelines\", UI code review requests, or any new UI component/page implementation where these conventions apply."
---

## Source
https://vercel.com/design/guidelines (canonical, longer list) and https://github.com/vercel-labs/web-interface-guidelines (command.md checklist below).

Use as a checklist when building new UI or reviewing existing UI code. Read files, check against rules, output concise `file:line - issue` findings. Sacrifice grammar for brevity.

## Rules

### Accessibility
- Icon-only buttons need `aria-label`
- Form controls need `<label>` or `aria-label`
- Interactive elements need keyboard handlers (`onKeyDown`/`onKeyUp`)
- `<button>` for actions, `<a>`/`<Link>` for navigation (never `<div onClick>`)
- Images need `alt` (or `alt=""` if decorative)
- Decorative icons need `aria-hidden="true"`
- Async updates (toasts, validation) need `aria-live="polite"`
- Use semantic HTML before ARIA
- Headings hierarchical `<h1>`–`<h6>`; include skip link for main content
- `scroll-margin-top` on heading anchors

### Focus States
- Interactive elements need visible focus: `focus-visible:ring-*` or equivalent
- Never `outline-none`/`outline: none` without focus replacement
- Use `:focus-visible` over `:focus` (avoid focus ring on click)
- Group focus with `:focus-within` for compound controls

### Forms
- Inputs need `autocomplete` and meaningful `name`
- Correct `type` (`email`, `tel`, `url`, `number`) and `inputmode`
- Never block paste
- Labels clickable (`htmlFor` or wrapping control)
- Disable spellcheck on emails/codes/usernames
- Checkbox/radio: label+control share one hit target
- Submit button stays enabled until request starts; spinner during request
- Errors inline next to fields; focus first error on submit
- Placeholders end with `…` and show example pattern
- `autocomplete="off"` on non-auth fields to avoid password manager triggers
- Warn before navigation with unsaved changes

### Animation
- Honor `prefers-reduced-motion`
- Prefer CSS > Web Animations API > JS libraries; avoid main-thread JS animation
- Animate `transform`/`opacity` only (compositor-friendly); avoid `width`/`height`/`top`/`left`
- Never `transition: all` — list properties explicitly
- Correct `transform-origin`
- SVG: transforms on `<g>` wrapper, `transform-box: fill-box; transform-origin: center`
- Animations interruptible by user input
- Animate only when it clarifies cause/effect or adds deliberate delight; avoid autoplay

### Typography
- `…` not `...`
- Curly quotes `" "` not straight `" "`
- Non-breaking spaces: `10&nbsp;MB`, `⌘&nbsp;K`, brand names
- Loading states end with `…`
- `font-variant-numeric: tabular-nums` for number columns/comparisons
- `text-wrap: balance`/`text-pretty` on headings (avoid widows)

### Content Handling
- Long content: `truncate`, `line-clamp-*`, or `break-words`
- Flex children need `min-w-0` for text truncation
- Handle empty states explicitly
- Anticipate short/average/very long user-generated content

### Images
- `<img>` needs explicit `width`/`height` (prevent CLS)
- Below-fold: `loading="lazy"`; above-fold critical: `priority`/`fetchpriority="high"`

### Performance
- Virtualize large lists (>50 items)
- No layout reads in render (`getBoundingClientRect`, `offsetHeight`, `scrollTop`)
- Batch DOM reads/writes
- Prefer uncontrolled inputs; controlled inputs cheap per keystroke
- `<link rel="preconnect">` for CDN/asset domains
- Preload critical fonts with `font-display: swap`

### Navigation & State
- URL reflects state (filters, tabs, pagination, expanded panels) — use nuqs or similar
- Links use `<a>`/`<Link>`, never substitute `<button>`/`<div>` for navigation
- Deep-link all stateful UI backed by `useState`
- Destructive actions need confirmation modal or undo window
- Back/Forward restores scroll position
- Accurate `<title>` reflecting current context; no dead ends (every screen offers next step/recovery)

### Touch & Interaction
- `touch-action: manipulation` (prevent double-tap zoom delay)
- `-webkit-tap-highlight-color` set intentionally
- `overscroll-behavior: contain` in modals/drawers/sheets
- During drag: disable text selection, `inert` on dragged elements
- `autoFocus` sparingly — desktop only, single primary input; rarely on mobile (keyboard causes layout shift)
- Match visual & hit targets: expand hit target to ≥24px (desktop) / ≥44px (mobile) if visual target smaller
- No dead zones — if part looks interactive, it must be
- Tooltip: delay first in a group, no delay for subsequent peers
- Never disable browser zoom (`user-scalable=no`/`maximum-scale=1`)
- Mobile `<input>` font-size ≥16px to prevent iOS auto-zoom

### Safe Areas & Layout
- Full-bleed layouts: `env(safe-area-inset-*)` for notches
- Avoid unwanted scrollbars — fix overflow, don't hide symptom
- Flex/grid/intrinsic layout over JS measurement
- Optical alignment: adjust ±1px when perception beats geometry
- Every element aligns deliberately (grid, baseline, edge, optical center)
- Balance contrast in icon+text lockups (weight/size/spacing/color)
- Verify responsive coverage: mobile, laptop, ultra-wide (zoom to 50%)

### Dark Mode & Theming
- `color-scheme: dark` on `<html>` for dark themes
- `<meta name="theme-color">` matches page background
- Native `<select>`: explicit `background-color`/`color` (Windows dark mode)

### Locale & i18n
- Dates/times: `Intl.DateTimeFormat`, not hardcoded
- Numbers/currency: `Intl.NumberFormat`, not hardcoded
- Detect language via `Accept-Language`/`navigator.languages`, never IP/GPS
- Wrap brand names, code tokens, identifiers with `translate="no"`
- Internationalize keyboard shortcuts for non-QWERTY layouts; show platform-specific symbols

### Hydration Safety
- Inputs with `value` need `onChange` (or use `defaultValue` for uncontrolled)
- Guard date/time rendering against server/client hydration mismatch
- `suppressHydrationWarning` only where truly needed
- Inputs must not lose focus/value after hydration

### Hover & Interactive States
- Buttons/links need `hover:` state
- Hover/active/focus states increase contrast over rest state

### Content & Copy
- Active voice: "Install the CLI" not "The CLI will be installed"
- Title Case for headings/buttons (Chicago style)
- Numerals for counts: "8 deployments" not "eight"
- Specific button labels: "Save API Key" not "Continue"
- Error messages include fix/next step, not just problem
- Second person; avoid first person
- `&` over "and" where space-constrained
- Menu items opening a follow-up end with `…` (e.g. "Rename…")
- Name things by what people control/recognize, not system internals
- Action name stays consistent through the flow (button "Publish" → toast "Published")
- Empty states are invitations to act; errors don't apologize and are specific

### Anti-patterns (flag these in review)
- `user-scalable=no`/`maximum-scale=1`
- `onPaste` + `preventDefault`
- `transition: all`
- `outline-none` without focus-visible replacement
- Inline `onClick` navigation without `<a>`
- `<div>`/`<span>` with click handlers instead of `<button>`
- Images without dimensions
- Large arrays `.map()` without virtualization
- Form inputs without labels
- Icon buttons without `aria-label`
- Hardcoded date/number formats
- `autoFocus` without clear justification

## Output Format (for review requests)
Group by file, `file:line` format, terse findings, no explanation unless fix non-obvious:
```
## src/Button.tsx
src/Button.tsx:42 - icon button missing aria-label
src/Button.tsx:67 - transition: all → list properties

## src/Card.tsx
✓ pass
```
