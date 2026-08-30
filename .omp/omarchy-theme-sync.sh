#!/bin/bash
# Generates an omp (oh-my-pi) custom theme named "omarchy" from the currently
# active Omarchy theme's colors.toml, and points omp's theme.<mode> setting at
# it. Safe to run any number of times; a no-op when Omarchy has no active
# theme yet.
#
# Installed as the omarchy `theme-set` hook (fires after `omarchy theme set`)
# and invoked directly by the `omarchy-theme-sync` omp extension on session
# start, so both the "switch theme" and "start omp" paths stay in sync.
set -euo pipefail

COLORS_FILE="$HOME/.local/state/omarchy/current/theme/colors.toml"
[[ -f $COLORS_FILE ]] || exit 0

get() {
  awk -F'=' -v key="$1" '
    {
      k = $1
      gsub(/^[ \t]+|[ \t]+$/, "", k)
      if (k == key) {
        val = $0
        sub(/^[^=]*=[ \t]*/, "", val)
        gsub(/^"|"$/, "", val)
        print val
        exit
      }
    }
  ' "$COLORS_FILE"
}

ACCENT=$(get accent)
SELECTION=$(get selection)
MUTED=$(get muted)
BACKGROUND=$(get background)
DARK_BACKGROUND=$(get dark_background)
LIGHTER_BACKGROUND=$(get lighter_background)
FOREGROUND=$(get foreground)
DARK_FOREGROUND=$(get dark_foreground)
RED=$(get red)
YELLOW=$(get yellow)
ORANGE=$(get orange)
GREEN=$(get green)
CYAN=$(get cyan)
BLUE=$(get blue)
MAGENTA=$(get magenta)

AGENT_DIR="${PI_CODING_AGENT_DIR:-$HOME/.omp/agent}"
THEMES_DIR="$AGENT_DIR/themes"
mkdir -p "$THEMES_DIR"
OUT_FILE="$THEMES_DIR/omarchy.json"

cat >"$OUT_FILE" <<JSON
{
  "\$comment": "Auto-generated from the active Omarchy theme by omarchy-theme-sync.sh. Do not hand-edit; re-run 'omarchy theme set' or restart omp to regenerate.",
  "name": "omarchy",
  "colors": {
    "accent": "$ACCENT",
    "border": "$MUTED",
    "borderAccent": "$ACCENT",
    "borderMuted": "$SELECTION",
    "success": "$GREEN",
    "error": "$RED",
    "warning": "$YELLOW",
    "muted": "$MUTED",
    "dim": "$DARK_FOREGROUND",
    "text": "$FOREGROUND",
    "thinkingText": "$MUTED",

    "selectedBg": "$SELECTION",
    "userMessageBg": "$LIGHTER_BACKGROUND",
    "userMessageText": "$FOREGROUND",
    "customMessageBg": "$LIGHTER_BACKGROUND",
    "customMessageText": "$FOREGROUND",
    "customMessageLabel": "$ACCENT",
    "toolPendingBg": "$LIGHTER_BACKGROUND",
    "toolSuccessBg": "$LIGHTER_BACKGROUND",
    "toolErrorBg": "$LIGHTER_BACKGROUND",
    "toolTitle": "$FOREGROUND",
    "toolOutput": "$MUTED",

    "mdHeading": "$ACCENT",
    "mdLink": "$ACCENT",
    "mdLinkUrl": "$MUTED",
    "mdCode": "$FOREGROUND",
    "mdCodeBlock": "$FOREGROUND",
    "mdCodeBlockBorder": "$MUTED",
    "mdQuote": "$MUTED",
    "mdQuoteBorder": "$MUTED",
    "mdHr": "$MUTED",
    "mdListBullet": "$ACCENT",

    "toolDiffAdded": "$GREEN",
    "toolDiffRemoved": "$RED",
    "toolDiffContext": "$MUTED",
    "syntaxComment": "$DARK_FOREGROUND",
    "syntaxKeyword": "$MAGENTA",
    "syntaxFunction": "$BLUE",
    "syntaxVariable": "$FOREGROUND",
    "syntaxString": "$GREEN",
    "syntaxNumber": "$ORANGE",
    "syntaxType": "$CYAN",
    "syntaxOperator": "$FOREGROUND",
    "syntaxPunctuation": "$MUTED",

    "thinkingOff": "$DARK_FOREGROUND",
    "thinkingMinimal": "$MUTED",
    "thinkingLow": "$BLUE",
    "thinkingMedium": "$CYAN",
    "thinkingHigh": "$MAGENTA",
    "thinkingXhigh": "$RED",
    "bashMode": "$CYAN",
    "pythonMode": "$MAGENTA",

    "statusLineBg": "$DARK_BACKGROUND",
    "statusLineSep": "$MUTED",
    "statusLineModel": "$MAGENTA",
    "statusLinePath": "$BLUE",
    "statusLineGitClean": "$GREEN",
    "statusLineGitDirty": "$YELLOW",
    "statusLineContext": "$CYAN",
    "statusLineSpend": "$CYAN",
    "statusLineStaged": "$GREEN",
    "statusLineDirty": "$YELLOW",
    "statusLineUntracked": "$RED",
    "statusLineOutput": "$FOREGROUND",
    "statusLineCost": "$ORANGE",
    "statusLineSubagents": "$MAGENTA"
  }
}
JSON

# Omarchy only ever has one active theme, and the terminal's real background
# already matches it -- so both slots should point at the same generated
# theme. This makes omp's dark/light auto-detection irrelevant instead of
# risking a stale slot rendering a leftover palette.
if command -v yq >/dev/null 2>&1; then
  CONFIG_FILE="$AGENT_DIR/config.yml"
  [[ -f $CONFIG_FILE ]] || printf '{}\n' >"$CONFIG_FILE"
  yq -i -y '.theme.dark = "omarchy" | .theme.light = "omarchy"' "$CONFIG_FILE"
fi
