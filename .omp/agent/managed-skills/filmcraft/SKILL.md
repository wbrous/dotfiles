---
name: filmcraft
description: "Use for ANY FilmCraft video-editor task: filmcraft-cli (exec/run/inspect/export/render/probe), the FilmCraft MCP (xd://mcp__filmcraft_*), driving-mode GUI launcher (filmcraft-launch-or-focus, SUPER+SHIFT+ALT+F, port 47601), mcp.json bridge/headless config, timeline command ids/recipes, ticks/frame-snapping, no-auth/no-sandbox caveats. Sibling of the photocraft skill."
---

# FilmCraft (v0.6.0): CLI, MCP, launcher, recipes

FilmCraft is a Premiere-style video editor from the same maker as PhotoCraft (`photocraft` skill). ONE registry of 650+ engine commands (`timeline.razor`, `effects.apply`, `file.exportMedia`, ...) is driven identically by the GUI, `filmcraft-cli`, a JSON-lines control channel, and the MCP server. Same architecture as PhotoCraft, but the surface DIFFERS in the ways below. Do not copy PhotoCraft habits blindly.

## FilmCraft vs PhotoCraft (verified on 0.6.0; the docs and binaries agree)

| | PhotoCraft | FilmCraft |
|---|---|---|
| Control port | 47600 | **47601** |
| Auth | 64-hex token file (`--control-token-file`) | **NONE.** `--control` takes only a port |
| File sandbox | `--automation-read-root/--automation-write-root` | **NONE.** `filmcraft-cli mcp --automation-read-root` is an `unknown mcp option`. Absolute paths work anywhere the user can write |
| Display | XWayland, needs `WINIT_X11_SCALE_FACTOR=1.5` | **Native Wayland**, scales correctly alone (`pixelsPerPoint 1.25`). NO scale workaround |
| CLI shape | `run --cmd/--params`, `convert`, `info` | `exec <id> k=v`, `run script.jsonl`, `inspect`, `export`, `render`, `probe` |
| Window class | `ai.storyteller.photocraft` | `ai.storyteller.filmcraft` |
| Time | pixels | **ticks: 254016000000 per second** (commands also take `seconds=`, `frame=`, `timecode=`) |
| MCP tools | `session_list`, `doc_*`, `ui_pointer`, `ui_set` | `project_inspect`, `sequence_inspect`, `media_import`, `render_frame`, `ui_elements`, `ui_click`, `ui_drag`, `ui_key`, `ui_type`, `ui_control` (NO `session_list`/`doc_new`/`doc_save`) |
| Launch keybind | `SUPER+SHIFT+ALT+P` | `SUPER+SHIFT+ALT+F` |

**Security consequence:** the control port is unauthenticated, loopback only. ANY local process can drive the app (and, via commands, read/write files as the user). The only protection is the `127.0.0.1` bind. The docs say "only enable it while you use it". The launcher leaves it on for the GUI's whole life; close FilmCraft when not editing.

## Pick the surface

| Goal | Use |
|---|---|
| One-shot headless edit/export/render, scripting | `filmcraft-cli` (no GUI, no MCP) |
| Drive the live GUI, see it, screenshot it (`ui_*`) | MCP **bridge** (`FilmCraft-Bridge`, the enabled entry). Needs the GUI in driving mode |
| Headless MCP edits, no window | `FilmCraft` entry (`--demo`, disabled by default) |

## Driving-mode GUI launcher

`~/.local/bin/filmcraft-launch-or-focus`, used by BOTH the `.desktop` override (`~/.local/share/applications/ai.storyteller.filmcraft.desktop`, `Exec=`+`TryExec=`) and the Hyprland binding `SUPER+SHIFT+ALT+F` (`~/.config/hypr/apps/filmcraft.lua`, required from `hyprland.lua`). Starts at most ONE GUI:

| State | Behaviour |
|---|---|
| Nothing running | `exec setsid uwsm-app -- filmcraft --control 47601 "$@"` |
| GUI running WITH `--control 47601` | focus it, exit 0 (waits up to 15s for the port if still starting; ~2s normally) |
| GUI running WITHOUT `--control` | focus it, notify + stderr warning, exit 1. A live process cannot be switched into driving mode; close it (save first) and relaunch |

**The single-instance guard is load-bearing here.** A second `filmcraft --control 47601` when the port is taken does NOT exit: it logs `control server failed to bind ... Address already in use` and keeps running as a duplicate window with no control channel (verified: it only ended because of a `timeout`). So never start a second GUI to "test" something.

