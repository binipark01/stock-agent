"""US news, filing, topic-hub, and public-feed mode handlers."""
from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from ..saveticker_data import build_saveticker_important_breaking, run_saveticker_ingest
    from .news.sec_filings import build_sec_focus_lines, fetch_sec_filings_pack
    from ..topic_hub import build_topic_hub_focus_lines
    from ..tossinvest_data import run_toss_ingest
except ImportError:  # direct script execution
    from saveticker_data import build_saveticker_important_breaking, run_saveticker_ingest
    from us.news.sec_filings import build_sec_focus_lines, fetch_sec_filings_pack
    from topic_hub import build_topic_hub_focus_lines
    from tossinvest_data import run_toss_ingest


def build_us_news_response(
    mode: str,
    payload: dict[str, Any],
    runtime_context: dict[str, Any],
    symbols: list[str],
    portfolio: set[str],
    watchlist: set[str],
    db_path: Path,
    sec_filings_fetch_func=None,
) -> dict[str, Any] | None:
    if mode == "sec_filings":
        focus: list[str] = []
        packs = []
        for symbol in symbols[:3]:
            fetch_pack = sec_filings_fetch_func or fetch_sec_filings_pack
            pack = fetch_pack(symbol)
            packs.append(pack)
            focus.extend(build_sec_focus_lines(pack, max_lines=5))
        return {
            "agent": "us-stock-agent",
            "mode": mode,
            "summary": f"SEC/EDGAR 최근 공시를 정리했습니다: {', '.join(symbols[:3])}",
            "symbols": symbols,
            "focus": focus,
            "next_actions": [
                "8-K는 form8-k 본문보다 ex99-1/exhibit 원문에 실제 숫자와 headline이 있는지 확인",
                "S-3/S-1은 primary issuance인지 selling-stockholder resale인지 구분",
                "10-Q/10-K는 MD&A, liquidity, risk factor 변화만 먼저 확인",
            ],
            "features": runtime_context.get("features", []) + ["sec_filings_pack"],
            "data": {"sec_filings_packs": packs},
        }



    if mode == "topic_hub":
        focus = build_topic_hub_focus_lines(symbols, db_path=db_path)
        return {
            "agent": "us-stock-agent",
            "mode": mode,
            "summary": f"DataHub-lite topic 목록과 캐시 peek를 정리했습니다: {', '.join(symbols[:3])}",
            "symbols": symbols,
            "focus": focus,
            "next_actions": [
                "topic 이름을 기준으로 quote/news/filing/options/social 소스를 분리해서 붙이기",
                "peek age_ms가 큰 항목은 ingest 또는 live fetch를 먼저 실행",
                "알림 모드에서는 필요한 topic만 좁혀 payload를 짧게 유지",
            ],
            "features": runtime_context.get("features", []) + ["topic_hub"],
        }



    if mode == "saveticker_sync":
        saveticker_result = run_saveticker_ingest(db_path)
        return {
            "agent": "us-stock-agent",
            "mode": mode,
            "summary": "SaveTicker 미국주 속보 수집을 완료했습니다.",
            "symbols": symbols,
            "focus": [
                f"SaveTicker 뉴스 저장: {saveticker_result['saveticker_items']}건",
                f"DB: {saveticker_result['db_path']}",
            ],
            "next_actions": [
                "brief 모드에서 SaveTicker 속보 섹션 확인",
                "포트폴리오 종목과 직접 매핑되는 속보 우선 검토",
                "rumor 태그가 붙은 뉴스는 추가 검증 후 판단",
            ],
            "features": runtime_context.get("features", []),
        }



    if mode == "saveticker_breaking":
        important_text = build_saveticker_important_breaking(
            db_path,
            portfolio_symbols=portfolio,
            watchlist_symbols=watchlist.union(set(symbols)),
            limit=int(payload.get("limit") or runtime_context.get("limit") or 5),
        )
        focus = [line[2:] if line.startswith("- ") else line for line in important_text.splitlines()[1:]]
        return {
            "agent": "us-stock-agent",
            "mode": mode,
            "summary": "SaveTicker 중요 속보만 선별했습니다.",
            "symbols": symbols,
            "focus": focus,
            "next_actions": [
                "루머/카더라 라벨은 검증 전 포지션 확대 금지",
                "보유/관심종목 관련 속보는 가격 반응과 공식 공시를 바로 대조",
                "중요 속보가 비어 있으면 먼저 saveticker_sync로 최신 뉴스 수집",
            ],
            "features": runtime_context.get("features", []) + ["saveticker_important_breaking"],
        }



    if mode == "toss_sync":
        toss_result = run_toss_ingest(db_path)
        return {
            "agent": "us-stock-agent",
            "mode": mode,
            "summary": "토스증권 공개 미국지수/뉴스 수집을 완료했습니다.",
            "symbols": symbols,
            "focus": [
                f"토스 미국지수 저장: {toss_result['toss_indices']}건",
                f"토스 뉴스 저장: {toss_result['toss_news']}건",
                f"DB: {toss_result['db_path']}",
            ],
            "next_actions": [
                "brief 모드에서 토스 보조지표 섹션 확인",
                "토스 뉴스와 Yahoo 뉴스 시각 차이 비교",
                "미국지수/뉴스를 장전 브리핑 우선순위에 반영",
            ],
            "features": runtime_context.get("features", []),
        }



    return None
