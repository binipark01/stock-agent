"""US earnings mode handlers."""
from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from ..repository import fetch_upcoming_earnings, get_connection
    from .earnings.preview import build_earnings_preview
except ImportError:  # direct script execution
    from repository import fetch_upcoming_earnings, get_connection
    from us.earnings.preview import build_earnings_preview


def build_us_earnings_response(
    mode: str,
    runtime_context: dict[str, Any],
    symbols: list[str],
    db_path: Path,
) -> dict[str, Any] | None:
    if mode == "earnings_preview":
        previews = [build_earnings_preview(symbol, db_path=db_path) for symbol in symbols]
        focus = []
        for preview in previews:
            focus.append(f"{preview['symbol']} Setup: {preview['earnings_date']} / {preview['session']} / {preview['recent_price'] or '가격 데이터 없음'}")
            focus.append(f"{preview['symbol']} Bull case: {preview['bull_case'][0]}")
            focus.append(f"{preview['symbol']} Bear case: {preview['bear_case'][0]}")
            focus.append(f"{preview['symbol']} Key metrics: {', '.join(preview['key_metrics'][:3])}")
            focus.append(f"{preview['symbol']} Questions: {preview['questions_for_call'][0]}")
        return {
            "agent": "stock-research-agent",
            "mode": mode,
            "summary": f"미국주 실적 프리뷰 팩을 준비했습니다: {', '.join(symbols)}",
            "symbols": symbols,
            "focus": focus,
            "next_actions": [
                "실적 전 1~3일 동안 최근 뉴스와 가이던스 변화를 다시 확인",
                "bull / bear 해석이 갈리는 KPI를 따로 체크",
                "콜에서 답을 꼭 들어야 하는 질문 5개를 미리 적어둘 것",
            ],
            "features": runtime_context.get("features", []),
        }



    if mode == "earnings":
        conn = get_connection(db_path)
        upcoming = [row for row in fetch_upcoming_earnings(conn, limit=10) if row["symbol"] in symbols]
        if not upcoming:
            upcoming = fetch_upcoming_earnings(conn, limit=5)
        conn.close()
        focus = []
        for row in upcoming:
            session_map = {"after_close": "장마감 후", "before_open": "장시작 전", "unknown": "시간 미정"}
            session_label = session_map.get(row["session"], "시간 미정")
            focus.append(f"{row['symbol']} 실적 예정: {row['earnings_date']} / {session_label} / {row['note']}")
        if not focus:
            focus = ["저장된 실적 일정이 없어서 ingest를 먼저 돌려야 함"]
        return {
            "agent": "stock-research-agent",
            "mode": mode,
            "summary": f"미국주 메인 워치리스트 기준으로 실적 일정을 정리했습니다.",
            "symbols": symbols,
            "focus": focus,
            "next_actions": [
                "실적 2일 전 장전 브리핑에 우선 표시",
                "보유 종목이면 thesis_note와 가이던스 변수 같이 점검",
                "earnings 뒤 가격반응보다 가이던스/콜 내용을 먼저 확인",
            ],
            "features": runtime_context.get("features", []),
        }



    return None