"Driving mode" is decided by reading `--control 47601` from `/proc/<pid>/cmdline`, NOT by the port alone, because the port opens ~2s after launch and a port-only check mislabels a still-starting driving GUI as plain. Focus uses `omarchy-launch-or-focus '^ai\.storyteller\.filmcraft$' true`, anchored: the helper also matches window TITLES, and a browser tab titled "...storytold/filmcraft..." would otherwise be focused.

File args (`%F`) are NOT forwarded to a running GUI; the script says so. Use MCP `media_import {paths:[...]}` (absolute paths) or `command_run file.open`. Process check: `pgrep -x filmcraft` (excludes `filmcraft-cli`).

State lives in `~/.local/share/filmcraft/` (`Logs/`, `Recovery/`); override with `--data-dir` / `FILMCRAFT_DATA_DIR`. `FILMCRAFT_CONTROL_PORT=N` is the env equivalent of `--control N`.

### Recovery prompts (a side effect to avoid)
FilmCraft keeps a crash-recovery journal in `Recovery/<started>-<pid>/` (snapshot every ~5s while edits arrive). A GUI that is `pkill`ed, or ended with the control channel's `app.quit`, leaves a journal, and the NEXT launch asks "Recover unsaved changes?". After testing with a throwaway/demo project, either quit normally (File > Quit, answer Don't Save) or delete only the journals YOU created. Run test GUIs with `--data-dir $(mktemp -d)` so they cannot touch the real data dir. `--recover` / `--no-recover` control the prompt.

## filmcraft-cli

Options go anywhere. Output is JSON. Exit: 0 ok, 1 command failed, 2 usage error.
- `commands [filter] [--json]`; `describe <id>` (menu, shortcut, params, `enabled`). `enabled:false` reflects the current SELECTION; a command with explicit params (`timeline.razor seconds=3.5`) still runs.
- `exec <id> key=value ...` or `exec <id> '<json>'`. Values parse as JSON when they can (`3.5`, `true`, `[1,2]`), else strings; dotted keys nest.
- `run <script.jsonl | ->`: one `{"id","params"}` per line, `#` comments; stops at first failure unless `--keep-going`.
- `inspect [project|sequence] [--compact]`; `import <file>...`; `probe <media>`.
- `export <out> [--preset name] [--format f] [--start s --end s] [--scale f] [--quality n] [--no-audio] [--queue]`: format guessed from extension (h264 hevc prores dnxhr apv mjpeg mxf png tiff gif wav aiff aac). Waits for the job. `--list-presets [query]`.
- `render --seconds S --out f.png [--scale 0.5]`: one Program frame to PNG.
- Project selection: `--demo` (built-in demo, 642 frames at 23.976 fps), `--project p.fcproj`; persist with `--save` (back to `--project`) or `--save-as p.fcproj`. WITHOUT a save flag, headless edits are discarded.
- `--bridge 127.0.0.1:47601`: send commands to the running GUI instead of a headless engine.
- Examples (all verified): `filmcraft-cli --demo --save-as d.fcproj exec timeline.razor seconds=3.5` -> `{"cuts":3}`; `filmcraft-cli --demo render --seconds 1 --out f.png --scale 0.25` -> 480x270 PNG; `filmcraft-cli --demo export out.mp4 --start 0 --end 1 --scale 0.25` (0.3s).
- A saved project beside which headless sessions create a `FilmCraft Previews/` folder; delete it with the test dir.

## MCP config (`~/.omp/agent/mcp.json`)

Both FilmCraft entries register the SAME tool names, so enable exactly one. FilmCraft and PhotoCraft tool names do NOT collide (different prefixes `mcp__filmcraft_*` vs `mcp__photocraft_*`), so both apps can be enabled at once. Editing args/`enabled` needs an omp restart/MCP reload.
- `FilmCraft-Bridge` (**enabled**, `timeout:120000`): `filmcraft-cli mcp --bridge 127.0.0.1:47601`. No token. Fails with a connect error until the GUI is up.
- `FilmCraft` (headless, **disabled**): `filmcraft-cli mcp --demo`. Also accepts `--project p.fcproj` and `--data-dir DIR`; any other option exits 2.

## MCP tools

