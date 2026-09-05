---
name: wifi-latency-spikes-packet-loss-diagnosis
description: "Use when diagnosing Wi-Fi packet loss, recurring latency spikes, or severe jitter on Linux — covers isolating first-hop vs WAN, identifying high TX frame retry rates in station dump, weak 5GHz vs strong 2.4GHz BSSID selection, and the NetworkManager wpa_supplicant bgscan 30-second scan storm."
---

# Wi-Fi Latency Spikes & Packet Loss Diagnosis (Linux)

## Symptoms
- Connection feels sluggish, high jitter, packet loss during voice calls or interactive terminal sessions.
- Pings to local gateway (`192.168.0.1`) show periodic latency spikes (e.g. 100ms–500ms) or 3–10% packet loss despite local ping min RTT being ~0.8ms.
- Spikes occur at rhythmic intervals (especially every ~30 seconds).

---

## 1. Isolate First-Hop vs WAN

Run simultaneous quick pings to the default gateway and a public IP:
```bash
GATEWAY=$(ip route show default | awk '{print $3}')
ping -c 25 -i 0.2 "$GATEWAY"
ping -c 25 -i 0.2 1.1.1.1
```

- **If gateway drops packets or spikes to 200–500ms**: The bottleneck is the local wireless link, not the ISP/modem.
- **If gateway is stable (<2ms, 0% loss) but WAN drops**: The issue is upstream (cable/DSL/WISP/cellular link or router WAN bufferbloat).

---

## 2. Inspect PHY Layer Frame Retries & Signal

Check the wireless station dump:
```bash
IFACE=$(ip -br link | grep -E '^wl' | awk '{print $1}')
iw dev "$IFACE" link
iw dev "$IFACE" station dump
```

Look for:
- `signal`: Weaker than -70 dBm (e.g. -72 to -78 dBm) means low SNR through walls/distance.
- `tx retries`: Compare against `tx packets`. A healthy link has <5% retries. If `tx retries` is 20–35%+, physical 802.11 frame corruption is causing rate backoff and head-of-line blocking.
- `rx drop misc`: High counts indicate dropped/corrupted frames at the receiver.

---

## 3. The NetworkManager `bgscan` 30-Second Scan Storm

NetworkManager passes `bgscan simple:30:-70:86400` to `wpa_supplicant` by default.
- **The Trap**: If signal drops below `-70 dBm` (very common on 5 GHz when separated by walls), `wpa_supplicant` initiates a full-band background scan **every 30 seconds**.
- During each scan, the radio leaves its active channel to probe others, causing a recurring 200–500ms freeze and dropped packets.

---

## 4. Compare 2.4 GHz vs 5 GHz BSSIDs

Inspect available BSSIDs for the active SSID:
```bash
nmcli -f BSSID,SSID,CHAN,FREQ,RATE,SIGNAL,BARS dev wifi list
```

Often routers broadcast the same SSID on both:
- **5 GHz**: Higher nominal rate (e.g. 1170 Mbit/s) but severe wall attenuation (-75 dBm, 2 bars, 30% retries).
- **2.4 GHz**: Lower nominal rate (e.g. 144–195 Mbit/s) but strong wall penetration (-50 dBm, 4 bars, <3% retries).

NetworkManager defaults to 5 GHz due to advertised bitrate, locking the client into a degraded link.

---

## 5. Remediation

### Lock Connection Profile to High-SNR BSSID
Per NetworkManager specification, locking a profile to a specific BSSID forces the reliable band **and automatically disables `bgscan`**, solving both root causes at once:

```bash
# Get active connection name
CON_NAME=$(nmcli -t -f NAME,TYPE con show --active | grep '802-11-wireless' | cut -d: -f1)

# Lock to the desired BSSID (e.g. 2.4 GHz BSSID from nmcli dev wifi list)
nmcli con mod "$CON_NAME" 802-11-wireless.bssid "<TARGET_BSSID>"
nmcli con up "$CON_NAME"
```

### Re-verify
```bash
iw dev "$IFACE" station dump
ping -c 30 -i 0.2 "$GATEWAY"
```
Expect:
- `tx retries` dropping to <5%.
- Gateway ping jitter flattening to consistent sub-2ms RTT with 0% loss.
- 30-second scan freezes completely eliminated.

### Rollback / Unlock
To allow multi-AP roaming again if the device is moved close to the AP:
```bash
nmcli con mod "$CON_NAME" 802-11-wireless.bssid ""
nmcli con up "$CON_NAME"
```
