#!/bin/sh
case "$ORCA_ANTIGRAVITY_EVENT" in
  Stop)
    printf '{"decision":""}\n'
    ;;
  *)
    printf "{}\n"
    ;;
esac
payload=$({ command -p cat 2>/dev/null || cat; })
if [ -z "$payload" ]; then
  payload='{}'
fi
if [ -n "$ORCA_AGENT_HOOK_ENDPOINT" ] && [ -r "$ORCA_AGENT_HOOK_ENDPOINT" ]; then
  . "$ORCA_AGENT_HOOK_ENDPOINT" 2>/dev/null || :
fi
if [ -z "$ORCA_AGENT_HOOK_PORT" ] || [ -z "$ORCA_AGENT_HOOK_TOKEN" ] || [ -z "$ORCA_PANE_KEY" ]; then
  exit 0
fi
printf '%s' "$payload" | curl -sS -X POST "http://127.0.0.1:${ORCA_AGENT_HOOK_PORT}/hook/antigravity" \
  --connect-timeout 0.5 --max-time 1.5 \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -H "X-Orca-Agent-Hook-Token: ${ORCA_AGENT_HOOK_TOKEN}" \
  --data-urlencode "paneKey=${ORCA_PANE_KEY}" \
  --data-urlencode "tabId=${ORCA_TAB_ID}" \
  --data-urlencode "launchToken=${ORCA_AGENT_LAUNCH_TOKEN}" \
  --data-urlencode "worktreeId=${ORCA_WORKTREE_ID}" \
  --data-urlencode "env=${ORCA_AGENT_HOOK_ENV}" \
  --data-urlencode "version=${ORCA_AGENT_HOOK_VERSION}" \
  --data-urlencode "hook_event_name=${ORCA_ANTIGRAVITY_EVENT}" \
  --data-urlencode "payload@-" >/dev/null 2>&1 || true
exit 0
