---
name: git-remote-ssh-host-key-fallback-https-gh-auth
description: "Use when a git push/pull over an SSH remote (git@github.com:...) fails with \"Host key verification failed\" / \"Could not read from remote repository\" on a machine/sandbox where the SSH host key for that git host isn't trusted yet (e.g. fresh git init + git remote add using an ssh:// or git@ URL). Also covers the general recipe for force-pushing a freshly git-init'd local directory over an existing remote repo's default branch when explicitly instructed to."
---

## Symptom

```
git push --force origin main
Host key verification failed.
fatal: Could not read from remote repository.
```

This happens when a remote is added with an SSH URL (`git@github.com:owner/repo.git`) but the environment has no trusted `known_hosts` entry for that host (common in fresh sandboxes/containers/agent environments that never did an interactive SSH handshake before).

## Fix

Switch the remote to HTTPS and let `gh` (already authenticated) supply credentials via its git credential helper:

```bash
git remote set-url origin https://github.com/OWNER/REPO.git
gh auth setup-git   # wires gh as the credential helper for github.com (and github hosts)
git push --force origin main
```

`gh auth setup-git` is idempotent and safe to run even if already configured — it just ensures `credential.https://github.com.helper` points at `gh auth git-credential`.

## Related: bootstrapping a fresh local checkout onto an existing remote's default branch

When a project directory has real files but no `.git` yet, and the user explicitly wants it to become the new history of an existing GitHub repo's default branch (force-push, discarding old remote history):

```bash
git init -b main
git add -A
git -c user.email="..." -c user.name="..." commit -m "..." --no-verify
git remote add origin https://github.com/OWNER/REPO.git   # use https:// directly to sidestep the SSH host-key issue
gh auth setup-git
git push --force origin main
```

Notes:
- Prefer adding the remote as `https://` from the start in agent/sandbox environments rather than `git@`, to avoid the SSH host-key failure entirely.
- Any existing nested `.gitignore` files (e.g. `apps/foo/.gitignore` excluding `apps/foo/.env`) are respected automatically by `git add -A` run from the repo root — no need to duplicate ignore rules at the root.
- This is a genuinely destructive action (overwrites the remote branch's history) — only do it when the user has explicitly and unambiguously asked for a force-push over an existing branch.
