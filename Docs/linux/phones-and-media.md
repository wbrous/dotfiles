# Phones and Media on Linux

Covers iPhone (photos, voice memos), Android via scrcpy, lossless music purchases, and audio transcription.

## Mount iPhone photos (ifuse)

**Symptom:** Plugged-in iPhone not browsable; `ifuse` missing on Arch/Omarchy.

**Cause:** `libimobiledevice`/`usbmuxd` are usually present, but `ifuse` often is not. Only Apple's media partition (AFC) is exposed — never app data or the full filesystem.

**Fix:**
```sh
lsusb | grep -i apple
systemctl is-active usbmuxd
idevice_id -l            # lists UDID if visible
idevicepair validate     # if not validated:
idevicepair pair         # tap "Trust" on the phone (unlock it first)
which ifuse || sudo pacman -S --needed --noconfirm ifuse
mkdir -p ~/iPhone && ifuse ~/iPhone
mount | grep ifuse && ls ~/iPhone   # photos/videos in ~/iPhone/DCIM
fusermount -u ~/iPhone   # unmount
```
No sudo needed for the mount itself, only for installing ifuse.

_Migrated from: arch-iphone-mount-ifuse_

## iPhone Voice Memos via local backup

**Symptom:** `ifuse` mount shows no recordings; no `Recordings/` dir, `VoiceMemos.plist` is an empty dict, `ifuse --documents com.apple.VoiceMemos` fails with `InstallationLookupFailed`.

**Cause:** AFC never exposes Voice Memos. Files-app browsing is the same as a backup — use `idevicebackup2` directly instead of searching the mount (whole-mount `find` is very slow, timed out at 120s).

**Fix:**
```sh
idevicepair validate
ideviceinfo -q com.apple.mobile.backup   # RequiresEncryption: 0 means no password needed
df -h ~                                  # backup is GBs; ~114k files, ~17 min on iOS 27
mkdir -p ~/iphone-backup && idevicebackup2 backup ~/iphone-backup  # background, timeout 3600
```
Backup lands in `~/iphone-backup/<UDID>/`, files stored as `<fileID[:2]>/<fileID>`; map via `Manifest.db` (sqlite, `Files` table: fileID, domain, relativePath). Voice memos live in domain `AppDomainGroup-group.com.apple.VoiceMemos.shared`, relativePath `Recordings/<YYYYMMDD HHMMSS>.qta` (iOS 18+ `.qta` QuickTime Audio; older `.m4a`). `Recordings/CloudRecordings.db` table `ZCLOUDRECORDING` (`ZCUSTOMLABEL`, `ZPATH`, `ZDURATION`, `ZDATE`) lists them; `.waveform` files are display-only, skip. Copy each by hash to `~/VoiceMemos/` under its real basename (python sqlite3 + shutil.copy2), verify with `ffprobe -show_entries format=duration`. `.qta` plays in mpv/VLC; convert with ffmpeg to `.m4a` if needed. Backup is unencrypted and contains messages/app data — offer `rm -rf ~/iphone-backup` after user confirms playback.

_Migrated from: arch-iphone-voice-memos-from-backup_

## Transcribe long audio with voxtype

**Symptom:** Need transcripts of long `.qta`/`.m4a` voice memos or lectures on Linux.

**Fix:** `voxtype transcribe` only accepts 16 kHz mono WAV — convert first (~1s per 30 min):
```sh
ffmpeg -nostdin -v error -y -i in.qta -vn -ar 16000 -ac 1 -c:a pcm_s16le out.wav
voxtype transcribe out.wav
```
Stdout mixes log/header lines with the transcript (`Loading audio file`, `Audio format`, `Processing`, ISO-timestamp `INFO` lines). Strip them:
```sh
voxtype transcribe f.wav 2>/dev/null | grep -v -E '^(Loading audio|Audio format|Processing|20[0-9]{2}-[0-9]{2}-[0-9]{2}T|$)' > f.txt
```
`voxtype config` and `voxtype info models` show config/models; default is Whisper `small.en`, `--model`/`--engine` override (medium/large-v3-turbo need downloading).

**Performance:** One run uses ~4 cores (~4x user vs real), ~6x realtime with small.en (30 min audio ≈ 5.5 min) on a 24-core box. Run multiple files in parallel as separate background processes, not sequentially; kill the old sequential job first or two processes write the same output file. Check strays with `pgrep -af 'voxtype transcribe'`.

**Quality check:** Whisper small.en on noisy multi-speaker audio can fall into repetition loops (one sentence repeated 40–90x). Detect:
```sh
tr '.?!' '\n\n\n' < f.txt | sed 's/^ *//' | grep -v '^$' | sort | uniq -c | sort -rn | head
```
If a sentence repeats dozens of times those stretches are lost; offer a re-run with a larger model (medium.en / large-v3-turbo, ~2–3x slower) rather than presenting the transcript as reliable.

_Migrated from: voxtype-transcribe-long-audio-files_

## Android view/control with scrcpy (USB and Wi-Fi)

**Symptom:** Want to view/control an Android device (e.g. Samsung A16/SM-A166U) from Linux.

**Fix:**
```sh
sudo pacman -S scrcpy   # pulls in adb
adb devices
scrcpy -s <serial>      # -s only needed with multiple devices
```
Wireless (phone on USB, same Wi-Fi as computer):
```sh
adb tcpip 5555
adb shell ip route      # phone's IP, e.g. 172.20.10.4 (look for src)
adb connect <ip>:5555
scrcpy -s <ip>:5555     # cable can then be unplugged; persists until reboot/USB-debug reset
```

**Cause/Fix for `protocol fault (couldn't read status)` / exit 1:** The adb daemon was restarted (e.g. `adb devices` auto-restarting a stopped daemon) after the tcpip connection was established, silently dropping the wireless device even though the phone still listens. Just reconnect — no need to redo `adb tcpip`:
```sh
adb connect <ip>:5555
adb devices -l
scrcpy -s <ip>:5555
```
USB serial and `<ip>:5555` showing simultaneously in `adb devices` is expected, not a conflict. Exit code 0 on window close is normal (user closed it).

_Migrated from: scrcpy-android-usb-and-wifi-control_

## Buy lossless ALAC/FLAC on Hyperion Records

**Symptom:** On hyperion-records.co.uk track/album pages (`dw.asp?dc=...`), only MP3 buy buttons show even though the page says "Studio Master FLAC & ALAC downloads available".

**Cause:** The buy buttons follow a format selector that defaults to MP3.

**Fix:** Click the small format dropdown labeled **"MP3"** (top-right of nav bar) → submenu **"FLAC downloads"** / **"ALAC downloads"** / **"CD / LP only"** → page re-renders with e.g. `Download all ALAC 16-bit 44.1 kHz £X.XX` and `Download all ALAC 24-bit 96 kHz £X.XX` (Studio Master, ~£0.40 more for a single track, recorded that way not upsampled). Clicking adds to basket via AJAX silently — confirm via nav basket icon changing from "(No items)" to "1 item", then basket icon → **"Checkout ..."** (`/Member/Welcome.aspx`), sign in, pay, download. Basket page: `/Anon/Basket.aspx`. Same for whole-album "View whole album" / "Download all" buttons.

_Migrated from: hyperion-records-alac-purchase-flow_
