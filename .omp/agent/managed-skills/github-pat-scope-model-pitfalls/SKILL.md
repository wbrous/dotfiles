---
name: github-pat-scope-model-pitfalls
description: "Use when designing or reviewing systems that mint/use GitHub PATs with per-resource scope claims (e.g. \"pull_request: write only\"), or when a repo's .env file may be git-tracked with secrets filled into the working tree."
---

## Classic vs fine-grained GitHub PAT scopes

Classic PATs (`ghp_...`) have coarse, bundled scopes: `repo` grants read+write
to contents, issues, PRs, all together. There is NO classic scope that grants
PR-write without also granting contents-write. If a design claims a
credential is "scoped to pull_request: write only" but provisions it as a
classic PAT, that claim is false — the token is fully capable of pushing
code; only the calling code's behavior (not the token) enforces the
restriction.

Per-resource scope splits (e.g. "Pull requests: Read and write" +
"Contents: Read-only") only exist on **fine-grained PATs**, created manually
via GitHub Settings → Developer settings → Fine-grained tokens (or an org's
PAT-approval admin API, not universally available). When a system design
calls for a narrowly-scoped write credential separate from a broad
code-push credential, document explicitly that it MUST be a fine-grained
PAT and that classic-PAT substitution silently defeats the security
property (code-enforced instead of token-enforced isolation).

## .env tracked in git + secrets filled into working tree

Before running `git status`/`git commit` in freshly scaffolded projects,
check whether `.env` (not just `.env.example`) is tracked. A committed
`.env` with placeholder values (`changeme`) is a landmine: once a user (or
agent) fills in real secrets in the working tree, a routine `git commit -a`
or `git add .` will commit real credentials into history.

Fix: `git rm --cached .env`, add `.env` to `.gitignore`, commit that
separately from other pending changes. If real secrets were already
visible in a `git diff` during the session (even if never committed to
history), tell the user to rotate them — treat any credential that passed
through agent output/logs as exposed regardless of whether it reached git
history.
