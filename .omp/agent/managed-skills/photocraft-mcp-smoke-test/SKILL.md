---
name: photocraft-mcp-smoke-test
description: "Use when testing or driving the PhotoCraft image-editor MCP (xd://mcp__photocraft_*): smoke test, command ids, headless vs bridge limits, save/write-root errors."
---

# PhotoCraft MCP smoke test / usage

## Setup
- Tools are `xd://mcp__photocraft_*`; write JSON args to them. Read the xd path first for the schema (or write `{}` and read the validation error, which prints the schema).
- `command_list` with no filter returns ~125 KB; ALWAYS pass `filter` (id/label substring) or `enabled_only`.

## Smoke sequence that worked (headless mode)
1. `session_list` -> `doc_new` {width,height,name,background:"#rrggbb"}.
2. `command_batch` {steps:[{id,params}...]} for edits:
   - `layer.new.layer` {name} -> returns {layer:id}
   - `select.rect` {x,y,width,height,ellipse?}; `edit.fill` {contents:"color",color:"#rrggbb"} fills the selection
   - `paint.stroke` {points:[[x,y],...],size,color,hardness}
   - `layer.setProps` {layer,opacity:0..1,blend:"Multiply"}
   - `layer.select` {layer}; `filter.blur.gaussianBlur` {radius}; `image.adjustments.invert`
   - `edit.undo` -> true
   - `document.pixel` {x,y} -> [r,g,b,a] 0..1 floats (best way to verify edits numerically)
3. `doc_inspect` (layers/history/selection), `doc_render_preview` {max_side} for visual proof.
4. `command_run` with `wait:false` -> {job:id}; poll `jobs_list` until state "done".
5. `doc_close`, confirm `session_list` empty.

## Gotchas
- A leftover selection clips later paint/fill; run `select.deselect` before painting elsewhere.
- Out-of-range params are silently clamped (blur radius 5000 -> 1000), not rejected.
- `command_batch` stops at first error unless `stop_on_error:false`; unknown ids give `unknown command`.
- Layer ids are not 0-based (first new layer after Background was id 3).
- `doc_save`/`doc_export`/`doc_open` fail with "write authority is absent" unless the server was launched with a write/read root; absolute paths and `../` are always rejected (relative forward-slash paths only).
- `ui_*` tools (ui_inspect, ui_screenshot, ui_pointer, ...) need bridge mode: `photocraft --control <port> --control-token-file <path>` then `photocraft-cli mcp --bridge 127.0.0.1:<port> --control-token-file <path>`. Headless `doc_render_preview` rejects nothing but bridge previews reject `index`.
