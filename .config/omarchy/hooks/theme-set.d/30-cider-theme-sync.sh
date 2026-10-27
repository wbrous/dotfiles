#!/bin/bash
# Sets Cider's accent color to the active Omarchy theme's `accent` color, and
# puts Cider in light or dark mode to match the theme's mode.
#
# Contract
#   Precondition : Omarchy has an active theme with a colors.toml;
#                  `omarchy-theme-color` is on PATH; Cider keeps its config in
#                  ~/.config/sh.cider.genten/spa-config.yml (Cider 4.x).
#   Postcondition: spa-config.yml has
#                    visual.ui_custom.customAccentColor      = true
#                    visual.ui_custom.customAccentColorValue = the resolved accent
#                    visual.appearance                       = "light" or "dark"
#                  matching the resolved mode. Every other key is untouched.
#                  If Cider was running it is quit first and relaunched after, on
#                  the Hyprland workspace its window was on, without switching the
#                  user's workspace or stealing focus. If Cider was closed it
#                  stays closed.
#   Failure      : exits non-zero, loudly, and leaves spa-config.yml as it was.
#                  It never edits the file while Cider is running: Cider holds the
#                  whole config in memory and rewrites it from there whenever any
#                  setting changes, which would silently undo the edit.
#
# Why these keys (read from Cider's own bundles): the UI writes
# customAccentColorValue straight into the CSS variables --musicKeyColor and
# --keyColor, and any #rrggbb is accepted, not just the preset swatches.
# visual.appearance is "dark", "light" or "auto"; "auto" follows the system
# prefers-color-scheme, so it is set explicitly to follow Omarchy instead.
#
# Installed as an omarchy `theme-set` hook (symlinked into theme-set.d/) so it
# fires after `omarchy theme set`. Safe to run repeatedly.
set -euo pipefail

COLORS_FILE="${CIDER_SYNC_COLORS_FILE:-$HOME/.local/state/omarchy/current/theme/colors.toml}"
CIDER_CONFIG="${CIDER_SYNC_CONFIG:-$HOME/.config/sh.cider.genten/spa-config.yml}"
CIDER_BIN_PATTERN='^/usr/lib/cider/Cider$' # main process only; children carry extra args
CIDER_WINDOW_CLASS="cider"
QUIT_TIMEOUT_SECONDS=30

[[ -f $COLORS_FILE ]] || exit 0 # no active Omarchy theme yet: nothing to sync

die() { echo "cider-omarchy-theme-sync: $*" >&2; exit 1; }

# No Cider config means Cider has never run for this user: nothing to sync.
[[ -f $CIDER_CONFIG ]] || exit 0

cider_running() { pgrep -f "$CIDER_BIN_PATTERN" >/dev/null; }

# Quit Cider gracefully and wait for it to exit.
quit_cider() {
  pkill -TERM -f "$CIDER_BIN_PATTERN" || true
  local waited=0
  while cider_running; do
    ((waited >= QUIT_TIMEOUT_SECONDS)) && die "Cider still running after ${QUIT_TIMEOUT_SECONDS}s; not touching its config"
    sleep 1
    waited=$((waited + 1)) # NOT ((waited++)): that returns 1 when waited is 0 and set -e aborts
  done
}

# Point HYPRLAND_INSTANCE_SIGNATURE at the running session. Hooks run without
# it, so take the newest instance dir under $XDG_RUNTIME_DIR/hypr/.
hypr_env() {
  if [[ -z ${HYPRLAND_INSTANCE_SIGNATURE:-} ]]; then
    HYPRLAND_INSTANCE_SIGNATURE=$(ls -t "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/hypr/" 2>/dev/null | head -n1 || true)
    export HYPRLAND_INSTANCE_SIGNATURE
  fi
}

# Print the name of the Hyprland workspace holding Cider's window, or nothing if
# Hyprland is unreachable or Cider has no mapped window. Must run BEFORE Cider
# is quit: afterwards there is no window left to ask about.
cider_workspace() {
  hypr_env
  [[ -n ${HYPRLAND_INSTANCE_SIGNATURE:-} ]] && command -v hyprctl >/dev/null || return 0
  hyprctl clients -j 2>/dev/null | python3 -c '
import json, sys
try:
    clients = json.load(sys.stdin)
except ValueError:
    sys.exit(0)
for c in clients:
    if c.get("class") == sys.argv[1] and c.get("mapped", True):
        print(c["workspace"]["name"])
        break
' "$CIDER_WINDOW_CLASS"
}

