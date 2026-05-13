"""US auxiliary market-data mode handlers."""
from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from ..tossinvest_data import build_toss_day_market_quote_report
    from .market_data.yfinance import build_yfinance_focus_lines, fetch_yfinance_market_pack
except ImportError:  # direct script execution
    from tossinvest_data import build_toss_day_market_quote_report
    from us.market_data.yfinance import build_yfinance_focus_lines, fetch_yfinance_market_pack


def build_us_market_data_response(
    mode: str,
    payload: dict[str, Any],
    runtime_context: dict[str, Any],
    request_text: str,
    symbols: list[str],
    db_path: Path,
) -> dict[str, Any] | None:
    if mode == "day_market":
        day_report = build_toss_day_market_quote_report(request_text, symbols=symbols, runtime_context=runtime_context)
        return {
            "agent": "stock-research-agent",
            "mode": mode,
            "summary": day_report["summary"],
            "symbols": day_report["symbols"],
            "focus": day_report["focus_lines"],
            "next_actions": day_report["next_actions"],
            "features": list(dict.fromkeys([*runtime_context.get("features", []), "day_market", "tossinvest_public"])),
            "data": {"day_market": day_report},
        }



    if mode == "yfinance_pack":
        focus: list[str] = []
        packs = []
        for symbol in symbols[:3]:
            pack = fetch_yfinance_market_pack(symbol)
            packs.append(pack)
            focus.extend(build_yfinance_focus_lines(pack, max_lines=8))
        return {
            "agent": "stock-research-agent",
            "mode": mode,
            "summary": f"yfinance optional pack을 정리했습니다: {', '.join(symbols[:3])}",
            "symbols": symbols,
            "focus": focus,
            "next_actions": [
                "현재가는 YF Quote source/timestamp 한계가 있으니 실매매 전 별도 현재가와 대조",
                "옵션 OI/volume은 최근 만기 중심으로 콜/풋 쏠림만 빠르게 확인",
                "뉴스/캘린더/홀더 데이터가 비면 yfinance 호출 제한 또는 Yahoo 쪽 누락으로 간주",
            ],
            "features": runtime_context.get("features", []) + ["yfinance_optional_pack"],
            "data": {"yfinance_packs": packs},
        }



    return None
