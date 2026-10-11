---
name: photocraft
description: "Use for ANY PhotoCraft image-editor task: photocraft-cli (run/convert/info/batch/serve), the PhotoCraft MCP (xd://mcp__photocraft_*), driving-mode GUI launcher (photocraft-launch-or-focus, SUPER+SHIFT+ALT+P, port 47600), mcp.json bridge/headless config, command ids/recipes, save/write-root errors."
---

# PhotoCraft (v0.6.0): CLI, MCP, launcher, recipes

PhotoCraft is a Photoshop-like editor. ONE registry of ~851 engine commands (e.g. `layer.new.layer`, `filter.blur.gaussianBlur`) is driven identically by the GUI, `photocraft-cli`, a JSON control channel, and the MCP server. Learn the command ids once; every surface uses them.

## Pick the surface

| Goal | Use |
|---|---|
| One-shot edit/convert of files, scripting | `photocraft-cli run/convert/info/batch` (no MCP, no GUI, no roots needed) |
| Drive the live GUI, see it, screenshot it (`ui_*`) | MCP **bridge** (the DEFAULT enabled entry). Needs the GUI running in driving mode |
| Headless edits with no window | MCP headless entry (`PhotoCraft`, disabled by default) |

NEVER run `photocraft --help` (or any unknown flag): the GUI binary opens a window and treats `--help` as a file. Help is `photocraft-cli --help`.

## Driving-mode GUI launcher (the way to start the GUI)

`~/.local/bin/photocraft-launch-or-focus`, used by BOTH the `.desktop` entry (`~/.local/share/applications/ai.storyteller.photocraft.desktop`, `Exec=` and `TryExec=`) and the Hyprland binding `SUPER+SHIFT+ALT+P` (`~/.config/hypr/apps/photocraft.lua`, required from `hyprland.lua`). It starts at most ONE GUI:

| State | Behaviour |
|---|---|
| Nothing running | `setsid env WINIT_X11_SCALE_FACTOR=1.5 uwsm-app -- photocraft --control 47600 --control-token-file ~/.config/photocraft/control-token --automation-read-root ~/Pictures/photocraft-agent/in --automation-write-root ~/Pictures/photocraft-agent/out "$@"` |
| GUI running WITH `--control 47600` | focus its window, exit 0 (waits up to 10s for the port if it is still starting) |
| GUI running WITHOUT `--control` | focus it, notify + stderr warning, exit 1. A live process cannot be switched into driving mode; close it (save first) and relaunch |

It decides "driving mode" by reading `--control 47600` from `/proc/<pid>/cmdline`, NOT by the port alone: the GUI takes ~1s to bind, so a port-only check gave a false "no driving mode" warning on a quick double launch. Focus uses `omarchy-launch-or-focus '^ai\.storyteller\.photocraft$' true` (anchored on the full window class, since the helper also matches window TITLES with word boundaries and would otherwise grab a browser tab titled "photocraft"). The scale fix `WINIT_X11_SCALE_FACTOR=1.5` lives in the script now (XWayland doubled with the 1.25 monitor scale).

Limitation: file args (`%F`, files opened from the file manager) are NOT forwarded to a running GUI; the script prints that it ignored them. Open files with the MCP `doc_open` instead (read root only), or relaunch.

Window class is `ai.storyteller.photocraft` (XWayland). Pid check: `pgrep -x photocraft` (exact name, excludes `photocraft-cli`). Beware `pgrep -a` output: the pgrep subshell can show up as a phantom pid; confirm with `ps -o lstart,args -p <pid>`.

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

Both entries register the SAME tool names, so exactly one is enabled. Editing args or `enabled` needs an omp restart/MCP reload.

- `PhotoCraft-Bridge` (**enabled**, `timeout: 120000`): `photocraft-cli mcp --bridge 127.0.0.1:47600 --control-token-file ~/.config/photocraft/control-token`. Every tool forwards to the running GUI. Fails with `cannot connect` until the GUI is up (launch it with `SUPER+SHIFT+ALT+P` / the launcher / the .desktop entry).
- `PhotoCraft` (headless, **disabled**, `timeout: 120000`): `photocraft-cli mcp --automation-read-root ~/Pictures/photocraft-agent/in --automation-write-root ~/Pictures/photocraft-agent/out`. Use it (flip the two `enabled` flags) when the GUI is not wanted.

Token file: 64 hex chars, mode 600 (`~/.config/photocraft/control-token`). The GUI creates it if missing and reuses it otherwise. Never pass `--control-token` and the file together. Never print the token.

### Roots, bridge vs headless
In bridge mode the automation roots belong to the GUI PROCESS (the launcher passes them), NOT to `photocraft-cli mcp --bridge`; in headless mode they are flags on `photocraft-cli mcp`. Either way `doc_open`/`doc_save`/`doc_export` take RELATIVE forward-slash paths under the roots (bridge: `app.open`/`app.save`); absolute paths and `../` are always rejected. Without roots: `write authority is absent`. The read and write roots are separate: you cannot save into the read root. To open a file, copy it into `in/` first; results land in `out/`.

