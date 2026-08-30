---
name: omp-omarchy-theme-sync
description: "Use when building or debugging a mechanism that syncs the omp (oh-my-pi) coding-agent theme with the currently active Omarchy Linux theme — e.g. \"sync omp theme with omarchy theme\", \"apply my omarchy colors to omp\", or when an omp custom theme JSON needs to be generated from an Omarchy colors.toml. Covers the working two-part design (omarchy theme-set hook + omp extension), the exact source-of-truth paths, the full color-token mapping, and the python-yq (not go-yq) in-place syntax gotcha on Arch/Omarchy."
---

## Working design (verified on this machine)

Two independent pieces sharing one conversion script, matching Omarchy's own
event model (a hook fires on theme switch; nothing else pushes updates):

1. **Shared script** `~/.local/share/omp/omarchy-theme-sync.sh`
   - Reads `~/.local/state/omarchy/current/theme/colors.toml` (the live
     Omarchy theme's resolved palette — NOT `~/.config/omarchy/themes/*`,
     which are just the source theme defs). Also has
     `~/.local/state/omarchy/current/theme.name` (slug) and a `mode` key
     inside colors.toml (`"dark"` or `"light"`).
   - Parses the flat `key = "value"` TOML with a small `awk` `get()` helper
     (no TOML library needed — the generated file is always flat).
   - Writes a full omp custom theme to `<agentDir>/themes/omarchy.json`
     (`agentDir` defaults `~/.omp/agent`, overridable via
     `PI_CODING_AGENT_DIR`). Always names it `"omarchy"` — one theme file
     that's regenerated in place, rather than per-omarchy-theme-name files.
   - Updates `<agentDir>/config.yml`'s `theme.dark` or `theme.light` (whichever
     matches Omarchy's `mode`) to `"omarchy"` via `yq -i -y '.theme.<slot> =
     "omarchy"' file` — leaves the other slot untouched.
   - No-ops safely (exit 0) if Omarchy has no active theme yet.

2. **Omarchy hook**: `omarchy hook install theme-set
   ~/.local/share/omp/omarchy-theme-sync.sh` — copies it into
   `~/.config/omarchy/hooks/theme-set.d/`. Fires after every `omarchy theme
   set`, so the omp theme file is fresh even if omp isn't running.
   **Gotcha**: `omarchy hook install` COPIES the script; it does not
   symlink. Editing the canonical script later requires re-running the
   install command to refresh the installed copy — diff the two paths to
   check they still match.

3. **omp extension**: `~/.omp/agent/extensions/omarchy-theme-sync.ts` — on
   `session_start`, `spawnSync`s the shared script (covers "theme changed
   while omp wasn't running"), then if `ctx.hasUI`, calls `await
   ctx.ui.setTheme("omarchy")` to apply live without requiring a restart.
   `ctx.ui.setTheme(name)` takes any theme name (built-in or custom) and
   loads+applies it immediately — this is how a prior unrelated extension in
   this environment toggled between built-in `"light"`/`"dark"` themes too.

## Color-token mapping (colors.toml -> omp theme colors)

Omarchy's `colors.toml` has a fixed flat schema: `accent`, `selection`,
`muted`, `background`, `dark_background`, `darker_background`,
`lighter_background`, `foreground`, `dark_foreground`, `light_foreground`,
`bright_foreground`, `red/yellow/orange/green/cyan/blue/magenta/brown` (+
`bright_*` variants), `mode`.

omp's theme schema (see `omp://theme.md`) requires 51 color tokens across
core text/borders, background blocks, message/tool text, markdown, diff +
syntax highlighting, thinking-level borders, and status-line segments (full
list validated against the runtime schema, not hand-guessed — every
required key must be present or `setTheme` fails validation). Practical
mapping used successfully:

- `accent`→accent, `border`/`muted`/`thinkingText`→muted, `success`→green,
  `error`→red, `warning`→yellow, `dim`→dark_foreground, `text`→foreground
- `selectedBg`/`borderMuted`→selection, `*Bg` (user/custom/toolPending/
  toolSuccess/toolError message backgrounds)→lighter_background (Omarchy
  doesn't expose per-state tinted backgrounds, so these collapse to one)
- markdown: heading/link/listBullet→accent, others→muted/foreground
- diff: added→green, removed→red, context→muted
- syntax: comment→dark_foreground, keyword→magenta, function→blue,
  variable/operator→foreground, string→green, number→orange, type→cyan,
  punctuation→muted
- thinking ladder (off→xhigh): dark_foreground, muted, blue, cyan, magenta,
  red; bashMode→cyan, pythonMode→magenta
- statusLineBg→dark_background; other status segments reuse the same
  green/yellow/cyan/red/orange/magenta/foreground assignments as above

Validate the generated JSON against the real schema before trusting it:
```bash
find / -name theme-schema.json 2>/dev/null   # ships inside the installed omp/pi-coding-agent package
python3 -c "
import json
schema = json.load(open('<path>/theme-schema.json'))
req = schema['properties']['colors']['required']
data = json.load(open('~/.omp/agent/themes/omarchy.json'))
print([k for k in req if k not in data['colors']])  # must print []
"
```

## Critical gotcha: `yq` on Arch is python-yq, not go-yq

`pacman -S yq` on Arch/Omarchy installs **kislyuk/python-yq** (a jq wrapper),
version string like `yq 4.1.2 / jq-1.8.2` — NOT mikefarah/go-yq, despite the
same binary name. Syntax differs:

- **Wrong** (go-yq syntax, silently errors on python-yq):
  `yq -i '.theme.dark = "omarchy"' file.yml`
  → `yq: -i/--in-place can only be used with -y/-Y/-t/-T/-x`
- **Correct** (python-yq): `yq -i -y '.theme.dark = "omarchy"' file.yml`
  (`-y` = read+write YAML through the jq filter; `-i` = in-place)

python-yq round-trips YAML through jq's JSON model, so formatting details
shift on every edit (flow-style `{}` vs block style, quote style on strings
like `'off'` vs `"off"`, trailing newline) — this is harmless noise, not a
bug, when diffing before/after.

## TS extension gotchas hit while building this

- Don't inline-cast a narrowed union result (`(result as {
  success?: boolean }).success`) — write a real type guard function
  (`function isFailedResult(value: unknown): value is {...}`) using
  `typeof`/`"prop" in value` narrowing instead. A type guard is one of the
  allowed exceptions to the "no tiny one-line functions" rule.
- Editing a file with the `edit` tool using a `PUT n.=m:` range: get the
  line numbers from a fresh `read` immediately before editing — reusing
  stale line numbers after a previous partial edit silently corrupts the
  file (duplicated/dangling code blocks) even though the tool reports the
  edit as applied.
