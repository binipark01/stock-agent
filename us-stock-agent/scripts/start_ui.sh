#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
python3 scripts/ui_server.py --host "${US_STOCK_AGENT_UI_HOST:-127.0.0.1}" --port "${US_STOCK_AGENT_UI_PORT:-8877}"
