---
name: zen-browser-clear-space-themes
description: Remove Zen Browser workspace (space) gradient themes while keeping the spaces; edit zen-sessions.jsonlz4 offline.
---

# Clear Zen space themes, keep spaces

Space (workspace) themes are NOT in places.sqlite or prefs. They live in `<profile>/zen-sessions.jsonlz4` (mozlz4: 8-byte magic `mozLz40\0` + lz4 block), under the top-level `spaces[]` array, each with a `theme` object.

## Procedure
1. Find the profile: `~/.config/zen/profiles.ini`; use the one in `installs.ini` (`Default=`), e.g. `xxxx.Default (release)`.
2. Zen MUST be closed (`pgrep -af zen-bin`). It rewrites the session file on shutdown and would overwrite edits. Re-check right before writing.
3. No `lz4` python module by default and `omni.ja` is not readable by unzip/zipfile; use `uv run --with lz4 python`.
4. Back up first: `cp -p zen-sessions.jsonlz4 /tmp/...pre-theme-removal`.
5. Decode, set every space's theme to Zen's own "no theme" value, re-encode with `lz4.block.compress(..., store_size=True)` (prefix the magic), read back to verify:
   `{"type":"gradient","gradientColors":[],"opacity":0.5,"texture":0}`
   (this is what `nsZenThemePicker.getTheme([])` gives a brand-new space; found by `strings omni.ja`).
6. Also patch `zen-sessions-backup/clean.jsonlz4` and `zen-sessions-backup/recovery.baklz4`, otherwise a restore brings the old gradients back. Dated hourly backups can be left alone.
7. Verify spaces keep name/icon/uuid/containerTabId and tab/folder/group counts unchanged.

## Notes
- Can't confirm visually unless Zen is launched; report that limit.
- Companion: `zen-browser-userchrome-theme-install` (Catppuccin userChrome/userContent install).
