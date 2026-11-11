# FilmCraft and PhotoCraft editors: CLI, MCP, launcher, recipes

Scope: driving the FilmCraft video editor and PhotoCraft image editor via CLI, MCP, and the driving-mode GUI launcher. Same engine-command architecture, different surfaces — do not copy habits between them.

## FilmCraft vs PhotoCraft (verified on 0.6.0)

| | PhotoCraft | FilmCraft |
|---|---|---|
| Control port | 47600 | **47601** |
| Auth | 64-hex token file (`--control-token-file`) | **NONE.** `--control` takes only a port |
| File sandbox | `--automation-read-root` / `--automation-write-root` | **NONE.** Absolute paths work anywhere the user can write |
| Display | XWayland, needs `WINIT_X11_SCALE_FACTOR=1.5` | **Native Wayland**, scales correctly alone (`pixelsPerPoint` 1.25), no workaround |
| CLI shape | `run --cmd/--params`, `convert`, `info` | `exec <id> k=v`, `run script.jsonl`, `inspect`, `export`, `render`, `probe` |
| Window class | `ai.storyteller.photocraft` | `ai.storyteller.filmcraft` |
| Time | pixels | **ticks: 254016000000 per second** (commands also take `seconds=`/`frame=`/`timecode=`) |
| MCP tools | `session_list`, `doc_*`, `ui_pointer`, `ui_set` | `project_inspect`, `sequence_inspect`, `media_import`, `render_frame`, `render_frame`, `ui_elements`, `ui_click`, `ui_drag`, `ui_key`, `ui_type`, `ui_control` (no `session_list`/`doc_new`/`doc_save`) |
| Launch keybind | `SUPER+SHIFT+ALT+P` | `SUPER+SHIFT+ALT+F` |

**Security:** FilmCraft's control port is unauthenticated, loopback-only. ANY local process can drive the app (and via commands read/write files as the user); the only protection is the `127.0.0.1` bind. "Only enable it while you use it" — the launcher leaves it on for the GUI's whole life; close FilmCraft when not editing.

## Pick the surface

| Goal | Use |
|---|---|
| One-shot headless edit/export/render, scripting | `filmcraft-cli` / `photocraft-cli` (no GUI, no MCP) |
| Drive the live GUI, see it, screenshot it (`ui_*`) | MCP **bridge** entry (enabled). Needs the GUI in driving mode |
| Headless MCP edits, no window | headless entry (`FilmCraft`/`PhotoCraft`, disabled by default) |

## Driving-mode GUI launchers

`~/.local/bin/filmcraft-launch-or-focus` (keybind `SUPER+SHIFT+ALT+F`, `.desktop` `~/.local/share/applications/ai.storyteller.filmcraft.desktop`, Hyprland `~/.config/hypr/apps/filmcraft.lua`) and `~/.local/bin/photocraft-launch-or-focus` (`SUPER+SHIFT+ALT+P`, analogous paths) each start at most ONE GUI:

| State | Behaviour |
|---|---|
| Nothing running | FilmCraft: `exec setsid uwsm-app -- filmcraft --control 47601 "$@"`. PhotoCraft: `setsid env WINIT_X11_SCALE_FACTOR=1.5 uwsm-app -- photocraft --control 47600 --control-token-file ~/.config/photocraft/control-token --automation-read-root ~/Pictures/photocraft-agent/in --automation-write-root ~/Pictures/photocraft-agent/out "$@"` |
| GUI running WITH `--control` | focus it, exit 0 (waits ~10–15s for the port if still starting) |
| GUI running WITHOUT `--control` | focus it, notify + stderr warning, exit 1 — a live process can't enter driving mode; close it (save first) and relaunch |

"Driving mode" is decided by reading `--control <port>` from `/proc/<pid>/cmdline`, NOT the port alone (bind lags launch by ~1–2s; a port-only check false-labels a starting GUI). Focus uses anchored `omarchy-launch-or-focus '^ai\.storyteller\.(film|photo)craft$' true` (the helper also matches window TITLES — a browser tab titled "...photocraft" would otherwise be grabbed). File args (`%F`) are NOT forwarded to a running GUI — use MCP `media_import`/`doc_open` instead. Process check: `pgrep -x filmcraft` / `pgrep -x photocraft` (excludes the `-cli` binaries). **Single-instance guard is load-bearing:** a second `filmcraft --control 47601` with the port taken does NOT exit — it logs `control server failed to bind ... Address already in use` and keeps running as a duplicate window with no channel. Never start a second GUI "to test". State lives in `~/.local/share/filmcraft/` (`Logs/`, `Recovery/`; override `--data-dir` / `FILMCRAFT_DATA_DIR`; `FILMCRAFT_CONTROL_PORT=N` ≡ `--control N`).

