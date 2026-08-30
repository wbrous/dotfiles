---
name: omp-omarchy-theme-sync
description: "Use when building or debugging a mechanism that syncs the omp (oh-my-pi) coding-agent theme with the currently active Omarchy Linux theme — e.g. \"sync omp theme with omarchy theme\", \"apply my omarchy colors to omp\", or when an omp custom theme JSON needs to be generated from an Omarchy colors.toml. Covers the working two-part design (omarchy theme-set hook + omp extension), the exact source-of-truth paths, the full color-token mapping, the python-yq (not go-yq) in-place syntax gotcha on Arch/Omarchy, the symlinked-hook approach, dotfiles sync status of the artifacts, and why both theme.dark and theme.light must point at the same generated theme."
---

## Goal

Generate an omp custom theme (`~/.omp/agent/themes/omarchy.json`) from the currently active Omarchy theme's palette, keep it in sync whenever the Omarchy theme changes, and apply it in omp on startup.

## Source of truth paths (Omarchy)

- Active theme colors: `~/.local/state/omarchy/current/theme/colors.toml` (flat `key = "value"` TOML, keys: `mode`, `accent`, `selection`, `muted`, `background`, `dark_background`, `darker_background`, `lighter_background`, `foreground`, `dark_foreground`, `light_foreground`, `bright_foreground`, `red`, `yellow`, `orange`, `green`, `cyan`, `blue`, `magenta`, `brown`, plus `bright_*` variants).
- Active theme slug: `~/.local/state/omarchy/current/theme.name`.
- **Not** `~/.config/omarchy/current/...` — that path doesn't exist; state lives under `~/.local/state/omarchy/current/`.

## Design: two parts, one shared script

1. **Shared conversion script** (canonical location: `~/.omp/omarchy-theme-sync.sh`): reads `colors.toml`, writes the full omp theme JSON, and updates `~/.omp/agent/config.yml`. Keep it OUT of `~/.local/share/omp/` — that XDG-data path is not the active agent dir for this setup and its presence confuses state resolution.
2. **Omarchy `theme-set` hook**: `omarchy hook install theme-set <script>` **copies** the script into `~/.config/omarchy/hooks/theme-set.d/`, but that's not required — Omarchy doesn't care if it's a symlink. Prefer a **symlink to the canonical script** so edits propagate without re-copying. Keep the canonical script at `~/.omp/omarchy-theme-sync.sh` and point the hook at it:
   `ln -sf ~/.omp/omarchy-theme-sync.sh ~/.config/omarchy/hooks/theme-set.d/omarchy-theme-sync.sh`
3. **omp extension** (`~/.omp/agent/extensions/*.ts`): on `session_start`, spawn the same shared script (`node:child_process` `spawnSync`), then if `ctx.hasUI`, call `await ctx.ui.setTheme("omarchy")` to apply immediately without a restart. `ctx.ui.setTheme(name)` loads and applies any theme (built-in or custom) by name. The extension references the script via `join(homedir(), ".omp/omarchy-theme-sync.sh")`.

This covers both paths: theme switched while omp isn't running (hook writes the file), and omp started fresh (extension re-syncs + applies live).

## Dotfiles sync (bare repo)

Both artifacts are tracked in the dotfiles bare repo (`~/.dotfiles`, commit convention "Add omp-omarchy theme sync script and extension"):
- `.omp/omarchy-theme-sync.sh` — canonical script (mode 100755)
- `.omp/agent/extensions/omarchy-theme-sync.ts` — extension (mode 100644)

