#!/bin/sh
payload=$({ command -p cat 2>/dev/null || cat; })
if [ -z "$payload" ]; then
  exit 0
fi
load_hook_endpoint() {
  endpoint_path="$1"
  case "$endpoint_path" in
    *.cmd)
      endpoint_cr=$(printf "\r")
      while IFS= read -r endpoint_line || [ -n "$endpoint_line" ]; do
        endpoint_line=${endpoint_line%"$endpoint_cr"}
        case "$endpoint_line" in
          "set ORCA_AGENT_HOOK_PORT="*) ORCA_AGENT_HOOK_PORT=${endpoint_line#*=} ;;
          "set ORCA_AGENT_HOOK_TOKEN="*) ORCA_AGENT_HOOK_TOKEN=${endpoint_line#*=} ;;
          "set ORCA_AGENT_HOOK_ENV="*) ORCA_AGENT_HOOK_ENV=${endpoint_line#*=} ;;
          "set ORCA_AGENT_HOOK_VERSION="*) ORCA_AGENT_HOOK_VERSION=${endpoint_line#*=} ;;
        esac
      done < "$endpoint_path"
      ;;
    *)
      . "$endpoint_path" 2>/dev/null || :
      ;;
  esac
}
if [ -n "$ORCA_AGENT_HOOK_ENDPOINT" ] && [ -r "$ORCA_AGENT_HOOK_ENDPOINT" ]; then
  load_hook_endpoint "$ORCA_AGENT_HOOK_ENDPOINT"
fi
if [ -z "$ORCA_AGENT_HOOK_PORT" ] || [ -z "$ORCA_AGENT_HOOK_TOKEN" ] || [ -z "$ORCA_PANE_KEY" ]; then
  exit 0
fi
post_codex_hook() {
  curl_bin="$1"
  connect_timeout="${2:-0.5}"
  max_time="${3:-1.5}"
  printf '%s' "$payload" | "$curl_bin" -sS -X POST "http://127.0.0.1:${ORCA_AGENT_HOOK_PORT}/hook/codex" \
    --connect-timeout "$connect_timeout" --max-time "$max_time" \
    --noproxy "127.0.0.1" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -H "X-Orca-Agent-Hook-Token: ${ORCA_AGENT_HOOK_TOKEN}" \
    --data-urlencode "paneKey=${ORCA_PANE_KEY}" \
    --data-urlencode "tabId=${ORCA_TAB_ID}" \
    --data-urlencode "launchToken=${ORCA_AGENT_LAUNCH_TOKEN}" \
    --data-urlencode "worktreeId=${ORCA_WORKTREE_ID}" \
    --data-urlencode "env=${ORCA_AGENT_HOOK_ENV}" \
    --data-urlencode "version=${ORCA_AGENT_HOOK_VERSION}" \
    --data-urlencode "payload@-"
}
is_wsl_runtime() {
  [ -n "$WSL_DISTRO_NAME" ] && return 0
  grep -qiE "microsoft|wsl" /proc/sys/kernel/osrelease /proc/version 2>/dev/null
}
if post_codex_hook curl >/dev/null 2>&1; then
  exit 0
fi
if is_wsl_runtime; then
  windows_curl=$(command -v curl.exe 2>/dev/null || true)
  if [ -n "$windows_curl" ] && [ -x "$windows_curl" ]; then
    post_codex_hook "$windows_curl" 3 5 >/dev/null 2>&1 || true
  fi
fi
exit 0