**Recovery-journal side effect:** FilmCraft keeps a crash-recovery journal in `Recovery/<started>-<pid>/` (snapshot ~every 5s while edits arrive). A `pkill`ed GUI or one ended via control-channel `app.quit` leaves a journal, and the NEXT launch asks "Recover unsaved changes?". After throwaway/demo testing, quit normally (File > Quit, Don't Save) or delete only the journals YOU created. Run test GUIs with `--data-dir $(mktemp -d)`. NEVER run `photocraft --help` (GUI binary opens a window, treats `--help` as a file) — help is `photocraft-cli --help`. Never `app.quit` the bridge (skips the save prompt, leaves a journal).

## filmcraft-cli

Options anywhere; output JSON; exit 0 ok / 1 command failed / 2 usage error. `commands [filter] [--json]`; `describe <id>` (`enabled:false` reflects current selection — an explicit-param call like `timeline.razor seconds=3.5` still runs); `exec <id> k=v...` or `exec <id> '<json>'` (values parse as JSON when possible, else strings; dotted keys nest); `run <script.jsonl | ->` (one `{"id","params"}` per line, `#` comments, stops at first failure unless `--keep-going`); `inspect [project|sequence] [--compact]`; `import <file>...`; `probe <media>`; `export <out> [--preset] [--format] [--start s --end s] [--scale f] [--quality n] [--no-audio] [--queue]` (format from extension: h264 hevc prores dnxhr apv mjpeg mxf png tiff gif wav aiff aac; waits for the job; `--list-presets [query]`); `render --seconds S --out f.png [--scale 0.5]` (one Program frame); `--demo` (built-in demo, 642 frames at 23.976 fps) or `--project p.fcproj`, persist with `--save`/`--save-as` (without a save flag headless edits are discarded); `--bridge 127.0.0.1:47601` sends commands to the running GUI. Verified: `filmcraft-cli --demo --save-as d.fcproj exec timeline.razor seconds=3.5` → `{"cuts":3}`; `--demo render --seconds 1 --out f.png --scale 0.25` → 480x270 PNG; `--demo export out.mp4 --start 0 --end 1 --scale 0.25` (~0.3s). Every saved `.fcproj` gets a sibling `FilmCraft Previews/` folder — delete it with test projects (render/export don't create it).

## photocraft-cli

- `run (<file> | --new '<json>') --cmd <id> [--params '<json>'] [--cmd ...] --out <file>`: each `--params` binds to the PRECEDING `--cmd`. `--new` takes `file.new` params (`width,height,background white|black|transparent|#rrggbb,mode,depth,resolution,name`).
- `info <file> --compact` (size, layers `[{name,kind,...}]`); `convert <in> <out> [--quality 1-100] [--tiff-layers]` (format by extension; PNG/JPG/WebP FLATTEN layers with a warning — save `.pcraft`/`.psd` to keep layers); `commands [--json] [--filter text]` (ALWAYS filter, full list ~125KB; `--json` `params` string documents keys/ranges/defaults — read before guessing); `batch --actions a.json --in dir --out dir` (`[[id,params],...]`; `--out` == `--in` refused unless `--in-place`); `droplet`, `serve` (JSON-lines server on stdio/`--port`; takes seconds to bind).
- A flag a subcommand doesn't take is an error. Exit is loud; read the message.

## MCP config (`~/.omp/agent/mcp.json`)

Both apps: the bridge and headless entries register the SAME tool names, so enable exactly one per app. Editing args/`enabled` needs an omp restart/MCP reload. FilmCraft and PhotoCraft are separate servers, tools prefixed per-server — both apps can be enabled at once.
- FilmCraft-Bridge (**enabled**, `timeout:120000`): `filmcraft-cli mcp --bridge 127.0.0.1:47601`. No token. Connect error until GUI is up.
- FilmCraft headless (**disabled**): `filmcraft-cli mcp --demo` (also `--project p.fcproj`, `--data-dir DIR`; any other option exits 2).
- PhotoCraft-Bridge (**enabled**, `timeout:120000`): `photocraft-cli mcp --bridge 127.0.0.1:47600 --control-token-file ~/.config/photocraft/control-token`. Forwards to the running GUI.
- PhotoCraft headless (**disabled**): `photocraft-cli mcp --automation-read-root ~/Pictures/photocraft-agent/in --automation-write-root ~/Pictures/photocraft-agent/out`.
- Token file: 64 hex chars, mode 600 (`~/.config/photocraft/control-token`); GUI creates/reuses it. Never pass `--control-token` and the file together; never print the token. `mcp.json` holds live API tokens in plaintext (context7, figma, github) — never print, rotate if leaked.

**Roots (PhotoCraft):** in bridge mode roots belong to the GUI PROCESS (launcher passes them), NOT to `photocraft-cli mcp --bridge`; in headless mode they're flags on `photocraft-cli mcp`. Either way `doc_open`/`doc_save`/`doc_export` take RELATIVE forward-slash paths under the roots (bridge: `app.open`/`app.save`); absolute paths and `../` always rejected; without roots: `write authority is absent`. Read and write roots are separate — can't save into the read root. Copy files into `in/` first; results land in `out/`. FilmCraft has NO sandbox — absolute paths write anywhere.

## MCP tools and recipes

Tools: `xd://mcp__filmcraft_<name>` / `xd://mcp__photocraft_<name>` — read the path for the schema (or write `{}` for the validation error). Strict args: unknown argument → `-32602` (not silently ignored). Loop: inspect → ids → `command_run` → `render_frame`/`ui_screenshot` → `edit.undo` if wrong. `command_batch` stops at first error unless `stop_on_error:false`, reports `{completed,failed,results}`; unknown ids → `unknown command`.

- FilmCraft both modes: `command_list {filter,enabled_only}`, `command_run {id,params}`, `command_batch {steps,stop_on_error}`, `doc_inspect`, `project_inspect`, `sequence_inspect`, `media_import {paths,bin?,image_sequence?}` (absolute paths), `render_frame {seconds}`/`render_preview` (PNG). Bridge only: `ui_inspect`, `ui_elements {prefix?}`, `ui_click {id|x,y}`, `ui_drag`, `ui_key {key}` (`Space`, `Cmd+K`), `ui_type`, `ui_screenshot {panel?}`, `ui_control {method,params}` (`ui.set`, `ui.scroll`, `ui.timeline.locate`, ...).
- PhotoCraft: `session_list`, `doc_new {width,height,name,background,mode,depth}`, `doc_open {path}`, `doc_select {index}`, `doc_close`, `doc_save {path,format,quality,tiffLayers}`, `doc_export`, `doc_inspect`, `doc_render_preview {max_side}` (PNG), `command_list {filter,enabled_only}`, `command_run {id,params,wait}`, `command_batch`, `jobs_list`, `jobs_cancel`, bridge-only `ui_inspect`, `ui_screenshot`, `ui_pointer {events}`, `ui_menu_invoke {id}`, `ui_set {fields}`, `control_call {method,params}`. Bridge quirks (VERIFIED): `session_list` and `ui_inspect` both return full UI state; `doc_select`/`doc_close` headless-only; `ui_*`/`control_call` bridge-only; `doc_render_preview` is a window screenshot, rejects `index`. `wait:false` on slow commands → `{job:id}`; poll `jobs_list` to `done`, don't edit that document meanwhile. Wrong token → `authentication required`; nothing listening → `cannot connect`. A transport failure/60s timeout drops the connection and says the op MAY have completed — inspect before retrying. On Wayland the GUI drains requests only on compositor frame callbacks, so an asleep display or fully occluded window times out every request while healthy.

**FilmCraft recipes (verified through the bridge):** open demo `command_run file.openDemoProject` → `{"sequence":21}`. Playhead `playhead.set {seconds:2}` SNAPS DOWN to the previous frame boundary (23.976fps: 1s→0.9593s, 2s→1.9603s, 3.5s→3.4618s) — never assert exact seconds; compare frames or read back `time` ticks. Razor `timeline.razor {seconds:3.5}` → `{"cuts":3}` (registry params `{time:ticks, track:"V1"|id?, clip:id?}`). Undo `edit.undo` → `{"undone":"Razor"}`. Effects `effects.apply {effect:"Gaussian Blur"}` (acts on selection unless targets named). New bin `file.newBin {name}`; place clip `timeline.place {item,track:"V1",seconds,sourceIn,duration}` (`track` = picture, `audioTrack` = sound). Selection-dependent commands are `enabled:false` until selected UNLESS targets named (`clips`/`clip` for timeline clips, `items`/`item` for project items). Tracks may be name (`"V1"`, `"A2"`) or id; nonexistent track = "invalid parameters", never a different track. Export `command_run file.exportMedia {..., wait:true}` blocks with progress/cancel; without `wait` returns `{job,path}` — poll `jobs.list`, stop with `jobs.cancel`. `sequence_inspect` → `duration` ticks, `durationFrames`, `playhead`, `markers`, `in`/`out`; fps = durationFrames / (duration/254016000000).

**PhotoCraft recipes (all verified):** layer ids are NOT 0-based (Background = 2, first new layer = 3; each creating command returns `{layer:id}`, use it). New layer `layer.new.layer {name}`; filled rect/ellipse `select.rect {x,y,width,height,ellipse?}` → `edit.fill {contents:"color",color:"#rrggbb"}` → `select.deselect`; stroke `paint.stroke {points:[[x,y],...],size,color,hardness}`; text `type.create {x,y,text,size,color,name}` (x,y = baseline anchor, returns `{layer,bounds}`; paragraph uses `box:[x,y,w,h]`); gradient fill `layer.newFillLayer.gradient {from,to,angle,style:"linear"}` (angle 0: `from` LEFT, `to` RIGHT; angle 90: `to` TOP, `from` bottom); solid fill `layer.newFillLayer.solidColor {color}`; adjustment layers `layer.newAdjustmentLayer.<hueSaturation|levels|curves|vibrance|brightnessContrast|...>` (same names under `image.adjustments.*` apply to pixels); props `layer.setProps {layer,opacity:0..1,blend,visible,name,locked}`, `layer.select {layer}`, `layer.translate {layer,dx,dy}`, `layer.arrange.bringToFront|sendToBack`; filters `filter.blur.gaussianBlur {radius}` (acts on SELECTED layer + current selection — `select.all` first to hit everything); canvas `image.imageSize {width,height,resample}`, `image.canvasSize {width,height,anchor}`, `image.crop {x,y,width,height}`, `image.imageRotation.90cw`; selection `select.all/deselect/inverse/colorRange`; undo `edit.undo` → `true`; colors `tools.setColors {foreground,background}`. Verify numerically first: `document.pixel {x,y}` returns `[r,g,b,a]` 0..1 of the COMPOSITE (`#203060` = `[0.1255,0.1882,0.3765,1]`) — best assertion for any edit; `doc_inspect` shows layers/selection/history; then `doc_render_preview {max_side:800}` / `ui_screenshot` for a picture.

**Shared gotchas:** the bridge drives the user's REAL open project/document — never edit/close their work to test; use a new project/sequence/document and undo; remove test files from roots after. Never kill the user's open GUI to test (may hold unsaved work); ask. `pkill -x <app>` tests race with launcher tests and orphan recovery journals — don't interleave. At most 16 FilmCraft control connections; a malformed line (non-JSON, no `method`, >4MiB) gets an error reply and the connection is CLOSED — reconnect. `command_list` without a filter is huge — always pass `filter`. PhotoCraft: a leftover selection CLIPS later paint/fill/filters — `select.deselect` first; out-of-range params are silently CLAMPED, not rejected (blur 5000 ran as 1000 — read ranges in `commands --json` `params`); hidden window/sleeping display makes `ui.screenshot` fail after 10s. Smoke tests (~2 min each) in source skills cover the full bridge loop (launcher re-run must exit 0 with process count staying 1; PhotoCraft `doc_save {path:"/etc/x.png"}` must fail on absolute path).

_Migrated from: filmcraft, photocraft_
