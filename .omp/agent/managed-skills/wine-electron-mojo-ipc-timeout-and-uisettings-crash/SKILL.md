---
name: wine-electron-mojo-ipc-timeout-and-uisettings-crash
description: "Use when a standalone Windows Electron .exe (unpacked, no installer) run under Wine or GE-Proton starts several child processes (gpu-process, utility/network, renderer) that are visible in ps but no window ever appears, and the process self-terminates cleanly ~15-17s after launch with no coredump/no signal. Also covers the related \"fixme:ui:uisettings2_get_TextScaleFactor stub!\" spam recursing into \"err:virtual:virtual_setup_exception stack overflow\" that kills the process much earlier (~1-2s)."
---

## Symptom 1: silent death ~15-17s after launch, no window ever shown
`ps aux` shows the main GeoGebra.exe/Electron.exe process plus short-lived
`--type=gpu-process`, `--type=utility --utility-sub-type=network.mojom.NetworkService`,
and later `--type=renderer` children — but no window ever maps
(`hyprctl clients` / `wmctrl` shows nothing), and after ~15-17s all
processes vanish with no coredump (`coredumpctl list` empty) and no SIGSEGV.

Root cause: the mojo IPC handshake between the Electron main process and its
sandboxed child processes never completes under **GE-Proton's staging wine
build**. Confirm by running with verbose Electron logging:
```
ELECTRON_ENABLE_LOGGING=1 wine app.exe --enable-logging=stderr --v=1 2>&1 | tail
```
Look for `[PID:.../...:INFO:content\child\child_thread_impl.cc:909] ChildThreadImpl::EnsureConnected()`
appearing exactly ~15s after the last prior log line — that 15s gap IS
Chromium's fixed child-process connection timeout (`kConnectionTimeoutS`).

Things that DON'T fix it: `--no-sandbox` (argv switch or
`app.commandLine.appendSwitch`), `--single-process` (actually makes it
*worse* — instant crash, don't use), `--disable-gpu`,
`--disable-gpu-shader-disk-cache`, clearing the Electron userData profile.

**Fix that works: use plain system `wine` instead of GE-Proton for this
class of app.** GE-Proton's wine-staging build breaks the named-pipe/mojo
handle inheritance for this Electron IPC pattern; a stock `wine` (e.g.
wine-11.15) completes the handshake fine and the window appears normally
with the full 4-process tree (main/gpu/network/renderer) staying alive.
GE-Proton is the right call for anti-cheat/DRM/proper-Windows-game
scenarios (see `wine-powrprof-stub-crash-fix`, `wine-webview2-*` skills) —
but for a bare unpacked Electron .exe with no such requirements, prefer
plain wine and only reach for GE-Proton if plain wine fails outright.

If unrecognized CLI switches passed to the .exe get silently swallowed or
misinterpreted as a "file to open" (check the app's own argv-parsing code,
e.g. Electron apps often have custom `main.js` logic that treats the last
unrecognized arg as a filename), you cannot pass Chromium switches via the
command line at all — add `app.commandLine.appendSwitch(...)` directly in
the app's own (unpacked, non-asar) `resources/app/main.js` near other
`app.commandLine.appendSwitch` calls instead.

## Symptom 2: stack overflow + death within ~1-2s of launch
Log shows thousands of repeated lines like:
```
0024:fixme:ui:uisettings2_get_TextScaleFactor iface XXXXXXXX, value XXXXXXXX stub!
```
ending in:
```
0024:fixme:ui:uisettings2_get_TextScaleFactor stack overflow 2752 bytes addr 0x... stack 0x...
```
This is a known Wine bug: `IUISettings2::get_TextScaleFactor` is an
unimplemented WinRT stub that Chromium's DPI-scale-factor query calls
repeatedly without properly unwinding, eventually overflowing the calling
thread's stack and killing the whole process.

Fix: disable the `windows.ui` WinRT component entirely so
`RoGetActivationFactory` fails cleanly instead of returning a
recursion-prone stub:
```
export WINEDLLOVERRIDES="windows.ui=d"
```
Set this in the launch script alongside `WINEPREFIX`. Confirm the fix by
grepping the run log for `TextScaleFactor` — count should drop to 0.

## Diagnosis workflow used
1. `coredumpctl list` — rule out real SIGSEGV/SIGABRT (empty = clean/self exit).
2. Track exact process lifecycle with unique cmdline matching (not raw PID —
   PIDs get reused within seconds on Linux, causing false "still alive"
   reads via `kill -0`):
   ```
   ps -eo cmd | grep -c "[G]eoGebra.exe"    # count, not PID
   hyprctl clients | grep -c "class: .*[Gg]eo[Gg]ebra"   # real window check
   ```
   Poll once per second in a loop to find the exact death/crash timing —
   the timing itself (15s vs 1-2s) is the key diagnostic signal pointing at
   which of the two bugs above is in play.
3. `ELECTRON_ENABLE_LOGGING=1 wine app.exe --enable-logging=stderr --v=1`
   for Chromium-side INFO/VERBOSE/ERROR lines with timestamps.
4. `WINEDEBUG=err+all,warn+all,fixme+all` for wine-side stub/fixme spam —
   watch for tight per-thread retry loops (e.g. `ReplaceFileW Ignoring
   flags 2` repeated hundreds of times from one thread ID) as a secondary
   symptom of a stuck IO thread, separate from the two root causes above.
