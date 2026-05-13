import argparse
import json
import re
from pathlib import Path
from typing import Any

try:
    from .repository import get_connection, insert_earnings_event, insert_news_item, insert_price_snapshot
    from .market_data import fetch_earnings_event, fetch_price_snapshot, fetch_symbol_news
    from .tossinvest_data import build_toss_market_brief
    from .saveticker_data import build_saveticker_brief
    from .us.social.threads import search_threads_seed_accounts
    from .us.market_data.yfinance import build_yfinance_focus_lines, fetch_yfinance_market_pack
    from .us.news.sec_filings import fetch_sec_filings_pack
    from .watchlists import SYMBOL_ALIASES, load_watchlist
    from .request_modes import infer_mode
    from .us.technical.snapshot import build_technical_snapshot
    from .kr.mode_handlers import build_krx_mode_response
    from .us.mode_handlers import build_us_mode_response
    from .us.core_handlers import build_us_core_response
    from .us.core_helpers import (
        _infer_brief_phase,
        build_brief_from_db,
        build_catalyst_board,
        build_compare_payload,
        build_compare_view,
        build_earnings_nearby_alert,
        build_market_summary,
        build_overnight_recap_payload,
        build_portfolio_brief,
        build_position_alert,
        build_staleness_warning,
        build_symbol_summary,
        build_thesis_break_reason,
        build_watchlist_movers,
        build_what_changed_payload,
        build_why_symbol_payload,
        build_breaking_line,
    )
except ImportError:  # direct script execution
    from repository import get_connection, insert_earnings_event, insert_news_item, insert_price_snapshot
    from market_data import fetch_earnings_event, fetch_price_snapshot, fetch_symbol_news
    from tossinvest_data import build_toss_market_brief
    from saveticker_data import build_saveticker_brief
    from us.social.threads import search_threads_seed_accounts
    from us.market_data.yfinance import build_yfinance_focus_lines, fetch_yfinance_market_pack
    from us.news.sec_filings import fetch_sec_filings_pack
    from watchlists import SYMBOL_ALIASES, load_watchlist
    from request_modes import infer_mode
    from us.technical.snapshot import build_technical_snapshot
    from kr.mode_handlers import build_krx_mode_response
    from us.mode_handlers import build_us_mode_response
    from us.core_handlers import build_us_core_response
    from us.core_helpers import (
        _infer_brief_phase,
        build_brief_from_db,
        build_catalyst_board,
        build_compare_payload,
        build_compare_view,
        build_earnings_nearby_alert,
        build_market_summary,
        build_overnight_recap_payload,
        build_portfolio_brief,
        build_position_alert,
        build_staleness_warning,
        build_symbol_summary,
        build_thesis_break_reason,
        build_watchlist_movers,
        build_what_changed_payload,
        build_why_symbol_payload,
        build_breaking_line,
    )


