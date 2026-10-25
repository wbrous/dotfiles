---
name: ryd-extension-change-setting-default
description: "Changing a default for a setting (e.g. hidePremiumTeaser) in the Return YouTube Dislike browser extension bundle (ryd.background.js, popup.js, ryd.content-script.js)."
---

## Context
The RYD extension ships prebuilt webpack bundles: `ryd.background.js`, `popup.js`, `ryd.content-script.js`. Each bundles its own copy of the config, so a default lives in several places. `_locales/` matches grep for most keywords; exclude it.

## Procedure for flipping a boolean default (example: `hidePremiumTeaser`)
1. `grep` the key in the three JS files (not `_locales`).
2. Update every site:
   - `defaultExtConfig` literal in each file (background ~42, popup ~42 and a second `popup_config` ~205, content-script ~1408 and a second config ~111547).
   - First-run initializer `initializeHide...()` in background and content-script: it writes the default to `storage.sync` when the value is `undefined`.
   - Readers that use `=== true`: these treat an unset value as false, so a new default of true needs `value === undefined ? true : value === true`. Seen in popup `initializeHide...` (calls handler with raw `res.key`) and content-script teaser `syncSuppressionWithSettings`.
3. Edits to a bundle need the file's current `#tag` header; re-read if rejected.
4. Verify with `node --check` on all three files, then grep for the old literal.

## Notes
- "Premium" analytics are gated server-side (Patreon session, `membershipTier === "premium"`). No client setting unlocks them; do not try to fake the tier. "Premium enabled by default" was clarified by the user as hiding the teaser by default.
