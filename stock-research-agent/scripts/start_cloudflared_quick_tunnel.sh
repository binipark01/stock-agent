#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/config/tradingview_webhook.env"
LOG_DIR="$ROOT/logs"
PID_FILE="$LOG_DIR/cloudflared_quick_tunnel.pid"
LOG_FILE="$LOG_DIR/cloudflared_quick_tunnel.log"
mkdir -p "$LOG_DIR"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

BIN="${CLOUDFLARED_BIN:-}"
if [[ -z "$BIN" ]]; then
  if command -v cloudflared >/dev/null 2>&1; then
    BIN="$(command -v cloudflared)"
  elif [[ -x "$ROOT/tools/cloudflared" ]]; then
    BIN="$ROOT/tools/cloudflared"
  else
    echo "cloudflared not installed. Install it first or place binary at $ROOT/tools/cloudflared"
    exit 1
  fi
fi

PORT="${TRADINGVIEW_WEBHOOK_PORT:-8765}"

if [[ -f "$PID_FILE" ]]; then
  old_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "$old_pid" ]] && kill -0 "$old_pid" 2>/dev/null; then
    echo "cloudflared quick tunnel already running pid=$old_pid"
    grep -Eo 'https://[-a-zA-Z0-9.]+\.trycloudflare\.com' "$LOG_FILE" | tail -1 || true
    exit 0
  fi
  rm -f "$PID_FILE"
fi

: > "$LOG_FILE"
nohup "$BIN" tunnel --url "http://localhost:$PORT" >"$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
echo "Started cloudflared quick tunnel pid=$(cat "$PID_FILE")"
echo "Waiting for public URL..."
for _ in $(seq 1 30); do
  url="$(grep -Eo 'https://[-a-zA-Z0-9.]+\.trycloudflare\.com' "$LOG_FILE" | tail -1 || true)"
  if [[ -n "$url" ]]; then
    secret="${TRADINGVIEW_WEBHOOK_SECRET:-}"
    echo "TradingView webhook URL: ${url}/webhook/tradingview?secret=${secret}"
    exit 0
  fi
  sleep 1
done

echo "Tunnel started but URL not detected yet. Check $LOG_FILE"
