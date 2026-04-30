#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$ROOT/logs/cloudflared_quick_tunnel.pid"
if [[ -f "$PID_FILE" ]]; then
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid"
    echo "Stopped cloudflared quick tunnel pid=$pid"
  else
    echo "cloudflared quick tunnel pid=$pid not running"
  fi
  rm -f "$PID_FILE"
else
  echo "cloudflared quick tunnel pid file not found"
fi
