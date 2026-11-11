# If not running interactively, don't do anything (leave this at the top of this file)
[[ $- != *i* ]] && return

# All the default Omarchy aliases and functions
# (don't mess with these directly, just overwrite them here!)
# /etc/omarchy.conf is written by omarchy-dev-link. When absent, force the
# package default instead of preserving a stale inherited dev-link value before
# we decide which rc file to source.
if [[ -f /etc/omarchy.conf ]]; then
  source /etc/omarchy.conf
  export OMARCHY_PATH="${OMARCHY_PATH:-/usr/share/omarchy}"
else
  export OMARCHY_PATH=/usr/share/omarchy
fi
source "$OMARCHY_PATH/default/bash/rc"

# Add your own exports, aliases, and functions here.
#
# Make an alias for invoking commands you use constantly
# alias p='python'
export PATH="/home/wils/.cache/.bun/bin:$PATH"
alias b='bun'

# Hermes Agent — ensure ~/.local/bin is on PATH
export PATH="$HOME/.local/bin:$PATH"

# Android Studio
export ANDROID_HOME="$HOME/Android/Sdk"
export PATH="$PATH:$ANDROID_HOME/emulator:$ANDROID_HOME/platform-tools:$ANDROID_HOME/cmdline-tools/latest/bin"
# git: shadow the real git so `git push` always resigns unpushed unsigned
# commits first, then pushes — one command, no "re-run the push command"
# abort. The global pre-push hook (~/.config/git/hooks/pre-push) stays as a
# safety net for pushes that bypass this shell (other shells, IDEs, scripts).
git() {
	if [ "${1:-}" = "push" ]; then
		shift 1
		command git-push-resign "$@"
	else
		command git "$@"
	fi
}

# dotfiles: bare-repo wrapper around git (GIT_DIR=~/.dotfiles, work tree $HOME).
#   dotfiles push      resign-then-push in one command (same flow as `git push`)
#   dotfiles autoadd   stage everything under ~/Docs (see dotfiles-autoadd)
#   dotfiles <git...>  anything else is plain git against the bare repo
dotfiles() {
	case "${1:-}" in
	push)
		shift 1
		GIT_DIR="$HOME/.dotfiles" GIT_WORK_TREE="$HOME" command git-push-resign "$@"
		;;
	autoadd)
		shift 1
		command dotfiles-autoadd "$@"
		;;
	*)
		git --git-dir="$HOME/.dotfiles/" --work-tree="$HOME" "$@"
		;;
	esac
}

. "$HOME/.local/share/../bin/env"
