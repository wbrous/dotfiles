---
name: git-config-xdg-config-home-not-isolated-by-home
description: "Use when writing or testing a shell script that manipulates git's global config (git config --global, core.hooksPath, etc.) inside an \"isolated\" sandbox by overriding HOME — especially before running install/uninstall scripts for real, or when a test unexpectedly mutates the real user's ~/.config/git/config."
---

## The trap

Git's global config is NOT solely `$HOME/.gitconfig`. If `$XDG_CONFIG_HOME` (or the default `~/.config`) has a `git/config` file, git prefers/also reads `$XDG_CONFIG_HOME/git/config` for global scope (`git config --global`).

So a test harness that does:

```sh
export HOME=$(mktemp -d)
git config --global core.hooksPath /some/tmp/path
```

...believing it's sandboxed, actually still writes to the REAL `$XDG_CONFIG_HOME/git/config` (e.g. `~/.config/git/config`) if `XDG_CONFIG_HOME` was never unset — because that env var wasn't touched by only reassigning `HOME`. This silently contaminates the real user's global git config (e.g. sets `core.hooksPath` to a tmp dir that gets deleted, breaking git hooks machine-wide) while the test output looks like it succeeded in isolation.

## Fix / correct isolation

To truly sandbox `git config --global` in a test:

```sh
export HOME=$(mktemp -d)
export XDG_CONFIG_HOME="$HOME/.config"   # must override this too
```

Or more robustly, use `GIT_CONFIG_GLOBAL=$(mktemp)` to point git at an explicit throwaway file for the global scope, bypassing both `~/.gitconfig` and `$XDG_CONFIG_HOME/git/config` lookup entirely — this is the most bulletproof option for test isolation.

## Recovery if you already contaminated real state

Check `git config --global --show-origin --get core.hooksPath` (or `cat ~/.config/git/config`) to see what leaked in, diff against what should be there (e.g. a pre-existing tool's hook like gitleaks), and either manually restore the correct value or re-run your own installer's uninstall path against the real environment to reset it before re-running the real install correctly.
