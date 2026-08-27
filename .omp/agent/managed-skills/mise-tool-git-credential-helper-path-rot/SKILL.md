---
name: mise-tool-git-credential-helper-path-rot
description: "Use when a git push/pull over HTTPS suddenly falls back to an interactive username/password prompt (e.g. via a dotfiles push wrapper or plain git), and the error mentions a versioned mise install path for gh like \".../mise/installs/gh/2.97.0/.../gh: No such file or directory\" — a git credential.host.helper entry hardcodes an absolute mise-managed binary path that mise pruned after auto-updating the tool."
---

## Symptom

```
/home/USER/.local/share/mise/installs/gh/2.97.0/gh_2.97.0_linux_amd64/bin/gh auth git-credential get: line 1: .../gh: No such file or directory
Username for 'https://github.com':
```

Any command that shells out through git's credential helper (plain `git push`, a `dotfiles push` wrapper, etc.) degrades to an interactive prompt.

## Root cause

`~/.config/git/config` (or `--global` config) has `credential.https://github.com.helper` set to an **absolute versioned mise install path**, e.g.:

```
credential.https://github.com.helper=!/home/USER/.local/share/mise/installs/gh/2.97.0/gh_2.97.0_linux_amd64/bin/gh auth git-credential
```

mise auto-updated `gh` (e.g. 2.97.0 → 2.98.0 via `latest` in `~/.config/mise/config.toml`) and pruned the old version's install dir. The hardcoded path now points at nothing.

Confirm with:
```sh
mise ls gh                          # shows currently installed/active version
which gh                            # shows the live shim/symlink path
git config --global --get-regexp credential
```

## Fix

Repoint the helper at `gh` resolved via `PATH`/mise shim instead of a versioned absolute path — this survives future mise auto-updates:

```sh
git config --global --replace-all credential.'https://github.com'.helper '' ''
git config --global --add credential.'https://github.com'.helper '!gh auth git-credential'
```

Note: `credential.<url>.helper` is multi-valued (an empty-string reset entry commonly precedes the real helper, same pattern used for e.g. `git.phermata.org` + `glab`). A plain `git config --global credential.X.helper VALUE` errors with "cannot overwrite multiple values with a single value" — must use `--replace-all` (to reset to a single empty value) then `--add` (to layer the real helper), matching the existing empty+real pattern rather than collapsing it.

Repeat for any other host using the same versioned-path pattern (e.g. `gist.github.com`).

Verify:
```sh
printf 'protocol=https\nhost=github.com\n\n' | git credential fill
```
Should return `username=...` with no prompt.