DEFAULT_SYMBOLS = ["NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "META", "GOOGL", "AMD"]
DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "stock_agent.db"
DEFAULT_WATCHLIST_PATH = Path(__file__).resolve().parents[1] / "config" / "watchlist.json"


def parse_request_payload(raw_request: str) -> dict[str, Any]:
    text = raw_request.strip()
    if text.startswith("{"):
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    return {"request": text}



def infer_symbols(request: str, provided_symbols: list[str] | None = None, watchlist_path: str | Path | None = None) -> list[str]:
    if provided_symbols:
        return provided_symbols
    lowered = request.lower()
    matched: list[str] = []

    def _contains_alias(keyword: str) -> bool:
        alias = keyword.lower().strip()
        if not alias:
            return False
        if re.fullmatch(r"[a-z0-9.=-]{1,4}", alias):
            return re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", lowered) is not None
        return alias in lowered

    for ticker, keywords in SYMBOL_ALIASES.items():
        if any(_contains_alias(keyword) for keyword in keywords):
            matched.append(ticker)
    if matched:
        return matched
    return load_watchlist(watchlist_path)["watchlist"]


def extract_social_search_query(request_text: str, provided_symbols: list[str] | None = None) -> str:
    if provided_symbols:
        return provided_symbols[0]
    query = request_text
    for token in ["스레드", "threads", "threads에서", "찾아줘", "검색", "social", "팔로잉", "목록에서", "알려줘"]:
        query = query.replace(token, " ")
    query = re.sub(r"\s+", " ", query).strip()
    return query or request_text.strip() or "NVDA"


def build_social_search_payload(request_text: str, symbols: list[str], recent_days: int = 14) -> tuple[str, list[str], list[str]]:
    query = extract_social_search_query(request_text, provided_symbols=symbols)
    hits = search_threads_seed_accounts(query, recent_days=recent_days)
    focus = [f"최근 Threads 반응: seed 계정 기준 최근 {recent_days}일 검색 / query={query}"]
    if not hits:
        focus.append(f"최근 Threads 반응: 최근 {recent_days}일 기준 seed 계정 언급 없음")
        next_actions = [
            "검색어를 ticker / 한글 종목명 / 회사명으로 바꿔서 다시 조회",
            "최근 1~2주 언급이 없으면 뉴스/공시 쪽을 먼저 확인",
            "필요하면 코인/미국주식 계정군만 별도로 좁혀서 재검색",
        ]
        summary = f"seed 계정 기준 Threads 최근 반응을 찾았지만 {query} 언급은 없었습니다."
        return summary, focus, next_actions

    for item in hits[:5]:
        focus.append(f"@{item['handle']} / {item['days_ago']}일 전 / {item['text']}")
    next_actions = [
        "가장 최근 언급 계정부터 원문 맥락 확인",
        "같은 종목이 뉴스/공시에도 같이 나오는지 교차검증",
        "최근 1~2주 언급 수가 적으면 모멘텀 약함으로 해석",
    ]
    summary = f"seed 계정 기준 Threads 최근 반응을 정리했습니다: {query}"
    return summary, focus, next_actions


def build_social_signal_line(symbols: list[str], recent_days: int = 14) -> str | None:
    if not symbols:
        return None
    query = symbols[0]
    try:
        hits = search_threads_seed_accounts(query, recent_days=recent_days)
    except Exception:
        return f"Social Signal: seed 계정 검색 실패 / {query} / 공개 Threads 접근 제한"
    if not hits:
        return f"Social Signal: seed 계정 최근 {recent_days}일 {query} 언급 없음"
    top = hits[0]
    return f"Social Signal: @{top['handle']} {top['days_ago']}일 전 / {top['text']}"


def should_include_social_signal(request_text: str, mode: str) -> bool:
    if mode != "brief":
        return False
    lowered = request_text.lower()
    return any(keyword in lowered for keyword in ["소식", "정보", "업데이트", "찾아줘", "알려줘"])




def run_ingest(symbols: list[str], db_path: Path = DEFAULT_DB_PATH) -> dict[str, Any]:
    conn = get_connection(db_path)
    stored_prices = 0
    stored_news = 0
    stored_earnings = 0

    for symbol in symbols:
        snapshot = fetch_price_snapshot(symbol)
        insert_price_snapshot(conn, **snapshot)
        stored_prices += 1
        for news in fetch_symbol_news(symbol):
            insert_news_item(conn, **news)
            stored_news += 1
        earnings_event = fetch_earnings_event(symbol)
        insert_earnings_event(conn, **earnings_event)
        stored_earnings += 1

    conn.commit()
    conn.close()
    return {
        "symbols": len(symbols),
        "prices": len(symbols),
        "stored_prices": stored_prices,
        "stored_news": stored_news,
        "stored_earnings": stored_earnings,
        "db_path": str(db_path),
    }























































def build_response(request: str, runtime_context: dict | None = None, explicit_mode: str | None = None) -> dict[str, Any]:
    runtime_context = runtime_context or {}
    payload = parse_request_payload(request)
    request_text = str(payload.get("request") or request).strip() or "오늘 시장 체크포인트 정리해줘"
    mode = infer_mode(request_text, explicit_mode=explicit_mode or payload.get("mode"))
    watchlist_path = payload.get("watchlist_path") or runtime_context.get("watchlist_path") or DEFAULT_WATCHLIST_PATH
    symbols = infer_symbols(request_text, provided_symbols=payload.get("symbols"), watchlist_path=watchlist_path)
    watchlist_data = load_watchlist(watchlist_path)
    if payload.get("watchlist") is not None:
        watchlist = set(payload.get("watchlist") or [])
    else:
        watchlist = set(watchlist_data["watchlist"])
    if payload.get("portfolio") is not None:
        portfolio = set(payload.get("portfolio") or [])
    else:
        portfolio = set(runtime_context.get("portfolio") or watchlist_data["portfolio"])
    db_path = Path(payload.get("db_path") or runtime_context.get("db_path") or DEFAULT_DB_PATH)

    krx_response = build_krx_mode_response(mode, payload, runtime_context, request_text, symbols)
    if krx_response is not None:
        return krx_response

    us_response = build_us_mode_response(
        mode,
        payload,
        runtime_context,
        request_text,
        symbols,
        watchlist_data,
        watchlist,
        portfolio,
        db_path,
        ingest_func=run_ingest,
        social_search_func=search_threads_seed_accounts,
        sec_filings_fetch_func=fetch_sec_filings_pack,
    )
    if us_response is not None:
        return us_response

    return build_us_core_response(
        mode,
        runtime_context,
        request_text,
        symbols,
        portfolio,
        watchlist,
        db_path,
        helpers={
            "build_symbol_summary": build_symbol_summary,
            "build_compare_payload": build_compare_payload,
            "build_what_changed_payload": build_what_changed_payload,
            "build_overnight_recap_payload": build_overnight_recap_payload,
            "build_why_symbol_payload": build_why_symbol_payload,
            "_infer_brief_phase": _infer_brief_phase,
            "build_market_summary": build_market_summary,
            "build_watchlist_movers": build_watchlist_movers,
            "build_portfolio_brief": build_portfolio_brief,
            "build_catalyst_board": build_catalyst_board,
            "build_earnings_nearby_alert": build_earnings_nearby_alert,
            "build_position_alert": build_position_alert,
            "build_thesis_break_reason": build_thesis_break_reason,
            "build_staleness_warning": build_staleness_warning,
            "build_breaking_line": build_breaking_line,
            "build_social_signal_line": build_social_signal_line,
            "should_include_social_signal": should_include_social_signal,
            "build_yfinance_focus_lines": build_yfinance_focus_lines,
            "fetch_yfinance_market_pack": fetch_yfinance_market_pack,
            "build_technical_snapshot": build_technical_snapshot,
            "build_toss_market_brief": build_toss_market_brief,
            "build_saveticker_brief": build_saveticker_brief,
            "build_compare_view": build_compare_view,
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="stock research agent")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--context-json", default="{}")
    parser.add_argument("--mode", choices=["ingest", "saveticker_sync", "saveticker_breaking", "toss_sync", "day_market", "earnings_preview", "earnings", "sec_filings", "topic_hub", "sector_strength", "watchlist_scan", "market_regime", "oil_vix", "options_flow", "options_sweep", "compare", "what_changed", "overnight_recap", "why_symbol", "threads_view_scan", "social_search", "technical_snapshot", "openbb_quote", "openbb_history", "openbb_profile", "yfinance_pack", "krx_flow_snapshot", "krx_flow_watch", "krx_flow_rank_scan", "krx_flow_rank_watch", "krx_major_flow_watch", "krx_theme_leader_scan", "krx_session_flow_watch", "krx_condition_scan", "krx_symbol_flow_v2", "krx_symbol_brief", "brief", "portfolio_guard", "symbol_review"], default=None)
    parser.add_argument("request", nargs="*")
    args = parser.parse_args()

    request = " ".join(args.request).strip() or "오늘 시장 체크포인트 정리해줘"
    runtime_context = json.loads(args.context_json)
    payload = build_response(request, runtime_context=runtime_context, explicit_mode=args.mode)

    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(payload["summary"])
        print("핵심 포인트:")
        for item in payload["focus"]:
            print(f"- {item}")
        print("다음 액션:")
        for item in payload["next_actions"]:
            print(f"- {item}")


if __name__ == "__main__":
    main()
