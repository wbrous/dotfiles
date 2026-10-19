#!/bin/bash
# End-to-end: a passkey made through real CTAP2 survives total loss of local state.
#
# Steps run strictly in order (they are dependent). Needs: a fake or real bw serve
# at $OMARCHY_PASSKEY_BW_URL, already unlocked; passless-ready group access to /dev/uhid
# (run under `newgrp fido`); the patched passless at $PASSLESS.
set -euo pipefail

here=$(cd "$(dirname "$0")/.." && pwd)
PASSLESS=${PASSLESS:-/tmp/plfix/passless}
store=${OMARCHY_PASSKEY_STORE:?}
log=$(mktemp)
daemon_pid=""

start_daemon() {
  PASSLESS_INTERACTION_MODE=automatic PASSLESS_BACKEND_TYPE=local \
    PASSLESS_LOCAL_PATH=$store PASSLESS_ENABLE_CREDENTIAL_BACKUP=true \
    "$PASSLESS" -v >"$log" 2>&1 &
  daemon_pid=$!
  for _ in $(seq 50); do
    grep -q "Authenticator is running" "$log" && sleep 0.5 && return 0
    sleep 0.2
  done
  echo "daemon did not start:"; tail -5 "$log"; return 1
}

stop_daemon() {
  [[ -n $daemon_pid ]] && kill "$daemon_pid" 2>/dev/null && wait "$daemon_pid" 2>/dev/null || true
  daemon_pid=""
  rm -f /run/user/"$(id -u)"/passless/*.lock
}
trap 'stop_daemon; rm -f "$log"' EXIT

echo "== 1. fresh store, start authenticator"
rm -rf "$store"; install -d -m 700 "$store"
start_daemon

echo "== 2. register a credential (the one we will try to lose)"
python3 /tmp/ctap_persist.py register

echo "== 3. back it up to the vault"
"$here/bin/omarchy-passkey-sync" push

echo "== 4. SIMULATED REBOOT: stop authenticator, destroy every local file"
stop_daemon
rm -rf "$store"; install -d -m 700 "$store"
echo "   local credential files: $(find "$store" -name '*.bin' | wc -l)"

echo "== 5. restore from the vault BEFORE the authenticator starts"
"$here/bin/omarchy-passkey-sync" pull
echo "   local credential files: $(find "$store" -name '*.bin' | wc -l)"

echo "== 6. start authenticator again and sign with the restored key"
start_daemon
python3 /tmp/ctap_persist.py assert

echo "== 7. counter advanced locally; push it so another device sees it"
"$here/bin/omarchy-passkey-sync" push
echo "E2E OK"
