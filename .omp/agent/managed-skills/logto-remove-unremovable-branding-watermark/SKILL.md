---
name: logto-remove-unremovable-branding-watermark
description: "Use when self-hosting a Logto fork/submodule (e.g. optic-fyi/logto, or any logto-io/logto derivative built from source rather than the prebuilt image) and asked to remove \"Powered by Logto\" branding/watermarks from user-facing apps (sign-in experience, account center). Also covers the general pattern of finding and neutralizing a deliberately unremovable/self-healing UI watermark (MutationObserver + setInterval re-enforcing display/visibility/position styles) rather than trying to fight it with CSS overrides."
---

## Where the Logto watermark lives

Logto's OSS build renders a "Powered by Logto" badge in every user-facing app, gated behind `hideLogtoBranding` — a setting that is **Cloud-only** (the admin console UI's own translation strings admit this: `hide_logto_branding_oss_note: 'This feature is natively available in <a>Logto Cloud</a>.'`). Self-hosted OSS instances can never legitimately turn it off via settings, so removing it means editing the fork's source.

Grep the whole monorepo for it first — don't assume one location:

```
(?i)(powered\s*[-_]?\s*by\s*logto|poweredby|powered_by|watermark)
```

As of Logto 1.43.x there is exactly **one shared component**, rendered from **three call sites**:

- Component: `packages/experience/src/shared/components/LogtoSignature/index.tsx` (+ its `index.module.scss`)
- Rendered from:
  - `packages/experience/src/Layout/AppLayout/index.tsx` — every sign-in/sign-up screen
  - `packages/account/src/App.tsx` (`Layout` component) — account center full layout
  - `packages/account/src/components/PageFooter/index.tsx` — account center compact footer

All three gate the render with `!hideLogtoBranding`, which is always `false` in OSS since nothing can set it true — so it always renders.

Also present but **out of scope for a typical self-hosted deployment**: `packages/device-demo-app/src/Footer.tsx` has its own inline "Powered by" badge. This is a standalone example app, not part of what `packages/core` serves at runtime (the Dockerfile's `app` image only serves core+console+experience+account) — skip it unless the demo app is actually being deployed.

## Why you can't just CSS-hide it

`LogtoSignature`'s `useEffect` is deliberately adversarial to removal attempts:

```ts
const enforceIntegrity = () => {
  container?.style.setProperty('display', 'block', 'important');
  container?.style.setProperty('visibility', 'visible', 'important');
  anchor.style.removeProperty('display');
  // ...
};
enforceIntegrity();
const observer = new MutationObserver(enforceIntegrity);
observer.observe(anchor, { attributes: true, attributeFilter: ['class', 'style', 'hidden'] });
observer.observe(container, { attributes: true, attributeFilter: ['class', 'style', 'hidden'] });
window.setInterval(enforceIntegrity, 2000);
```

It also injects a `<style data-logto-signature-guard="true">` into `document.head` with `!important` rules keyed off `[data-logto-signature="secured"]` attributes. Trying to hide it via CSS/DOM manipulation after the fact is a losing fight — it actively re-asserts every 2s and on every attribute mutation.

**Fix: don't render the component at all.** Remove the `<LogtoSignature ... />` JSX at each of the three call sites (and the now-unused `hideLogtoBranding`/`theme` variables that only existed to feed it), then delete the component directory entirely. This is a normal React edit — no observer to fight because it never mounts.

## Cleanup checklist per call site

1. Remove the `LogtoSignature` import.
2. Remove the conditional `<LogtoSignature .../>` render block.
3. Remove `hideLogtoBranding` derivation if it's now unused elsewhere in that file.
4. Remove `theme` from context destructuring if it was *only* used to feed `LogtoSignature` (check with a grep of `theme` within that file before deleting — some files use `theme` elsewhere too).
5. After fixing all call sites, grep the whole repo for `LogtoSignature` again to confirm zero references, then delete `packages/experience/src/shared/components/LogtoSignature/`.

## Verification

1. `docker compose build app` — a clean TypeScript compile is itself a good signal (unused imports/types would fail the build if you missed a cleanup step).
2. Bring the stack up, run the existing OIDC discovery smoke test.
3. Visually confirm: open the admin console's **Sign-in experience** page (`/console/sign-in-experience/experience`) — it embeds a *live* iframe preview of the real experience app, so a screenshot of it reflects the actual deployed UI without needing to drive a full OIDC auth flow yourself.

## Submodule workflow

Commit and push inside the submodule to your fork's own default branch first (check `git branch -r` — Logto forks off `logto-io/logto` typically default to `master`, not `main`), *then* from the parent repo `git add path/to/submodule && git commit` to bump the pointer, then push the parent repo.
