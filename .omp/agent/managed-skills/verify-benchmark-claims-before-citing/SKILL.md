---
name: verify-benchmark-claims-before-citing
description: "Use when asked to compare AI coding tools/harnesses (e.g. oh-my-pi vs codex vs pi vs claude code) via benchmarks, or any time web search returns benchmark numbers/leaderboard claims from blog posts — before citing a specific score or ranking, verify it traces to a real primary source (actual repo with committed run data), not a content-farm blog repeating an unverified number."
---

## Problem

Web search for benchmark comparisons (e.g. "oh-my-pi vs codex benchmark") frequently surfaces a cluster of low-authority SEO/AI-generated blog posts (Medium, Composio, various `*.dev`/`*.ai` sites) that all repeat the exact same specific numbers ("Pi 20, OMP 17") with no link back to a primary source. Red flags:

- Multiple independent-looking sites citing identical, oddly-precise numbers.
- Post dates in the future relative to today (e.g. dated 2026 when today is also 2026 but the site has no other verifiable presence).
- No link to raw data, a committed dataset, or a reproducible run.
- Generic-sounding domains with no other footprint (standardcompute.com, critique.sh, adipod.ai style).

## What actually happened (oh-my-pi vs codex case)

Searched for "oh-my-pi vs codex benchmark" — got confident claims that "OMP beat Claude Code, Codex, and OpenCode" citing `github.com/minghinmatthewlam/openbench`. Went and actually read that repo directly (`_read` on the GitHub URL, then `RESULTS.md`). Findings:

- The repo is real (135 stars, actual committed JSONL run data, Wilson-CI methodology, honest caveats section).
- It tests harnesses named `codex`, `pi`, `opencode`, `cursor`, `devin` — **never `oh-my-pi`**.
- `pi` (pi.dev) and `oh-my-pi` (can1357's fork of pi) are DIFFERENT projects. The blogs conflated them, inventing an "OMP" result that doesn't exist in the actual dataset.
- Grepping the full RESULTS.md for `oh-my-pi|OMP\b|omp\.sh` confirmed zero matches.

## Procedure

1. When search results hand you a specific benchmark score/ranking, identify the *primary* source (the actual benchmark repo/dataset), not the blog repeating it.
2. Fetch that primary source directly (`_read` the repo README, then the actual results file).
3. Grep/check whether the specific tool names in the claim actually appear in the primary data. Tool-name conflation (similar names, forks, rebrands) is a common failure mode.
4. If the primary source doesn't substantiate the claim, say so explicitly and give the user only what the primary data actually shows — don't launder the blog's fabricated claim into your own answer.
5. It's fine and expected to tell the user "the comparison you're asking about doesn't have a credible source; here's what the closest verified data actually shows instead."
