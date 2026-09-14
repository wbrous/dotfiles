---
name: linux-manual-app-bundle-install
description: "Use when installing a downloaded manual/portable app bundle on Linux that ships bin/lib/share dirs (no installer script) with a .desktop file whose Exec path already hardcodes a specific /usr/lib/vendor/app location — e.g. REV Hardware Client, or similar vendor-shipped tarballs from FTC/FRC robotics tooling and other GTK apps. Covers reading the .desktop file's Exec/Icon fields to determine the exact required install path, copying the whole bundle there, symlinking the binary into /usr/local/bin, and installing the desktop file + all hicolor icon sizes to system locations so the app shows up in the launcher."
---

## Symptom
User downloads a tarball like `rev-hardware-client-1.4.2-linux-amd64/rev-hardware-client-1.4.2/` containing:
```
bin/<app-binary>
lib/app/, lib/runtime/
share/applications/<reverse-dns>.desktop
share/icons/hicolor/<size>/apps/<icon-name>.png
```
No install.sh. Just "install this thingy".

## Key insight
The bundled `.desktop` file's `Exec=` line already hardcodes the path the binary MUST live at (e.g. `/usr/lib/rev-robotics/rev-hardware-client/bin/rev-hardware-client`). Read that file first — it tells you exactly where to copy the whole bundle, so paths aren't invented by hand.

## Steps
1. Read `share/applications/*.desktop` to get `Exec=` (target path) and `Icon=` (icon name).
2. `sudo mkdir -p` the parent dir implied by Exec (e.g. `/usr/lib/<vendor>/`), then `sudo cp -r` the entire extracted bundle dir there so bin/lib/share sit together exactly as shipped (Exec path must resolve).
3. `sudo ln -sf <installed>/bin/<binary> /usr/local/bin/<binary>` for CLI convenience.
4. `sudo cp` the `.desktop` file to `/usr/share/applications/`.
5. `sudo cp -r share/icons/hicolor /usr/share/icons/` (copies all sizes at once — icon dirs mirror this structure, no need to loop per-size manually).
6. `sudo update-desktop-database /usr/share/applications` and `sudo gtk-update-icon-cache -f /usr/share/icons/hicolor` (both may silently no-op on some distros; ignore errors, harmless).
7. Verify: `ls -la` the installed binary dir, and `cat` the installed .desktop to confirm Exec still resolves.

## Gotchas
- Multiple sudo invocations each trigger a fresh fingerprint (fprintd) prompt on this machine when run as separate `bash` calls — batch related sudo commands into one shell invocation with `&&`/newlines to minimize prompts, but each sudo call inside still needs the ticket to still be valid (fprintd auth typically caches for a short sudo session, so back-to-back commands in the same script usually only prompt once).
- Don't skip icon sizes — the shipped bundle usually has a `hicolor/<size>/apps/<name>.png` for many sizes (16 up to 1024); copy the whole `hicolor` tree in one `cp -r` rather than looping/reinventing paths.
