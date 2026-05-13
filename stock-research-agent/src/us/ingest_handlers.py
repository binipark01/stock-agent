"""US ingest mode handler."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def build_us_ingest_response(
    mode: str,
    runtime_context: dict[str, Any],
    symbols: list[str],
    db_path: Path,
    ingest_func: Callable[[list[str], Path], dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    if mode == "ingest":
        if ingest_func is None:
            raise ValueError("ingest mode requires ingest_func")
        ingest_result = ingest_func(symbols, db_path=db_path)
        return {
            "agent": "stock-research-agent",
            "mode": mode,
            "summary": f"미국주식 메인 워치리스트 기준으로 {', '.join(symbols)} 데이터 수집을 완료했습니다.",
            "symbols": symbols,
            "focus": [
                f"가격 저장: {ingest_result['stored_prices']}건",
                f"뉴스 저장: {ingest_result['stored_news']}건",
                f"실적 일정 저장: {ingest_result['stored_earnings']}건",
                f"DB: {ingest_result['db_path']}",
            ],
            "next_actions": [
                "미국장 장전 브리핑으로 저장 데이터 확인",
                "포트폴리오 보유 미국주 종목 우선순위 반영",
                "미국 실적 일정/소셜 시그널 저장 계층 추가",
            ],
            "features": runtime_context.get("features", []),
        }



    return None
