---
name: mt7925e-suspend-resume-packet-loss
description: "Use when a laptop with a MediaTek mt7925e Wi-Fi 7 chipset (e.g. Framework 13 AMD, RZ717 PCIe adapter) gets severe packet loss / high RTT / \"no route to host\" style connectivity degradation after closing the lid or resuming from suspend, which only clears after a full reboot. Also covers diagnosing lid-close packet loss in general on Linux (checking HandleLidSwitch, s2idle vs deep sleep, iw power_save, station dump retries) before concluding it's this specific known upstream bug."
---

## Symptom
Laptop with MediaTek `mt7925e` (Wi-Fi 7, e.g. Framework 13 Ryzen AI HX/350, RZ717 PCIe adapter) has fine
connectivity while awake, but after closing the lid (which triggers `suspend` per systemd-logind's
`HandleLidSwitch`) and reopening, the Wi-Fi reassociates successfully (driver logs show clean
authenticate/associate) but traffic suffers heavy packet loss / multi-second RTT / intermittent
"no route to host" until a full reboot. Rebooting is the only thing that clears it — resuming again does not.

## Diagnostic sequence (don't skip straight to "it's the known bug")
1. Confirm lid action and sleep mode:
   - `systemctl show -p HandleLidSwitch,HandleLidSwitchExternalPower,HandleLidSwitchDocked`
   - `cat /sys/power/mem_sleep` — `[s2idle]` vs `[deep]`. This bug is specifically tied to s2idle.
2. Rule out simple Wi-Fi power-save first: `iw dev <if> get power_save` — if "on", that's a separate,
   simpler fix (`iw dev <if> set power_save off` / NetworkManager `wifi.powersave=2`), not this bug.
3. Confirm driver/hardware: `ethtool -i <if>` → `driver: mt7925e`.
4. Check resume logs for the actual reassociation and any firmware timeouts:
   `journalctl -k --since "<last resume time>" | grep -iE "mt7925|wlp|assoc|timeout|firmware"`
   — clean auth/assoc lines mean the *link* reconnects fine; the bug is in firmware packet handling
   post-resume, not failure to reconnect.
5. Verify the loss is real, against the RIGHT gateway. Get it from `ip route` (`default via X`), not a
   guessed `.1` address — pinging a nonexistent host gives "No route to host" / ARP FAILED and looks like
   a network bug but is actually operator error re-checking the wrong IP.
   `ip neigh show dev <if>` — FAILED entry for gateway is a real red flag if it's the actual configured gateway.
6. Check `iw dev <if> station dump` for `tx retries` / `rx drop misc` climbing — corroborates real airtime
   quality problems distinguishing from a routing/DNS issue.

## Root cause
Known open upstream bug class in `mt76`/`mt7925e`: CLC command timeouts during suspend/resume, and
periodic `linux-firmware-mediatek` regressions (specific bad builds have shipped causing 23-29% packet
loss / 1.2-1.8s RTT post-resume) that only clear via full module reload or reboot — resuming again does
NOT fix it because the firmware state itself is wedged, not just the network stack.
Reference: `wifi: mt76: mt7925: fix CLC command timeout when suspend/resume` (kernel patch), Framework
Community and Ubuntu launchpad bugs (#2115643, #2118937, #2141198), Arch forum threads on mt7925e/mt7921e
post-suspend Wi-Fi failure.

## Fixes, cheapest first
1. **systemd-sleep hook to reload the driver on every resume** (avoids needing a reboot):
   ```sh
   # /usr/lib/systemd/system-sleep/99-mt7925e-resume-fix.sh (root-owned, chmod +x)
   #!/bin/sh
   case "$1" in
     post)
       /usr/bin/modprobe -r mt7925e
       sleep 1
       /usr/bin/modprobe mt7925e
       ;;
   esac
   ```
   systemd invokes any executable under `system-sleep/` with `$1=post` right after resume. This is
   non-destructive and installs without needing to wait for an upstream fix.
2. **Pin/downgrade `linux-firmware-mediatek`** if you suspect a recent firmware regression (check package
   version against known-bad build windows reported upstream), via the Arch Linux Archive, then
   `IgnorePkg` it in `/etc/pacman.conf` until confirmed fixed.
3. **Track newer kernel** — fixes for the CLC timeout have landed/backported around the 6.12→6.14/6.16
   lines; updating past the fix version resolves it without workarounds.
4. Longer term, switching `mem_sleep` to `deep` (S3) instead of `s2idle` avoids this bug class entirely if
   the hardware/firmware supports true S3 suspend, at the cost of slower resume and higher battery use
   during sleep.