The `theme-set.d/omarchy-theme-sync.sh` hook entry is a **machine-specific symlink and deliberately NOT tracked** — recreate on a fresh machine with `ln -sf ~/.omp/omarchy-theme-sync.sh ~/.config/omarchy/hooks/theme-set.d/omarchy-theme-sync.sh` (matches the repo's convention of only tracking `.sample` hooks under `theme-set.d/`). The generated `~/.omp/agent/themes/omarchy.json` is derived state and is NOT tracked (changes on every theme switch).

## omp theme JSON: color token mapping from Omarchy palette

omp requires 51 color tokens (see `omp://theme.md`). A solid, defensible mapping from Omarchy's ~20 palette keys:

- `accent`/`borderAccent`/`mdHeading`/`mdLink`/`mdListBullet` → `accent`
- `border` → `muted`; `borderMuted`/`selectedBg` → `selection`
- `success`/`toolDiffAdded`/`syntaxString` → `green`; `error`/`toolDiffRemoved` → `red`; `warning`/`statusLineGitDirty`/`statusLineDirty` → `yellow`
- `text`/`toolTitle`/`syntaxVariable`/`mdCode*` → `foreground`; `dim`/`syntaxComment`/`thinkingOff` → `dark_foreground`
- `userMessageBg`/`customMessageBg`/`toolPendingBg`/`toolSuccessBg`/`toolErrorBg` → `lighter_background` (fine to reuse one bg for all three tool states — no per-state blends available from the palette)
- `statusLineBg` → `dark_background`
- `syntaxKeyword`/`thinkingHigh`/`pythonMode`/`statusLineModel`/`statusLineSubagents` → `magenta`
- `syntaxFunction`/`thinkingLow`/`statusLinePath` → `blue`; `syntaxType`/`thinkingMedium`/`bashMode`/`statusLineContext`/`statusLineSpend` → `cyan`
- `syntaxNumber`/`statusLineCost` → `orange`
- `syntaxOperator` → `foreground`; `syntaxPunctuation`/`toolDiffContext`/`mdQuote*`/`mdHr`/`mdLinkUrl`/`toolOutput`/`thinkingMinimal`/`statusLineSep` → `muted`
- `thinkingXhigh`/`statusLineUntracked` → `red`; `statusLineGitClean`/`statusLineStaged` → `green`; `statusLineOutput` → `foreground`
- Optional `thinkingMax` can be omitted — it falls back to `thinkingXhigh`.

Validate against the real schema before shipping: find `theme-schema.json` under an installed `@earendil-works/pi-coding-agent` (or `@oh-my-pi/pi-coding-agent`) package (e.g. under `~/.local/share/*/node_modules/`), then check `required` colors list against generated JSON keys with a quick Python script.

## Critical gotcha: `theme.dark` AND `theme.light` must both be set

Omarchy only ever has one active theme at a time, and the terminal's real background already matches it. If you only update `theme.<mode>` (the slot matching the palette's own `mode` field) and leave the other slot alone, omp's OSC11-luminance auto dark/light detection can pick the *stale* slot and render an unrelated leftover theme. Fix: always set **both** `theme.dark` and `theme.light` to the same generated theme name (`"omarchy"`), unconditionally — don't branch on the palette's `mode` field for this. This makes the auto-detection irrelevant — either slot renders the current, correct palette.

```bash
yq -i -y '.theme.dark = "omarchy" | .theme.light = "omarchy"' "$CONFIG_FILE"
```

## Critical gotcha: `yq` variant on Arch/Omarchy

`/usr/bin/yq` on this system is **python-yq** (kislyuk/yq, a jq wrapper), version `4.1.2` (`jq-1.8.2` reported alongside it) — **not** mikefarah/go-yq. Its in-place-edit syntax differs:

- **Wrong** (go-yq syntax, fails with `-i/--in-place can only be used with -y/-Y/-t/-T/-x`): `yq -i '.theme.dark = "omarchy"' file.yml`
- **Right** (python-yq): `yq -i -y '.theme.dark = "omarchy"' file.yml` — the `-y` flag is required to round-trip YAML output; `-i` alone silently rejects.

python-yq's expression is real jq syntax (double-quote strings, `|` to pipe multiple assignments), unlike go-yq's own dialect. Round-tripping through jq/python also normalizes formatting (e.g. `{}` block-style vs `{}` flow-style, quote style, trailing newline) — harmless but shows up in diffs.

## Gotcha: `~/.local/share/omp/` is NOT the agent dir

The real agent data dir on this machine is `~/.omp/agent/` (config.yml, agent.db with credentials, models.db). The omp extension discovery path and theme dir are `~/.omp/agent/...`. Do NOT place theme-sync state under `~/.local/share/omp/` — an empty dir there can be mistaken for the active state root and leads to "No model selected" (empty credentials). If a stray empty `~/.local/share/omp/` appears, remove it (`rm -rf ~/.local/share/omp/`) — it's scaffolding, not real data; all real data lives under `~/.omp/`.

## Verification approach (no live terminal needed)

1. `bash -n script.sh` for syntax.
2. Run the script twice in a row to confirm idempotency.
3. `python3 -m json.tool generated-theme.json` for JSON validity.
4. Diff the generated JSON's `colors` keys against the real schema's `required` array (find `theme-schema.json` in an installed npm package) — confirms zero missing tokens without needing to launch omp interactively.
5. A `omp -p "..."` smoke run can fail early on missing API keys before reaching `session_start`/extension load — that's expected in a sandboxed/unauthenticated environment and doesn't indicate an extension bug. BUT be warned: launching `omp` itself may create a fresh `~/.local/share/omp/` scaffold; clean it up after.
6. Always back up and restore `~/.omp/agent/config.yml` around test runs that mutate the user's real `theme.dark`/`theme.light` settings — a verification pass should leave the user's actual configuration untouched unless they've asked for the change to stick.
