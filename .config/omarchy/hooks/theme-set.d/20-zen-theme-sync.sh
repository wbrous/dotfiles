#!/bin/bash
# Sets the theme of every Zen Browser space (workspace) to the active Omarchy
# theme's `dark_background` color, and puts Zen in light or dark mode to match
# the theme's mode.
#
# Contract
#   Precondition : Omarchy has an active theme with a colors.toml; `omarchy-theme-color`
#                  is on PATH; Zen's profile is the one named by Zen's installs.ini.
#                  The palette may be semantic (dark_background/mode) or
#                  terminal-style (background + color0..15 only): the helper
#                  derives what is missing.
#   Postcondition: every space in zen-sessions.jsonlz4 (and the two backup
#                  copies Zen restores from) has exactly one flat gradient color
#                  equal to the resolved dark_background. Tabs/names/icons are
#                  untouched. prefs.js has zen.view.window.scheme = 1 when the
#                  resolved mode is "light", 0 when "dark".
#                  If Zen was running it is quit first and relaunched after, on
#                  the Hyprland workspace its window was on, without switching
#                  the user's workspace or stealing focus. If Zen was closed it
#                  stays closed.
#   Failure      : exits non-zero, loudly, and leaves the session files and
#                  prefs.js as they were. It never edits them while Zen is
#                  running, because Zen rewrites them on exit and would undo
#                  the change.
#
# Installed as an omarchy `theme-set` hook (symlinked into theme-set.d/) so it
# fires after `omarchy theme set`. Safe to run repeatedly.
set -euo pipefail

COLORS_FILE="${ZEN_SYNC_COLORS_FILE:-$HOME/.local/state/omarchy/current/theme/colors.toml}"
ZEN_DIR="$HOME/.config/zen"
ZEN_BIN_PATTERN="/opt/zen-browser-bin/zen-bin"
QUIT_TIMEOUT_SECONDS=30

[[ -f $COLORS_FILE ]] || exit 0 # no active Omarchy theme yet: nothing to sync

die() { echo "zen-omarchy-theme-sync: $*" >&2; exit 1; }

# Zen's active profile directory, from installs.ini (Default= is relative to ZEN_DIR).
profile_dir() {
  local rel
  rel=$(awk -F= '/^Default=/ { print $2; exit }' "$ZEN_DIR/installs.ini")
  [[ -n $rel && -d "$ZEN_DIR/$rel" ]] || die "cannot resolve Zen profile from $ZEN_DIR/installs.ini"
  printf '%s\n' "$ZEN_DIR/$rel"
}

zen_running() { pgrep -f "$ZEN_BIN_PATTERN" >/dev/null; }

# Quit Zen gracefully so it flushes its session, then wait for it to exit.
quit_zen() {
  pkill -TERM -f "${ZEN_BIN_PATTERN}\$" || true
  local waited=0
  while zen_running; do
    ((waited >= QUIT_TIMEOUT_SECONDS)) && die "Zen still running after ${QUIT_TIMEOUT_SECONDS}s; not touching session files"
    sleep 1
    waited=$((waited + 1)) # NOT ((waited++)): that returns 1 when waited is 0 and set -e aborts
  done
}

# Print the name of the Hyprland workspace holding Zen's window, or nothing if
# Hyprland is unreachable or Zen has no mapped window. Must run BEFORE Zen is
# quit: afterwards there is no window left to ask about. The workspace *name*
# (not id) is used because that is what a launch rule accepts, including for
# named and special workspaces whose ids are negative or non-numeric.
zen_workspace() {
  hypr_env
  [[ -n ${HYPRLAND_INSTANCE_SIGNATURE:-} ]] && command -v hyprctl >/dev/null || return 0
  hyprctl clients -j 2>/dev/null | python3 -c '
import json, sys
try:
    clients = json.load(sys.stdin)
except ValueError:
    sys.exit(0)
for c in clients:
    if c.get("class") == "zen" and c.get("mapped", True):
        print(c["workspace"]["name"])
        break
'
}

# Point HYPRLAND_INSTANCE_SIGNATURE at the running session. Hooks run without
# it, so take the newest instance dir under $XDG_RUNTIME_DIR/hypr/.
hypr_env() {
  if [[ -z ${HYPRLAND_INSTANCE_SIGNATURE:-} ]]; then
    HYPRLAND_INSTANCE_SIGNATURE=$(ls -t "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/hypr/" 2>/dev/null | head -n1 || true)
    export HYPRLAND_INSTANCE_SIGNATURE
  fi
}

# Launch Zen detached from this process, via Hyprland so it gets a proper
# Wayland session even when this runs from a hook. If ZEN_WORKSPACE is set, the
# window opens on that workspace WITHOUT taking focus.
#
# Two rules are both required to leave the user's workspace and focused window
# alone (verified on Hyprland 0.56 by sampling focus every 250ms for 25s after
# launch, repeated):
#   no_initial_focus      stops the window being focused when it first maps.
#   suppress_event=activatefocus  stops Zen taking focus afterwards: it is a
#                         Firefox-based browser and requests activation once its
#                         window is up, which Hyprland honours (misc:focus_on_activate).
# With no_initial_focus alone Zen still pulled the view to its workspace.
launch_zen() {
  hypr_env
  if [[ -n ${HYPRLAND_INSTANCE_SIGNATURE:-} ]] && command -v hyprctl >/dev/null; then
    local rules="no_initial_focus=true, suppress_event='activatefocus'"
    if [[ -n $ZEN_WORKSPACE ]]; then
      [[ $ZEN_WORKSPACE =~ ^[A-Za-z0-9_:.+-]+$ ]] || die "refusing to use odd workspace name: '$ZEN_WORKSPACE'"
      rules="workspace='$ZEN_WORKSPACE', $rules"
    fi
    hyprctl dispatch "hl.dsp.exec_cmd('zen-browser', {$rules})" >/dev/null
  else
    setsid nohup zen-browser >/dev/null 2>&1 &
  fi
}

