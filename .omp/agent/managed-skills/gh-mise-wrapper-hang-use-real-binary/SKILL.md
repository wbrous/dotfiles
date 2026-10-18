---
name: gh-mise-wrapper-hang-use-real-binary
description: Use when gh (even gh --version) or git push over HTTPS hangs/times out on this machine because ~/.local/bin/gh is a mise wrapper; call the installed gh binary directly.
---

## Symptom
`gh --version`, `gh auth status`, `gh run list` hang (timeout exit 124), and `git push` to github.com HTTPS hangs/"interrupted", because `gh` is also the git credential helper (`credential.https://github.com.helper = !gh auth git-credential`).

## Cause
`~/.local/bin/gh` is a bash wrapper: `mise use -g --quiet gh || exit 1; exec mise x gh -- gh "$@"`. The `mise use -g` step stalls (likely network/latest-version lookup). mise itself is fine (`mise which gh` works).

## Workaround (no config changes)
```bash
GH=$(mise which gh)   # e.g. ~/.local/share/mise/installs/gh/latest/gh_<ver>_linux_amd64/bin/gh
$GH run list -R owner/repo --limit 3
git -c credential.https://github.com.helper= \
    -c "credential.https://github.com.helper=!$GH auth git-credential" push origin master
```
Use `GIT_TERMINAL_PROMPT=0` and `timeout` so a hang fails fast. If `mise which gh` itself hangs, use `ls ~/.local/share/mise/installs/gh/`.

## Notes
- Push hook (global pre-push) only resigns unsigned commits; an already-signed commit (`git log -1 --format=%G?` = G) passes, so a push timeout is the credential helper, not signing.
- Token scopes of the gh login: gist, project, read:org, repo, workflow (no packages scopes).
- Long-term fix (ask the user first): make the wrapper skip `mise use -g` or resolve the binary via `mise which`.