### Bridge-mode behaviour (VERIFIED against a real GUI)
- `session_list` and `ui_inspect` both return the full `ui.inspect` UI state in bridge mode; `doc_select`/`doc_close` are headless-only; `ui_*`, `control_call` are bridge-only.
- `doc_render_preview` is a window screenshot and rejects `index`. `ui_screenshot` returns a PNG.
- Wrong token -> `authentication required`; nothing listening -> `cannot connect`. `photocraft-cli serve` is NOT a GUI (`unknown method ui.inspect`).
- A transport failure or 60s timeout drops the connection and says the operation MAY have completed: inspect before retrying an edit. On Wayland the GUI only drains requests on compositor frame callbacks, so an asleep display or fully occluded window makes every request time out while the app is healthy.

## MCP tools

Tools are `xd://mcp__photocraft_<name>`. Write JSON args to them; read the path for the schema, or write `{}` and the validation error prints it.

`session_list`, `doc_new {width,height,name,background,mode,depth}`, `doc_open {path}`, `doc_select {index}`, `doc_close`, `doc_save {path,format,quality,tiffLayers}`, `doc_export`, `doc_inspect`, `doc_render_preview {max_side}` (returns a PNG image; use it for visual proof), `command_list {filter,enabled_only}`, `command_run {id,params,wait}`, `command_batch {steps:[{id,params,wait}],stop_on_error}`, `jobs_list`, `jobs_cancel`, bridge-only: `ui_inspect`, `ui_screenshot`, `ui_pointer {events}`, `ui_menu_invoke {id}`, `ui_set {fields}` (e.g. `{zoom:1}`), `control_call {method,params}`.

Prefer `command_batch` for edits (one history step per command, one round trip). It stops at the first error unless `stop_on_error:false`; unknown ids give `unknown command`. `wait:false` on a slow command returns `{job:id}`; poll `jobs_list` until `state:"done"`, and do not edit that document meanwhile. Job results show internal document/layer ids, not list positions.

## Recipes (all verified)

Layer ids are NOT 0-based: Background is 2, the first new layer is 3. Each creating command returns `{layer:id}`; use that id.

- New layer: `layer.new.layer {name}`
- Filled rectangle/ellipse: `select.rect {x,y,width,height,ellipse?:true}` then `edit.fill {contents:"color",color:"#rrggbb"}` (fills the selection on the active layer). Then `select.deselect`.
- Brush stroke: `paint.stroke {points:[[x,y],...],size,color,hardness}`
- Text: `type.create {x,y,text,size,color,name}` (x,y is the baseline anchor; returns `{layer,bounds}`); paragraph text uses `box:[x,y,w,h]`.
- Gradient fill layer: `layer.newFillLayer.gradient {from,to,angle,style:"linear"}`. Angle 0: `from` on the LEFT, `to` on the RIGHT. Angle 90: `to` at the TOP, `from` at the bottom.
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
- `doc_render_preview {max_side:800}` / `ui_screenshot` for a picture.

## Gotchas
- A leftover selection CLIPS later paint/fill/filters to it; `select.deselect` first. (A stroke outside a stale ellipse selection was cut off.)
- Out-of-range params are silently CLAMPED, not rejected (blur radius 5000 ran as 1000). Read the range in `commands --json` `params`.
- Layer-less file formats flatten: after `doc_save` to png, the layers are not in the file.
- `command_list` without a filter is huge; always pass `filter`.
- The bridge works on the user's REAL open GUI document: do not `doc_close`/edit their work to test. Use a new document, and remove test files from the roots after.
- Starting a driving-mode GUI needs any plain PhotoCraft closed first. Never kill the user's open GUI to test; ask (it may hold unsaved work).
- Tests that `pkill -x photocraft` race with launcher tests; do not interleave them.
- `mcp.json` holds live API tokens in plaintext (context7, figma, github). Never print them; rotate if leaked.

## Smoke test (bridge, ~2 minutes; headless is the same minus `ui_*`)
1. `ss -ltn 'sport = :47600'` shows a listener; else run `photocraft-launch-or-focus`.
2. `session_list` / `ui_inspect` succeed. `doc_new {width:800,height:600,background:"#203060"}`.
3. `command_batch`: new layer, `select.rect`, `edit.fill #ff0000`, `document.pixel` inside and outside the box; include one bogus id to confirm the error path.
4. `doc_inspect`, `ui_screenshot`; `edit.undo` then `document.pixel` to confirm revert.
5. Copy a PNG into the `in` root, `doc_open {path:"x.png"}`, edit, `doc_save {path:"y.png"}`, check the file in the `out` root.
6. `doc_save {path:"/etc/x.png"}` must fail (absolute path rejected).
7. Run the launcher again: it must exit 0 and `pgrep -x photocraft | wc -l` must stay 1.
8. Close only the document you created; remove any files you put in the roots.