# Resolve the palette with Omarchy's own helper rather than parsing colors.toml
# here: it understands terminal-style palettes (color0..color15, no
# dark_background), derives a missing dark_background, and decides light/dark
# the same way the rest of the desktop does (mode, theme_type, light.mode file,
# then background luminance, then dark).
resolve() { omarchy-theme-color --file "$COLORS_FILE" "$1"; }

BACKGROUND_HEX=$(resolve dark_background) || die "cannot resolve dark_background from $COLORS_FILE"
[[ $BACKGROUND_HEX =~ ^#[0-9a-fA-F]{6}$ ]] || die "dark_background is not #rrggbb in $COLORS_FILE: '$BACKGROUND_HEX'"
BACKGROUND_HEX=${BACKGROUND_HEX,,}

THEME_MODE=$(resolve mode) || die "cannot resolve mode from $COLORS_FILE"
case $THEME_MODE in
  light) ZEN_SCHEME=1 ;;
  dark) ZEN_SCHEME=0 ;;
  *) die "unexpected theme mode '$THEME_MODE' in $COLORS_FILE" ;;
esac

PROFILE=$(profile_dir)

# Write the color into one mozlz4 session file. Requires Zen to be stopped.
# isCustom=true makes Zen use the CSS color string verbatim (no opacity blend),
# so the sidebar renders exactly BACKGROUND_HEX; opacity 1 / texture 0 keep it flat.
set_space_themes() {
  uv run --quiet --with lz4 python - "$BACKGROUND_HEX" "$@" <<'PY'
import json, sys
import lz4.block

MAGIC = b"mozLz40\0"
color, paths = sys.argv[1], sys.argv[2:]
theme = {
    "type": "gradient",
    "gradientColors": [{
        "c": color, "isCustom": True, "isPrimary": True,
        "algorithm": "floating", "lightness": "50", "type": "explicit-lightness",
    }],
    "opacity": 1,
    "texture": 0,
}
for path in paths:
    raw = open(path, "rb").read()
    assert raw[:8] == MAGIC, f"{path}: not a mozlz4 file"
    data = json.loads(lz4.block.decompress(raw[8:]))
    assert data["spaces"], f"{path}: no spaces found"
    tabs_before = json.dumps(data["tabs"], sort_keys=True)
    for space in data["spaces"]:
        space["theme"] = json.loads(json.dumps(theme))
    assert json.dumps(data["tabs"], sort_keys=True) == tabs_before
    out = MAGIC + lz4.block.compress(json.dumps(data, separators=(",", ":")).encode(), store_size=True)
    open(path, "wb").write(out)
    # Read back: the file we wrote must decode to the color we intended.
    check = json.loads(lz4.block.decompress(open(path, "rb").read()[8:]))
    for space in check["spaces"]:
        assert space["theme"]["gradientColors"][0]["c"] == color, f"{path}: read-back mismatch"
    print(f"{path}: {len(check['spaces'])} spaces -> {color}")
PY
}

# Set zen.view.window.scheme in prefs.js (0 dark, 1 light, 2 auto). Requires Zen
# to be stopped: Zen rewrites prefs.js on exit. Edits the one line in place so
# every other pref is left alone, and reads the file back to prove it took.
set_zen_scheme() {
  local prefs="$1/prefs.js" line="user_pref(\"zen.view.window.scheme\", $ZEN_SCHEME);"
  [[ -f $prefs ]] || die "no prefs.js at $prefs"
  if grep -q '^user_pref("zen.view.window.scheme"' "$prefs"; then
    sed -i "s|^user_pref(\"zen.view.window.scheme\".*|$line|" "$prefs"
  else
    printf '%s\n' "$line" >>"$prefs"
  fi
  grep -qxF "$line" "$prefs" || die "failed to set zen.view.window.scheme in $prefs"
  echo "$prefs: zen.view.window.scheme = $ZEN_SCHEME"
}

WAS_RUNNING=0
ZEN_WORKSPACE=""
if zen_running; then
  WAS_RUNNING=1
  ZEN_WORKSPACE=$(zen_workspace)
  quit_zen
fi

FILES=("$PROFILE/zen-sessions.jsonlz4")
for f in "$PROFILE/zen-sessions-backup/clean.jsonlz4" "$PROFILE/zen-sessions-backup/recovery.baklz4"; do
  [[ -f $f ]] && FILES+=("$f")
done
[[ -f ${FILES[0]} ]] || die "no session file at ${FILES[0]}"

set_space_themes "${FILES[@]}"
set_zen_scheme "$PROFILE"

if ((WAS_RUNNING)); then
  launch_zen
fi
exit 0
