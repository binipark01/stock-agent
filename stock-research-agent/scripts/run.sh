#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON_BIN="${STOCK_AGENT_PYTHON:-python3}"
"$PYTHON_BIN" src/main.py "$@"
