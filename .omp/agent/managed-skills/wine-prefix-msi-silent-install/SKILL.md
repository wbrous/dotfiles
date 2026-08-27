---
name: wine-prefix-msi-silent-install
description: "Use when creating a new Wine prefix in a project folder (e.g. .pfx) and silently installing an .msi into it on Arch Linux — covers installing wine/winetricks via pacman if missing, wineboot --init noise that is safe to ignore, msiexec /qn /l*v logging, and why the foreground msiexec call may hit the bash tool's timeout even though the install actually completed (verify via the log's \"Return value 1\" / no error lines and by checking installed files under drive_c/Program Files, not by the timed-out shell exit code)."
---

## Setup
```
sudo pacman -S --noconfirm wine winetricks   # if not installed; use hub PTY for fingerprint/sudo prompt
export WINEPREFIX="$(pwd)/.pfx"
export WINEARCH=win64
wineboot --init
```
`wineboot --init` prints lots of `err:ole:`, `fixme:`, `err:setupapi:do_file_copyW Unsupported style(s) 0x10` noise — this is normal Wine boilerplate, not a failure. Exit code 0 confirms prefix creation.

## Install MSI
```
msiexec /i "$(pwd)/App.msi" /qn /l*v "$(pwd)/install.log"
```
- Large MSIs (e.g. bundling Edge WebView runtime) can run past a 180s foreground bash-tool timeout. The bash tool reports "Command timed out" / "error: interrupted", but the underlying msiexec process frequently already finished — the timeout only kills the tool's wait, and by the time you check, only `wineserver`/`winedevice.exe` background processes remain (msiexec itself exits after the action completes).
- **Do not treat a foreground timeout as install failure.** Verify actual outcome:
  1. `pgrep -fa msiexec` — if empty, msiexec has exited.
  2. Tail `install.log`: look for `Action ended ...: INSTALL. Return value 1.` (success) with no `error:`/`Installation failed` lines nearby.
  3. `find "$WINEPREFIX/drive_c/Program Files"* -iname "*<app>*"` to confirm the expected binaries/uninstaller landed.

## Launch installed app
```
WINEPREFIX="$(pwd)/.pfx" wine "$(pwd)/.pfx/drive_c/Program Files/<App>/<App>.exe"
```
