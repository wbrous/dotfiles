---
name: scrcpy-android-usb-and-wifi-control
description: "Use when the user wants to remotely view/control an Android device (e.g. a Samsung A16/SM-A166U) from Linux via scrcpy, either over USB or wirelessly over Wi-Fi — covers install, launching, wireless pairing via adb tcpip, and the \"protocol fault\"/exit-1 failure caused by the adb daemon restarting and dropping the tcpip connection."
---

## Setup
- Install: `sudo pacman -S scrcpy` (pulls in adb as dependency if missing).
- Check device attached over USB: `adb devices` — daemon auto-starts if not running.

## USB control
```
scrcpy -s <serial>
```
`-s` only needed with multiple devices attached; plain `scrcpy` works with one.

## Going wireless
With phone on USB and same Wi-Fi network as the computer:
```
adb tcpip 5555
adb shell ip route     # note the phone's IP, e.g. 172.20.10.4 (look for src)
adb connect <ip>:5555
scrcpy -s <ip>:5555
```
USB cable can then be unplugged; the tcpip mode persists on the phone until reboot/USB debugging reset.

## Known failure: "protocol fault (couldn't read status)" / exit code 1
Symptom: launching `scrcpy -s <ip>:5555` shows the device as found, then:
```
adb: error: connect failed: protocol fault (couldn't read status): Success
ERROR: "adb push" returned with value 1
ERROR: Server connection failed
```
Cause: the adb daemon was restarted (e.g. `adb devices` auto-restarting a stopped daemon) after the tcpip connection was established, silently dropping the wireless device from its tracked list even though the phone is still listening on that port.

Fix: just reconnect, no need to redo `adb tcpip`:
```
adb connect <ip>:5555
adb devices -l   # confirm it shows up again
scrcpy -s <ip>:5555
```
Both the USB serial and the `<ip>:5555` entry can show simultaneously in `adb devices` while the cable is still plugged in — that's expected, not a conflict.

## Running as a background window (hub tool)
```
hub start --name scrcpy-<device> --application scrcpy --args '["-s","<ip>:5555"]' --persist
```
Exit code 0 on window close is normal (user just closed it). Exit code 1 with the protocol-fault log above means: reconnect adb first, then `hub restart`.
