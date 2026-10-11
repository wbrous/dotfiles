---
name: photocraft-mcp-smoke-test
description: "Use for ANY PhotoCraft image-editor task: photocraft-cli (run/convert/info/batch/serve), the PhotoCraft MCP (xd://mcp__photocraft_*), mcp.json roots/bridge config, command ids/recipes, headless vs GUI bridge, save/write-root errors."
---

# PhotoCraft (v0.6.0): CLI, MCP, config, recipes

PhotoCraft is a Photoshop-like editor. ONE registry of ~851 engine commands (e.g. `layer.new.layer`, `filter.blur.gaussianBlur`) is driven identically by the GUI, `photocraft-cli`, a JSON control channel, and the MCP server. Learn the command ids once; every surface uses them.

## Pick the surface

| Goal | Use |
|---|---|
| One-shot edit/convert of files, scripting | `photocraft-cli run/convert/info/batch` (no MCP, no roots needed) |
| Interactive multi-step editing with previews | MCP tools `xd://mcp__photocraft_*` (headless engine) |
| Drive/inspect the live GUI window (`ui_*`) | MCP bridge mode (needs GUI launched with `--control`) |

NEVER run `photocraft --help` (or any unknown flag): the GUI binary opens a window and treats `--help` as a file. Help is `photocraft-cli --help`.

## photocraft-cli

- `run (<file> | --new '<json>') --cmd <id> [--params '<json>'] [--cmd ...] --out <file>`: each `--params` binds to the PRECEDING `--cmd`. Prints one JSON result per command. `--new` takes the `file.new` params: `{"width","height","background":"white|black|transparent|#rrggbb","mode","depth","resolution","name"}`.
- `info <file> --compact`: document JSON (size, layers `[{name,kind,...}]`).
- `convert <in> <out> [--quality 1-100] [--tiff-layers]`: format by extension (.pcraft .psd .png .jpg .tif .webp .exr).
- `commands [--json] [--filter text]`: registry search. ALWAYS filter; the full list is ~125 KB. `--json` gives `[{id,label,menu,params,enabled}]`; the `params` string documents each command's keys, ranges and defaults, so read it before guessing.
- `batch --actions a.json --in dir --out dir`: apply an action list (`[[id,params],...]`) to a folder; `--out` equal to `--in` is refused unless `--in-place`.
- `droplet`, `serve` (JSON-lines server on stdio or `--port`; takes several seconds to bind, wait for the port).
- A flag a subcommand does not take is an error. Exit is loud; read the message.
- PNG/JPG/WebP output FLATTENS layers (warning printed). Save `.pcraft` (native, lossless) or `.psd` to keep layers; reopening `.pcraft` preserves Type/Fill/Adjustment layer kinds.

## MCP config (`~/.omp/agent/mcp.json`)

Two entries, already set up. Editing args needs an omp restart or MCP reload.

- `PhotoCraft` (headless, enabled): `photocraft-cli mcp --automation-read-root ~/Pictures/photocraft-agent/in --automation-write-root ~/Pictures/photocraft-agent/out`, `timeout: 120000`.
- `PhotoCraft-Bridge` (`enabled: false`): `photocraft-cli mcp --bridge 127.0.0.1:47600 --control-token-file ~/.config/photocraft/control-token`.

Without the roots, `doc_open`/`doc_save`/`doc_export` fail with `write authority is absent`. File paths given to MCP tools are RELATIVE forward-slash paths under those roots; absolute paths and `../` are always rejected. To open a file, copy it into the `in` folder first; results land in `out`. The two roots are separate: you cannot save into the read root.

### Enabling bridge mode (`ui_*` tools: ui_inspect, ui_screenshot, ui_pointer, ui_set, ui_menu_invoke)
1. Launch a NEW GUI: `photocraft --control 47600 --control-token-file ~/.config/photocraft/control-token`. A GUI that is already running cannot be switched into control mode.
2. Set `"enabled": true` on `PhotoCraft-Bridge` (and consider disabling headless `PhotoCraft`, since both register the same tool names).
3. Token file: 64 hex chars, mode 600 (`openssl rand -hex 32`). Never pass `--control-token` and the file together.
4. Errors: wrong token -> `authentication required`; nothing listening -> `cannot connect`. `photocraft-cli serve` is NOT a GUI: it answers `unknown method ui.inspect`. Bridge `doc_render_preview` is a window screenshot and rejects `index`. [INFERENCE: bridge mode was only verified for auth/connect against `serve`, never against a real GUI.]

## MCP tools (headless)

Tools are `xd://mcp__photocraft_<name>`. Write JSON args to them; read the path for the schema, or write `{}` and the validation error prints it.

