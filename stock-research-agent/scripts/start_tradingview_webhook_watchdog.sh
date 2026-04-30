#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT/logs"
PID_FILE="$LOG_DIR/tradingview_webhook_watchdog.pid"
WATCH_LOG="$LOG_DIR/tradingview_webhook_watchdog.log"
mkdir -p "$LOG_DIR"

if [[ -f "$PID_FILE" ]]; then
  old_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "$old_pid" ]] && kill -0 "$old_pid" 2>/dev/null; then
    echo "TradingView webhook watchdog already running pid=$old_pid"
    exit 0
  fi
  rm -f "$PID_FILE"
fi

(
  echo "[$(date -Is)] watchdog started"
  while true; do
    bash "$ROOT/scripts/start_tradingview_webhook.sh" >>"$WATCH_LOG" 2>&1 || true
    sleep 15
  done
) >>"$WATCH_LOG" 2>&1 &

echo $! > "$PID_FILE"
echo "Started TradingView webhook watchdog pid=$(cat "$PID_FILE")"
echo "Log: $WATCH_LOG"