# Relaunch Cider detached, through Hyprland so it gets a proper Wayland session
# even from a hook. With a known workspace it opens there WITHOUT taking focus;
# both no_initial_focus and suppress_event=activatefocus are required, because
# Electron apps request activation after their window is up (see the
# hyprland-launch-app-in-background-no-focus-steal skill).
launch_cider() {
  hypr_env
  if [[ -n ${HYPRLAND_INSTANCE_SIGNATURE:-} ]] && command -v hyprctl >/dev/null; then
    local rules="no_initial_focus=true, suppress_event='activatefocus'"
    if [[ -n $CIDER_WORKSPACE ]]; then
      [[ $CIDER_WORKSPACE =~ ^[A-Za-z0-9_:.+-]+$ ]] || die "refusing to use odd workspace name: '$CIDER_WORKSPACE'"
      rules="workspace='$CIDER_WORKSPACE', $rules"
    fi
    hyprctl dispatch "hl.dsp.exec_cmd('uwsm-app -- cider', {$rules})" >/dev/null
  else
    setsid nohup cider >/dev/null 2>&1 &
  fi
}

# Resolve the palette with Omarchy's own helper, so terminal-style palettes
# (no `accent`/`mode` keys) work the same as semantic ones.
resolve() { omarchy-theme-color --file "$COLORS_FILE" "$1"; }

ACCENT_HEX=$(resolve accent) || die "cannot resolve accent from $COLORS_FILE"
[[ $ACCENT_HEX =~ ^#[0-9a-fA-F]{6}$ ]] || die "accent is not #rrggbb in $COLORS_FILE: '$ACCENT_HEX'"
ACCENT_HEX=${ACCENT_HEX,,}

THEME_MODE=$(resolve mode) || die "cannot resolve mode from $COLORS_FILE"
case $THEME_MODE in
  light | dark) APPEARANCE=$THEME_MODE ;;
  *) die "unexpected theme mode '$THEME_MODE' in $COLORS_FILE" ;;
esac

# Set the three keys in spa-config.yml. Requires Cider to be stopped.
#
# Edited as text, one line each, instead of loading and re-dumping the YAML:
# a round trip through a YAML library would reorder/requote the whole file and
# Cider migrates and reads it itself, so the smallest possible diff is safest.
# Each target is addressed by its indentation inside its parent block, so the
# many other `enabled:` / `appearance`-like keys elsewhere cannot be hit. The
# file is read back afterwards and must contain exactly the intended values.
set_cider_config() {
  python3 - "$CIDER_CONFIG" "$ACCENT_HEX" "$APPEARANCE" <<'PY'
import re, sys

path, accent, appearance = sys.argv[1:4]
lines = open(path).read().split("\n")


def block_range(lines, header, indent):
    """Return (start, end) of the lines inside `header:` at `indent` spaces."""
    pat = re.compile(r"^" + " " * indent + re.escape(header) + r":\s*$")
    starts = [i for i, l in enumerate(lines) if pat.match(l)]
    if len(starts) != 1:
        sys.exit(f"expected exactly one '{header}:' block at indent {indent}, found {len(starts)}")
    start = starts[0] + 1
    end = start
    while end < len(lines) and (lines[end].strip() == "" or len(lines[end]) - len(lines[end].lstrip(" ")) > indent):
        end += 1
    return start, end


def set_key(lines, block, key, indent, value):
    """Replace `key: ...` at exactly `indent` spaces inside the (start, end) block."""
    start, end = block
    pat = re.compile(r"^" + " " * indent + re.escape(key) + r":")
    hits = [i for i in range(start, end) if pat.match(lines[i])]
    if len(hits) != 1:
        sys.exit(f"expected exactly one '{key}' at indent {indent} in its block, found {len(hits)}")
    lines[hits[0]] = " " * indent + f"{key}: {value}"


visual = block_range(lines, "visual", 0)
set_key(lines, visual, "appearance", 2, appearance)
ui_custom = block_range(lines, "ui_custom", 2)
set_key(lines, ui_custom, "customAccentColor", 4, "true")
set_key(lines, ui_custom, "customAccentColorValue", 4, f'"{accent}"')

open(path, "w").write("\n".join(lines))

# Read back: the file we wrote must contain exactly the intended values.
check = open(path).read().split("\n")
v = block_range(check, "visual", 0)
u = block_range(check, "ui_custom", 2)
want = [
    (v, "  appearance: " + appearance),
    (u, "    customAccentColor: true"),
    (u, f'    customAccentColorValue: "{accent}"'),
]
for (start, end), line in want:
    if line not in check[start:end]:
        sys.exit(f"read-back mismatch: missing {line!r}")
print(f"{path}: appearance={appearance} accent={accent}")
PY
}

WAS_RUNNING=0
CIDER_WORKSPACE=""
if cider_running; then
  WAS_RUNNING=1
  CIDER_WORKSPACE=$(cider_workspace)
  quit_cider
fi

set_cider_config

if ((WAS_RUNNING)); then
  launch_cider
fi
exit 0
