# Networking on Linux

Covers Wi-Fi diagnosis (general latency spikes, mt7925e post-suspend bug) and Tailscale forwarding warnings.

## Wi-Fi latency spikes and packet loss

**Symptom:** Sluggish connection, jitter, loss on calls/SSH; pings to the local gateway show periodic 100–500ms spikes or 3–10% loss despite ~0.8ms minimum RTT; spikes at rhythmic intervals (especially every ~30s).

**Fix — isolate first-hop vs WAN:**
```bash
GATEWAY=$(ip route show default | awk '{print $3}')
ping -c 25 -i 0.2 "$GATEWAY"
ping -c 25 -i 0.2 1.1.1.1
```
Gateway dropping/spiking = local wireless link, not ISP. Gateway stable (<2ms, 0% loss) but WAN dropping = upstream (cable/DSL/WISP/cellular or router bufferbloat).

**Fix — inspect PHY retries:**
```bash
IFACE=$(ip -br link | grep -E '^wl' | awk '{print $1}')
iw dev "$IFACE" link
iw dev "$IFACE" station dump
```
`signal` weaker than -70 dBm (e.g. -72 to -78) means low SNR. `tx retries` vs `tx packets`: healthy <5%; 20–35%+ means 802.11 frame corruption causing rate backoff and head-of-line blocking. High `rx drop misc` = receiver-side corrupted frames.

**Cause — the NetworkManager bgscan 30-second scan storm:** NM passes `bgscan simple:30:-70:86400` to wpa_supplicant. Below -70 dBm (common on 5 GHz through walls), wpa_supplicant does a full-band background scan every 30 seconds; the radio leaves its channel, causing a recurring 200–500ms freeze and drops.

**Cause — weak 5 GHz vs strong 2.4 GHz:** Check `nmcli -f BSSID,SSID,CHAN,FREQ,RATE,SIGNAL,BARS dev wifi list`. Same SSID often on both: 5 GHz higher nominal rate (e.g. 1170 Mbit/s) but -75 dBm/2 bars/30% retries through walls; 2.4 GHz lower rate (144–195 Mbit/s) but -50 dBm/4 bars/<3% retries. NM defaults to 5 GHz by advertised bitrate.

**Fix — lock profile to the high-SNR BSSID** (also automatically disables bgscan):
```bash
CON_NAME=$(nmcli -t -f NAME,TYPE con show --active | grep '802-11-wireless' | cut -d: -f1)
nmcli con mod "$CON_NAME" 802-11-wireless.bssid "<TARGET_BSSID>"
nmcli con up "$CON_NAME"
```
Re-verify with `iw dev "$IFACE" station dump` and `ping -c 30 -i 0.2 "$GATEWAY` — expect retries <5%, flat sub-2ms RTT, no 30s freezes. Rollback: `nmcli con mod "$CON_NAME" 802-11-wireless.bssid "" && nmcli con up "$CON_NAME"`.

_Migrated from: wifi-latency-spikes-packet-loss-diagnosis_

## mt7925e packet loss after suspend/resume

**Symptom (preconditions: MediaTek `mt7925e` Wi-Fi 7, e.g. Framework 13 Ryzen AI, RZ717 PCIe adapter; s2idle sleep):** Fine while awake; after lid-close suspend + resume, Wi-Fi reassociates cleanly but suffers heavy loss / multi-second RTT / intermittent "no route to host" until a full reboot. Resuming again does not fix it.

**Fix — diagnostic sequence (don't skip to "known bug"):**
1. `systemctl show -p HandleLidSwitch,HandleLidSwitchExternalPower,HandleLidSwitchDocked`; `cat /sys/power/mem_sleep` (`[s2idle]` vs `[deep]` — this bug is s2idle-specific).
2. Rule out Wi-Fi power-save first: `iw dev <if> get power_save` — if on, that's a separate fix (`iw dev <if> set power_save off` / NM `wifi.powersave=2`).
3. Confirm driver: `ethtool -i <if>` → `driver: mt7925e`.
4. `journalctl -k --since "<last resume time>" | grep -iE "mt7925|wlp|assoc|timeout|firmware"` — clean auth/assoc means the link reconnects; the bug is firmware packet handling post-resume.
5. Verify loss against the RIGHT gateway from `ip route` (`default via X`), not a guessed `.1` — pinging a nonexistent host gives "No route to host"/ARP FAILED that mimics a network bug. `ip neigh show dev <if>` FAILED for the real gateway is a red flag.
6. `iw dev <if> station dump` — climbing `tx retries`/`rx drop misc` corroborates airtime problems vs routing/DNS.

**Cause:** Known open upstream bug class in `mt76`/`mt7925e`: CLC command timeouts during suspend/resume plus periodic `linux-firmware-mediatek` regressions (bad builds shipping 23–29% loss / 1.2–1.8s RTT post-resume). Firmware state is wedged, not the network stack — hence only a module reload or reboot clears it. Refs: kernel patch `wifi: mt76: mt7925: fix CLC command timeout when suspend/resume`; Framework Community, Ubuntu launchpad #2115643/#2118937/#2141198, Arch forum mt7925e/mt7921e threads.

**Fix, cheapest first:**
1. systemd-sleep hook reloading the driver on every resume (`/usr/lib/systemd/system-sleep/99-mt7925e-resume-fix.sh`, root-owned, `chmod +x`):
   ```sh
   #!/bin/sh
   case "$1" in
     post)
       /usr/bin/modprobe -r mt7925e
       sleep 1
       /usr/bin/modprobe mt7925e
       ;;
   esac
   ```
2. Pin/downgrade `linux-firmware-mediatek` via the Arch Linux Archive + `IgnorePkg` in `/etc/pacman.conf` if a recent firmware regression is suspected.
3. Track a newer kernel — CLC-timeout fixes landed/backported around 6.12→6.14/6.16.
4. Long-term: switch `mem_sleep` to `deep` (S3) if hardware supports true S3, at the cost of slower resume and higher sleep battery use.

_Migrated from: mt7925e-suspend-resume-packet-loss_

## Tailscale IPv6-forwarding and UDP-GRO warnings (Arch)

**Symptom:** Tailscale warns `IPv6 forwarding is disabled. ... See https://tailscale.com/s/ip-forwarding` and/or `UDP GRO forwarding is suboptimally configured on <iface>`; subnet routes / exit nodes misbehave.

**Fix:**
```sh
sudo sysctl -w net.ipv6.conf.all.forwarding=1
echo 'net.ipv6.conf.all.forwarding=1' | sudo tee /etc/sysctl.d/99-tailscale.conf
sysctl net.ipv4.ip_forward   # usually already on via tailscaled/systemd
sudo pacman -S --noconfirm ethtool   # may be absent on minimal Arch; `pacman -Q ethtool` failing is expected, not a bug
# uplink iface from `ip route` / `ip link`, e.g. wlp192s0:
sudo ethtool -K <iface> rx-udp-gro-forwarding on rx-gro-list off
sysctl net.ipv6.conf.all.forwarding
ethtool -k <iface> | grep -i gro   # expect rx-udp-gro-forwarding: on, rx-gro-list: off
```
**Cause (persistence caveat):** `ethtool -K` is NOT persistent across reboot/link resets and Arch has no built-in unit for it — re-run after reboots, or create a systemd oneshot (e.g. `/etc/systemd/system/tailscale-gro-fix.service` with `ExecStart=/usr/bin/ethtool -K <iface> ...`, `WantedBy=multi-user.target`).

_Migrated from: tailscale-forwarding-warnings-fix_
