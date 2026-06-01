#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/config/tradingview_webhook.env"
LOG_DIR="$ROOT/logs"
PID_FILE="$LOG_DIR/tradingview_webhook.pid"
OUT_LOG="$LOG_DIR/tradingview_webhook.out.log"
ERR_LOG="$LOG_DIR/tradingview_webhook.err.log"
mkdir -p "$LOG_DIR"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # Strip CRLF at source time so Windows-edited env files do not break WSL bash.
  # shellcheck disable=SC1090
  source <(sed 's/\r$//' "$ENV_FILE")
  set +a
fi

HOST="${TRADINGVIEW_WEBHOOK_HOST:-0.0.0.0}"
PORT="${TRADINGVIEW_WEBHOOK_PORT:-8765}"
SECRET="${TRADINGVIEW_WEBHOOK_SECRET:-}"
NOTIFY_COMMAND="${TRADINGVIEW_WEBHOOK_NOTIFY_COMMAND:-}"
NOTIFY_TIMEOUT="${TRADINGVIEW_WEBHOOK_NOTIFY_TIMEOUT:-30}"

is_pid_alive() {
  local pid="$1"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

if [[ -f "$PID_FILE" ]]; then
  old_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if is_pid_alive "$old_pid"; then
    echo "TradingView webhook already running pid=$old_pid"
    exit 0
  fi
  rm -f "$PID_FILE"
fi

if ss -ltn 2>/dev/null | grep -q ":$PORT "; then
  echo "Port $PORT is already listening. Not starting duplicate."
  exit 0
fi

cd "$ROOT"
PYTHON_BIN="${STOCK_AGENT_PYTHON:-python3}"
nohup "$PYTHON_BIN" scripts/tradingview_webhook_server.py \
  --host "$HOST" \
  --port "$PORT" \
  --secret "$SECRET" \
  --notify-command "$NOTIFY_COMMAND" \
  --notify-timeout "$NOTIFY_TIMEOUT" \
  >>"$OUT_LOG" 2>>"$ERR_LOG" &
pid=$!
echo "$pid" > "$PID_FILE"
echo "Started TradingView webhook pid=$pid url=http://$HOST:$PORT/webhook/tradingview"
echo "Logs: $OUT_LOG / $ERR_LOG"
