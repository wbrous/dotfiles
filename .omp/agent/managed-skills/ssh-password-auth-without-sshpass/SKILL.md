---
name: ssh-password-auth-without-sshpass
description: "Use when needing to SSH/run remote commands with password-only auth (no SSH key configured, no sudo to install sshpass) — e.g. the omp ssh:// tool fails with \"Permission denied (publickey,password)\" and there's no package manager access. Also covers syncing a subfolder of a forked monorepo from its upstream (e.g. updating python/robomp in a private fork from can1357/oh-my-pi) while preserving local customizations to a shared file like docker-compose.yml."
---

## Password-only SSH without sshpass

When the built-in `ssh://` device fails with `Permission denied (publickey,password)` (no key auth configured) and you only have a password, and `sshpass` isn't installed and you have no sudo to install it:

Use OpenSSH's `SSH_ASKPASS_REQUIRE=force` (OpenSSH 8.4+) to feed the password non-interactively via `bash`, bypassing the need for a real TTY or sshpass:

```bash
mkdir -p /tmp/askpass
cat > /tmp/askpass/pw.sh <<'EOF'
#!/bin/sh
echo "THE_PASSWORD"
EOF
chmod +x /tmp/askpass/pw.sh

export SSH_ASKPASS=/tmp/askpass/pw.sh
export SSH_ASKPASS_REQUIRE=force
ssh -o PreferredAuthentications=password -o PubkeyAuthentication=no \
    -o StrictHostKeyChecking=accept-new \
    root@HOST "command here" </dev/null 2>&1
```

Notes:
- Do NOT wrap in `setsid` — that detaches stdout and you get no output.
- `</dev/null` prevents ssh from trying to read a passphrase from a pipe.
- `-o PreferredAuthentications=password -o PubkeyAuthentication=no` forces password auth even if a (wrong/missing) key would otherwise be tried first and fail differently.
- Clean up `/tmp/askpass` when done (contains the plaintext password).
- Every remote command must repeat the `export`s (each `bash` tool call is a fresh shell) — bundle multiple remote steps into one `ssh ... "cmd1 && cmd2"` invocation, or repeat the two export lines per bash call.

## Syncing a forked monorepo subfolder from upstream, preserving local overrides

When a private fork (e.g. `origin = zep-dev-ai/oh-my-pi`) has a subfolder (e.g. `python/robomp`) that tracks an upstream repo (e.g. `can1357/oh-my-pi`) and needs updating without dragging in unrelated upstream changes to the rest of the monorepo:

1. `git add`/`git commit` any uncommitted local changes first (so nothing is lost/needs stashing).
2. `git remote add upstream <url>` (fails harmlessly if it already exists) + `git fetch upstream main`.
3. Sanity-check divergence: `git log --oneline HEAD..upstream/main -- <subfolder>` and the reverse, to spot genuinely local-only commits vs. re-authored copies of upstream commits (fork-sync scripts often re-author commits under a bot identity — check commit stats/sizes match).
4. `git diff --stat HEAD upstream/main -- <subfolder>` to see full scope before touching anything.
5. `git checkout upstream/main -- <subfolder>` — this overwrites ONLY that path's tracked files with upstream's version in the index+worktree, leaving the rest of the repo untouched. Much safer than a full `git merge upstream/main` when the fork has unrelated infra differences elsewhere.
6. Manually reapply any real local customizations to files upstream also touched (e.g. docker-compose.yml env-var passthrough, internal IPs) — diff the old local version against the new upstream version to find exact reinsertion points.
7. `git add <subfolder> && git commit`.
8. Smoke-verify: `python3 -m py_compile src/**/*.py` for syntax, `docker compose config -q` for compose file validity — cheap checks that don't require installing the full toolchain (uv/pip) or rebuilding containers.
9. Do NOT rebuild/restart live containers as part of "update the code" unless explicitly asked — a monorepo sync can introduce new required env vars/migrations; flag that as a separate follow-up decision.
