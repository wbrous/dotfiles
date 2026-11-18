#!/bin/bash
# Regenerates the Multica "omarchy" theme's theme.css from the active Omarchy
# theme's colors.toml. Select Settings -> Appearance -> "Omarchy" in Multica
# once; every `omarchy theme set` afterwards rewrites the file in place.
#
# Precondition: ~/.config/Multica/themes/omarchy/manifest.json exists (the
# folder is only maintained once Multica has it installed); else exit 0.
# Postcondition: the running Multica desktop app is killed; theme.css holds the same palette under .theme-light and
# .theme-dark, so the theme looks right whichever mode Multica is in.
set -euo pipefail

COLORS_FILE="$HOME/.local/state/omarchy/current/theme/colors.toml"
THEME_DIR="$HOME/.config/Multica/themes/omarchy"
[[ -f $COLORS_FILE && -f $THEME_DIR/manifest.json ]] || exit 0

get() {
  awk -F'=' -v key="$1" '
    { k = $1; gsub(/^[ \t]+|[ \t]+$/, "", k)
      if (k == key) { v = $0; sub(/^[^=]*=[ \t]*/, "", v); gsub(/^"|"$/, "", v); print v; exit } }
  ' "$COLORS_FILE"
}

declare -A c
for key in accent muted background dark_background lighter_background foreground \
  red yellow orange green cyan blue magenta; do
  c[$key]=$(get "$key")
  [[ ${c[$key]} =~ ^#[0-9a-fA-F]{6}$ ]] || { echo "multica-sync: bad or missing '$key' in $COLORS_FILE" >&2; exit 1; }
done

fg=${c[foreground]} bg=${c[background]}
mix() { echo "color-mix(in srgb, $fg $1%, $bg)"; }

tmp=$(mktemp "$THEME_DIR/theme.css.XXXXXX")
trap 'rm -f "$tmp"' EXIT
cat >"$tmp" <<CSS
/* Auto-generated from the active Omarchy theme by
 * ~/.config/omarchy/hooks/theme-set.d/50-multica-sync.sh. Do not hand-edit. */
.theme-light, .theme-dark {
  --app-shell: ${c[dark_background]};
  --page-canvas: $bg;
  --surface: $bg;
  --surface-foreground: $fg;
  --surface-raised: $(mix 7);
  --surface-hover: $(mix 14);
  --surface-selected: color-mix(in srgb, ${c[accent]} 28%, $bg);
  --surface-selected-foreground: $fg;
  --surface-border: ${c[muted]};
  --foreground: $fg;
  --card-foreground: $fg;
  --popover-foreground: $fg;
  --primary: ${c[accent]};
  --primary-foreground: ${c[background]};
  --secondary: ${c[lighter_background]};
  --secondary-foreground: $fg;
  --muted: $(mix 14);
  --muted-foreground: $(mix 72);
  --faint-foreground: $(mix 55);
  --accent: color-mix(in srgb, ${c[accent]} 30%, $(mix 7));
  --accent-foreground: $fg;
  --border: ${c[muted]};
  --input: ${c[muted]};
  --ring: ${c[accent]};
  --sidebar: ${c[dark_background]};
  --sidebar-foreground: $fg;
  --sidebar-primary: ${c[accent]};
  --sidebar-primary-foreground: ${c[background]};
  --sidebar-accent: ${c[lighter_background]};
  --sidebar-accent-foreground: $fg;
  --sidebar-border: ${c[muted]};
  --sidebar-ring: ${c[accent]};
  --brand: ${c[accent]};
  --brand-foreground: ${c[background]};
  --destructive: ${c[red]};
  --success: ${c[green]};
  --warning: ${c[yellow]};
  --info: ${c[blue]};
  --chart-1: ${c[accent]};
  --chart-2: ${c[blue]};
  --chart-3: ${c[green]};
  --chart-4: ${c[yellow]};
  --chart-5: ${c[magenta]};
  --tooltip: $(mix 14);
  --tooltip-foreground: $fg;
  --palette-red: ${c[red]};
  --palette-orange: ${c[orange]};
  --palette-yellow: ${c[yellow]};
  --palette-green: ${c[green]};
  --palette-teal: ${c[cyan]};
  --palette-blue: ${c[blue]};
  --palette-indigo: ${c[blue]};
  --palette-purple: ${c[magenta]};
  --palette-pink: ${c[magenta]};
  --label-chip-color: ${c[background]};
}
CSS
mv "$tmp" "$THEME_DIR/theme.css"

# Multica reads theme.css at launch, so close the desktop app (not the
# `multica daemon`) to make the next launch pick up the new colors.
pkill -x multica-desktop || true
