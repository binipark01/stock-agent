#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT/logs"
PID_FILE="$LOG_DIR/tradingview_webhook.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo "TradingView webhook pid file not found."
  exit 0
fi

pid="$(cat "$PID_FILE" 2>/dev/null || true)"
if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
  kill "$pid"
  echo "Stopped TradingView webhook pid=$pid"
else
  echo "TradingView webhook pid=$pid not running"
fi
rm -f "$PID_FILE"
