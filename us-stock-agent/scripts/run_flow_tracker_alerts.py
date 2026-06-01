#!/usr/bin/env python3
"""Run stateful US sector/theme flow event tracker.

Default behavior is watchdog-friendly: print nothing when no event is detected,
and print the short event alert when a new non-duplicate event appears.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.flow_tracker import run_flow_tracker_cycle

DEFAULT_DB_PATH = ROOT / "data" / "flow_tracker.db"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Track sector/theme flow-proxy changes and print short event alerts")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="SQLite DB path for flow tracker state")
    parser.add_argument("--input-json", help="Read a prebuilt sector_strength report JSON instead of live fetch")
    parser.add_argument("--cooldown-minutes", type=int, default=20, help="Duplicate event cooldown per theme/event type")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Print full sanitized JSON result")
    return parser


def _load_report_from_input(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _build_live_report() -> dict[str, Any]:
    from scripts.run_sector_strength_alerts import build_sector_response

    return build_sector_response()


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    report = _load_report_from_input(args.input_json) if args.input_json else _build_live_report()
    result = run_flow_tracker_cycle(report, db_path=args.db_path, cooldown_minutes=args.cooldown_minutes)
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False), flush=True)
    elif result.get("alert_text"):
        print(result["alert_text"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
