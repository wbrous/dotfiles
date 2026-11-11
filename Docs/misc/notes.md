# Misc project notes

One-off reusable facts that don't merit their own topic doc.

## Verify benchmark claims before citing

**Symptom:** Web search for tool/harness benchmark comparisons (e.g. "oh-my-pi vs codex benchmark") returns confident numbers from low-authority SEO/AI-generated blogs (Medium, Composio, various `.dev`/`.ai` sites) repeating identical oddly-precise scores with no primary-source link. Red flags: multiple "independent" sites citing identical numbers, post dates in the future, no raw data/committed dataset/reproducible run, generic domains with no other footprint.

**Cause (oh-my-pi vs codex case):** Blogs claimed "OMP beat Claude Code, Codex, and OpenCode" citing `github.com/minghinmatthewlam/openbench`. Reading the actual repo (`RESULTS.md`, committed JSONL run data, Wilson-CI methodology): it tests harnesses named `codex`, `pi`, `opencode`, `cursor`, `devin` — never `oh-my-pi` (grep for `oh-my-pi|OMP\b|omp\.sh` = zero matches). `pi` (pi.dev) and `oh-my-pi` (can1357's fork of pi) are DIFFERENT projects — the blogs conflated them and invented an "OMP" result.

**Fix:** When search hands you a score/ranking, identify the primary source (benchmark repo/dataset), fetch it directly (README + results file), and grep whether the claimed tool names actually appear. Tool-name conflation (similar names, forks, rebrands) is a common failure mode. If the primary source doesn't substantiate the claim, say so explicitly and report only what the data actually shows — don't launder the blog's fabricated claim. It's fine to say the asked-about comparison has no credible source and show the closest verified data instead.

_Migrated from: verify-benchmark-claims-before-citing_

## Return YouTube Dislike extension: flipping a boolean default

**Symptom:** Changing a default (e.g. `hidePremiumTeaser`) in the RYD extension's prebuilt webpack bundles (`ryd.background.js`, `popup.js`, `ryd.content-script.js`).

**Cause:** Each bundle carries its own copy of the config, so a default lives in several places. `_locales/` matches grep for most keywords — exclude it.

**Fix:**
1. `grep` the key in the three JS files (not `_locales`).
2. Update every site: the `defaultExtConfig` literal in each file (background ~42, popup ~42 plus a second `popup_config` ~205, content-script ~1408 plus a second config ~111547); the first-run initializer `initializeHide...()` in background and content-script (writes the default to `storage.sync` when the value is `undefined`); and readers using `=== true` (treat unset as false, so a new true default needs `value === undefined ? true : value === true` — seen in popup `initializeHide...` calling the handler with raw `res.key`, and content-script teaser `syncSuppressionWithSettings`).
3. Bundle edits need the file's current `#tag` header; re-read if rejected.
4. Verify with `node --check` on all three files, then grep for the old literal.

Note: "Premium" analytics are gated server-side (Patreon session, `membershipTier === "premium"`) — no client setting unlocks them; don't fake the tier. ("Premium enabled by default" was clarified as hiding the teaser by default.)

_Migrated from: ryd-extension-change-setting-default_
