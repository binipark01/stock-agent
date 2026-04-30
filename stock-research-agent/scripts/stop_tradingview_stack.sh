#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bash "$ROOT/scripts/stop_cloudflared_quick_tunnel.sh" || true
bash "$ROOT/scripts/stop_tradingview_webhook_watchdog.sh" || true
