---
name: arch-iphone-voice-memos-from-backup
description: "Extract iPhone Voice Memos on Linux when ifuse mount shows no recordings; use idevicebackup2 + Manifest.db, .qta files."
---

# iPhone voice memos via local backup (Linux)

## Why
`ifuse` (AFC media partition) NEVER exposes Voice Memos: no `Recordings/` dir, `VoiceMemos.plist` is an empty dict, MediaLibrary has 0 voice rows, and `ifuse --documents com.apple.VoiceMemos` fails with InstallationLookupFailed (no UIFileSharingEnabled). Do not keep searching the mount. Files app / "pretend to be a Mac" = same thing as a backup: use `idevicebackup2`.

## Steps
1. Prereqs: device paired (`idevicepair validate`), `idevicebackup2` present (libimobiledevice). Check `ideviceinfo -q com.apple.mobile.backup` -> `RequiresEncryption: 0` means no password needed. Check `df -h ~` (backup was ~GBs; 114k files, ~17 min on iOS 27).
2. Run in background (async, timeout 3600): `mkdir -p ~/iphone-backup && idevicebackup2 backup ~/iphone-backup`. User may need to tap Trust / enter passcode on phone.
3. Backup lands in `~/iphone-backup/<UDID>/`. Files are stored as `<fileID[:2]>/<fileID>`; map via `Manifest.db` (sqlite, `Files` table: fileID, domain, relativePath).
4. Voice memos domain: `AppDomainGroup-group.com.apple.VoiceMemos.shared`, relativePath `Recordings/<YYYYMMDD HHMMSS>.qta` (iOS 18+ uses `.qta` QuickTime Audio; older = `.m4a`). Also `Recordings/CloudRecordings.db` (table ZCLOUDRECORDING: ZCUSTOMLABEL, ZPATH, ZDURATION, ZDATE). `.waveform` files are display-only; skip.
5. Copy each by hash to `~/VoiceMemos/` under its real basename (python sqlite3 + shutil.copy2). Verify with `ffprobe -show_entries format=duration`. `.qta` plays in mpv/VLC; convert with ffmpeg to .m4a if needed.
6. Cleanup: backup is unencrypted and contains messages/app data; offer `rm -rf ~/iphone-backup` after user confirms playback. Unmount ifuse with `fusermount -u ~/iPhone`.

## Gotchas
- Big `find` over the ifuse mount is very slow (timed out at 120s); avoid whole-mount censuses.
- Recount rows from the query before reporting totals.

See also skill arch-iphone-mount-ifuse for mounting photos/DCIM.
