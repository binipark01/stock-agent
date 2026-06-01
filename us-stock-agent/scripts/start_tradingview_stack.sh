#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

bash "$ROOT/scripts/start_tradingview_webhook_watchdog.sh"

if [[ -x "$ROOT/tools/cloudflared" ]] || command -v cloudflared >/dev/null 2>&1; then
  bash "$ROOT/scripts/start_cloudflared_quick_tunnel.sh" || true
else
  echo "cloudflared not installed; local webhook is running but TradingView cannot reach it from internet."
fi
