#!/usr/bin/env python3
"""Run sector leadership intelligence / premarket plan / closing review."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.main import build_response
from src.us.sector.intelligence import (
    build_closing_review,
    build_premarket_plan,
    build_sector_intelligence_report,
    format_sector_intelligence_text,
)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build US sector/theme leadership intelligence")
    parser.add_argument("--mode", choices=["sector_intelligence", "premarket_plan", "closing_review"], default="sector_intelligence")
    parser.add_argument("--input-json", help="JSON file containing sector_report, or open_report/close_report for closing_review")
    parser.add_argument("--json", action="store_true", dest="as_json", help="print JSON instead of compact Korean text")
    return parser


def _load_payload(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return data
    raise ValueError("input JSON must be an object")


def _live_sector_report() -> dict[str, Any]:
    response = build_response('{"mode":"sector_strength","request":"장중 섹터 강약"}', explicit_mode="sector_strength")
    return response["data"]["sector_strength"]


def build_report(mode: str, payload: dict[str, Any]) -> dict[str, Any]:
    if mode == "closing_review":
        close_report = payload.get("close_report") or payload.get("sector_report") or _live_sector_report()
        open_report = payload.get("open_report") or close_report
        return build_closing_review(open_report, close_report)
    sector_report = payload.get("sector_report") or payload.get("report") or _live_sector_report()
    if mode == "premarket_plan":
        return build_premarket_plan(
            sector_report,
            previous_report=payload.get("previous_report"),
            social_report=payload.get("social_report"),
            watchlist=payload.get("watchlist"),
        )
    return build_sector_intelligence_report(
        sector_report,
        flow_events=payload.get("flow_events"),
        social_report=payload.get("social_report"),
        watchlist=payload.get("watchlist"),
        portfolio=payload.get("portfolio"),
    )


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    report = build_report(args.mode, _load_payload(args.input_json))
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False), flush=True)
    else:
        print(format_sector_intelligence_text(report), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
