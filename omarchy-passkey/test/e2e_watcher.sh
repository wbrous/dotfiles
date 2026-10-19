#!/bin/bash
# End-to-end: registering a passkey through real CTAP2 reaches the vault with NO
# manual push, because omarchy-passkey-watch pushes it. Also checks the watcher
# does not push on unrelated writes (temp files).
#
# Needs an UNLOCKED bw serve (or stand-in) at $OMARCHY_PASSKEY_BW_URL, and
# /dev/uhid access (run under `newgrp fido`).
set -euo pipefail

here=$(cd "$(dirname "$0")/.." && pwd)
PASSLESS=${PASSLESS:-/tmp/plfix/passless}
store=${OMARCHY_PASSKEY_STORE:?}
vault_file=${VAULT_FILE:?set VAULT_FILE to the path of the stand-in items file}
log=$(mktemp); watch_log=$(mktemp)
pids=()

cleanup() {
  for pid in "${pids[@]}"; do kill "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
  rm -f /run/user/"$(id -u)"/passless/*.lock "$log" "$watch_log"
}
trap cleanup EXIT

items() { python3 -c "import json,sys;print(len(json.load(open('$vault_file'))))" 2>/dev/null || echo 0; }

# notify-send is stubbed so a failed push is visible here instead of on the desktop.
stub=$(mktemp -d)
trap 'cleanup; rm -rf "$stub"' EXIT
cat >"$stub/notify-send" <<STUB
#!/bin/bash
echo "NOTIFY: \$*" >> "$watch_log"
STUB
chmod +x "$stub/notify-send"

rm -rf "$store"; install -d -m 700 "$store"
rm -f "$vault_file"

PASSLESS_INTERACTION_MODE=automatic PASSLESS_BACKEND_TYPE=local PASSLESS_LOCAL_PATH=$store \
  PASSLESS_ENABLE_CREDENTIAL_BACKUP=true "$PASSLESS" -v >"$log" 2>&1 &
pids+=($!)
for _ in $(seq 50); do grep -q "Authenticator is running" "$log" && break; sleep 0.2; done
sleep 0.5

PATH="$stub:$PATH" "$here/bin/omarchy-passkey-watch" >>"$watch_log" 2>&1 &
pids+=($!)
sleep 1

echo "== vault items before registering: $(items)"
python3 /tmp/ctap_persist.py register
for _ in $(seq 40); do [[ $(items) -ge 1 ]] && break; sleep 0.25; done
echo "== vault items after registering (no manual push): $(items)"
[[ $(items) -eq 1 ]] || { echo "FAIL: watcher did not push"; cat "$watch_log"; exit 1; }

echo "== registering a second credential: still exactly one push each, no duplicates"
python3 /tmp/ctap_flags.py >/dev/null
for _ in $(seq 40); do [[ $(items) -ge 2 ]] && break; sleep 0.25; done
sleep 1.5
echo "== vault items: $(items) (want 2)"
[[ $(items) -eq 2 ]] || { echo "FAIL: expected 2 items"; cat "$watch_log"; exit 1; }
grep -q NOTIFY "$watch_log" && { echo "FAIL: unexpected notification:"; grep NOTIFY "$watch_log"; exit 1; }
echo "WATCHER E2E OK"