`xd://mcp__filmcraft_<name>`. Read the path for the schema (or write `{}` for the validation error). Strict args: an unknown argument is `-32602 unknown argument "filtr" for command_list; expected: enabled_only, filter` (not silently ignored).
Both modes: `command_list {filter,enabled_only}`, `command_run {id,params}`, `command_batch {steps:[{id,params}],stop_on_error}`, `doc_inspect`, `project_inspect`, `sequence_inspect`, `media_import {paths,bin?,image_sequence?}` (absolute paths), `render_frame {seconds}` / `render_preview` (PNG).
Bridge only (headless returns "this tool drives the live app"): `ui_inspect`, `ui_elements {prefix?}`, `ui_click {id|x,y}`, `ui_drag`, `ui_key {key}` (`Space`, `Cmd+K`), `ui_type`, `ui_screenshot {panel?}`, `ui_control {method,params}` (any control method: `ui.set`, `ui.scroll`, `ui.timeline.locate`...).
Loop: `project_inspect`/`sequence_inspect` -> ids -> `command_run` -> `render_frame`/`ui_screenshot` -> `edit.undo` if wrong. `command_batch` stops at the first error and reports `{completed,failed,results}`; unknown ids give `unknown command`.

## Recipes (verified through the bridge on the real GUI)

- Open the built-in demo: `command_run file.openDemoProject` -> `{"sequence":21}`.
- Playhead: `playhead.set {seconds:2}`. It SNAPS DOWN to the previous frame boundary: at 23.976 fps, 1s -> 0.9593s, 2s -> 1.9603s, 3.5s -> 3.4618s. Never assert on exact seconds; compare frames, or read back the returned `time` ticks.
- Razor cut: `timeline.razor {seconds:3.5}` -> `{"cuts":3}`; params in the registry are `{time:ticks, track:"V1"|id?, clip:id?}`.
- Undo: `edit.undo` -> `{"undone":"Razor"}`.
- Effects: `effects.apply {effect:"Gaussian Blur"}` (acts on the selection unless targets named).
- New bin: `file.newBin {name}`. Place a clip: `timeline.place {item,track:"V1",seconds,sourceIn,duration}` (`track` = picture, `audioTrack` = sound; an audio track as `track` places sound alone).
- Selection-dependent commands are `enabled:false` until something is selected UNLESS the call names targets (`clips`/`clip` for timeline clips, `items`/`item` for project items).
- Tracks may be a name (`"V1"`, `"A2"`) or id; a nonexistent track is an "invalid parameters" error, never a different track.
- Export: `command_run file.exportMedia {..., wait:true}` blocks until written, with MCP progress/cancel; without `wait` it returns `{job,path}`: poll `jobs.list`, stop with `jobs.cancel`.
- `sequence_inspect` returns `duration` in ticks, `durationFrames`, `playhead`, `markers`, `in`/`out`, track/clip data. fps = durationFrames / (duration/254016000000).

### Verify
- Numeric first: `sequence_inspect` / `inspect sequence` (cut counts, clip times); then `render_frame`/`ui_screenshot` for a picture.

## Gotchas
- NO auth, NO sandbox (see the table). A command given an absolute path writes there (`file.saveAs {path:"/tmp/x.fcproj"}` succeeded outside any "root").
- Headless MCP sessions start from an empty project or `--demo`; GUI edits are in the GUI's own project. They are separate worlds.
- The bridge drives the user's REAL open project. Do not edit/close their work to test; use a new project/sequence and undo, and never `app.quit` (it skips the save prompt and leaves a recovery journal).
- A hidden window or sleeping display makes `ui.screenshot` fail after 10s (Wayland only renders on frame callbacks); `ui.inspect` can time out too.
- At most 16 control connections; a malformed line (non-JSON, no `method`, >4 MiB) gets an error reply and the connection is CLOSED, so reconnect.
- Never run bare `filmcraft --help`-style probes on the GUI binary; use `filmcraft-cli --help`. Test GUIs get `--data-dir $(mktemp -d)`.
- Tests that `pkill -x filmcraft` race with launcher tests and orphan recovery journals; do not interleave them.

## Smoke test (bridge, ~2 minutes)
1. `ss -ltn 'sport = :47601'` shows a listener; else run `filmcraft-launch-or-focus`.
2. `ui_inspect` and `project_inspect` succeed.
3. `command_batch`: `playhead.set`, a bogus id (must report `unknown command`, `failed:1`), `playhead.set`.
4. `timeline.razor {seconds:3.5}` then `sequence_inspect`, then `edit.undo` (`undone: Razor`).
5. `render_frame {seconds:1}` and `ui_screenshot` return images.
6. Run the launcher again: exit 0, `pgrep -x filmcraft | wc -l` stays 1, one window of class `ai.storyteller.filmcraft`.
7. Undo any edits; do not `app.quit`.