`session_list`, `doc_new {width,height,name,background,mode,depth}`, `doc_open {path}`, `doc_select {index}`, `doc_close`, `doc_save {path,format,quality,tiffLayers}`, `doc_export`, `doc_inspect`, `doc_render_preview {max_side}` (returns a PNG image; use it for visual proof), `command_list {filter,enabled_only}`, `command_run {id,params,wait}`, `command_batch {steps:[{id,params,wait}],stop_on_error}`, `jobs_list`, `jobs_cancel`, `control_call` (bridge only).

Prefer `command_batch` for edits (one history step per command, one round trip). It stops at the first error unless `stop_on_error:false`; unknown ids give `unknown command`. `wait:false` on a slow command returns `{job:id}`; poll `jobs_list` until `state:"done"`, and do not edit that document meanwhile.

## Recipes (all verified)

Layer ids are NOT 0-based: Background is 2, the first new layer is 3. Each creating command returns `{layer:id}`; use that id.

- New layer: `layer.new.layer {name}`
- Filled rectangle/ellipse: `select.rect {x,y,width,height,ellipse?:true}` then `edit.fill {contents:"color",color:"#rrggbb"}` (fills the selection on the active layer). Then `select.deselect`.
- Brush stroke: `paint.stroke {points:[[x,y],...],size,color,hardness}`
- Text: `type.create {x,y,text,size,color,name}` (x,y is the baseline anchor; returns `{layer,bounds}`); paragraph text uses `box:[x,y,w,h]`.
- Gradient fill layer: `layer.newFillLayer.gradient {from,to,angle:90,style:"linear"}`. At angle 90 the `to` colour is at the TOP.
- Solid fill layer: `layer.newFillLayer.solidColor {color}`
- Adjustment layers (non-destructive): `layer.newAdjustmentLayer.<hueSaturation|levels|curves|vibrance|brightnessContrast|...>`; same names under `image.adjustments.*` apply directly to pixels.
- Layer props: `layer.setProps {layer,opacity:0..1,blend:"Multiply",visible,name,locked}`; select with `layer.select {layer}`; move `layer.translate {layer,dx,dy}`; reorder `layer.arrange.bringToFront|sendToBack`.
- Filters: `filter.blur.gaussianBlur {radius}` acts on the SELECTED layer and the current selection (select.all first to blur everything).
- Canvas: `image.imageSize {width,height,resample}`, `image.canvasSize {width,height,anchor}`, `image.crop {x,y,width,height}`, `image.imageRotation.90cw`.
- Selection: `select.all`, `select.deselect`, `select.inverse`, `select.colorRange`.
- Undo: `edit.undo` returns `true`.
- Colours: `tools.setColors {foreground,background}`.

### Verify numerically, then visually
- `document.pixel {x,y}` returns `[r,g,b,a]` floats 0..1 of the COMPOSITE (e.g. `#203060` = `[0.1255,0.1882,0.3765,1]`). This is the best assertion for any edit; use it before trusting a render.
- `doc_inspect` shows layers (kind, bounds, blend, opacity), selection, and history names.
- `doc_render_preview {max_side:800}` for a picture.

## Gotchas
- A leftover selection CLIPS later paint/fill/filters to it; `select.deselect` first. (A stroke outside a stale ellipse selection was cut off.)
- Out-of-range params are silently CLAMPED, not rejected (blur radius 5000 ran as 1000). Read the range in `commands --json` `params`.
- Layer-less file formats flatten: after `doc_save` to png, the layers are not in the file.
- `command_list` without a filter is huge; always pass `filter`.
- Both MCP entries expose the same tool names; keep only one enabled.
- `mcp.json` holds live API tokens in plaintext (context7, figma, github). Never print them; rotate if leaked.

## Smoke test (headless MCP, ~2 minutes)
1. `session_list` (empty), `doc_new {width:800,height:600,background:"#203060"}`.
2. `command_batch`: new layer, `select.rect`, `edit.fill #ff0000`, `document.pixel` inside and outside the box; include one bogus id to confirm the error path.
3. `doc_inspect`, `doc_render_preview`.
4. `edit.undo` then `document.pixel` to confirm revert.
5. Copy a PNG into the `in` root, `doc_open {path:"x.png"}`, edit, `doc_save {path:"y.png"}`, check the file in the `out` root.
6. `doc_save {path:"/etc/x.png"}` must fail (absolute path rejected).
7. `command_run {id:"filter.blur.gaussianBlur",params:{radius:30},wait:false}` then `jobs_list` until done.
8. `doc_close`; `session_list` empty. Remove any files you put in the roots.
