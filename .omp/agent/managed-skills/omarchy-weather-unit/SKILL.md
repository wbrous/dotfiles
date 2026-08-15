---
name: omarchy-weather-unit
description: Use when changing Omarchy bar weather widget between Celsius/Fahrenheit (metric/imperial units).
---

## Setting Omarchy bar weather temperature unit (Celsius vs Fahrenheit)

The weather widget defaults to locale/country-based unit detection
(`shouldUseImperial` in `/usr/share/omarchy/shell/plugins/panels/weather/Model.js`).
Override it explicitly in the user's shell config.

1. Edit `~/.config/omarchy/shell.json`.
2. Find the bar layout entry with `"id": "omarchy.weather"`.
3. Add a `"unit"` key to that same object:
   - `"unit": "metric"` → Celsius
   - `"unit": "imperial"` → Fahrenheit

Example:
```json
{
  "id": "omarchy.weather",
  "unit": "metric"
}
```

No restart needed — `shell.json` hot-reloads on save. Validate JSON syntax
after editing (e.g. `python3 -c "import json;json.load(open(path))"`).

Source of truth: `Panel.qml` line `useImperial: Model.shouldUseImperial(setting("unit", ""), Qt.locale().name, reportCountry)`
— the `unit` setting takes precedence over locale/country detection.

### Pitfall: do NOT run `omarchy restart shell` / `omarchy-restart-shell` after this edit

Observed once: after adding `"unit": "metric"`, running `omarchy restart shell`
caused the running shell to rewrite `~/.config/omarchy/shell.json` and silently
strip the added `"unit"` key back out (file reverted to its pre-edit content).
The bar's drag-reorder autosave path (`mutateShellConfig` in
`plugins/bar/Bar.qml`) re-serializes the layout and can drop keys it doesn't
recognize as part of its normalized schema.

Workflow that actually sticks:
1. Add `"unit"` key to the `omarchy.weather` layout entry.
2. Save — do not restart the shell.
3. Wait a couple seconds for hot-reload, then re-read the file to confirm the
   key is still present (`grep -A2 weather shell.json`).
4. If the widget still doesn't reflect the change, re-check the file for the
   key before assuming the setting itself is wrong — the file may have been
   silently reverted by an unrelated shell action, not by your edit being
   incorrect.
