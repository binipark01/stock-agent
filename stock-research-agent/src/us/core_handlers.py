"""US core brief/review/compare response handler.

The helper functions still live in main.py for compatibility; main.py
injects them here so this module can own the response assembly without creating
an import cycle.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def build_us_core_response(
    mode: str,
    runtime_context: dict[str, Any],
    request_text: str,
    symbols: list[str],
    portfolio: set[str],
    watchlist: set[str],
    db_path: Path,
    helpers: dict[str, Callable[..., Any]],
) -> dict[str, Any]:
    build_symbol_summary = helpers["build_symbol_summary"]
    build_compare_payload = helpers["build_compare_payload"]
    build_what_changed_payload = helpers["build_what_changed_payload"]
    build_overnight_recap_payload = helpers["build_overnight_recap_payload"]
    build_why_symbol_payload = helpers["build_why_symbol_payload"]
    _infer_brief_phase = helpers["_infer_brief_phase"]
    build_market_summary = helpers["build_market_summary"]
    build_watchlist_movers = helpers["build_watchlist_movers"]
    build_portfolio_brief = helpers["build_portfolio_brief"]
    build_catalyst_board = helpers["build_catalyst_board"]
    build_earnings_nearby_alert = helpers["build_earnings_nearby_alert"]
    build_position_alert = helpers["build_position_alert"]
    build_thesis_break_reason = helpers["build_thesis_break_reason"]
    build_staleness_warning = helpers["build_staleness_warning"]
    build_breaking_line = helpers["build_breaking_line"]
    build_social_signal_line = helpers["build_social_signal_line"]
    should_include_social_signal = helpers["should_include_social_signal"]
    build_yfinance_focus_lines = helpers["build_yfinance_focus_lines"]
    fetch_yfinance_market_pack = helpers["fetch_yfinance_market_pack"]
    build_technical_snapshot = helpers["build_technical_snapshot"]
    build_toss_market_brief = helpers["build_toss_market_brief"]
    build_saveticker_brief = helpers["build_saveticker_brief"]
    build_compare_view = helpers["build_compare_view"]

    summaries = [build_symbol_summary(symbol, portfolio, db_path=db_path) for symbol in symbols]
    focus: list[str] = []
    next_actions: list[str] = []

    if mode == "compare":
        summary = f"비교 관점에서 {', '.join(symbols[:2])} 우선순위를 정리했습니다."
        focus, next_actions = build_compare_payload(symbols, summaries, portfolio)
    elif mode == "what_changed":
        summary = f"최근 저장 기준으로 {', '.join(symbols[:2])} 변화 포인트를 정리했습니다."
        focus, next_actions = build_what_changed_payload(symbols, summaries, portfolio, db_path=db_path)
    elif mode == "overnight_recap":
        summary = f"장후~장전 기준으로 {', '.join(symbols[:2])} 야간 변화 포인트를 정리했습니다."
        focus, next_actions = build_overnight_recap_payload(symbols, summaries, portfolio, db_path=db_path)
    elif mode == "why_symbol":
        summary = f"왜 지금 {symbols[0]}를 봐야 하는지 핵심 이유를 정리했습니다." if symbols else "왜 이 종목을 봐야 하는지 핵심 이유를 정리했습니다."
        focus, next_actions = build_why_symbol_payload(symbols, summaries, portfolio)
    elif mode == "brief":
        brief_phase = _infer_brief_phase(request_text)
        summary_prefix = "장후 브리핑" if brief_phase == "after_close" else "장전 브리핑"
        summary = f"{summary_prefix} 관점에서 {', '.join(symbols)} 체크포인트를 정리했습니다."
        market_summary = build_market_summary(db_path=db_path, portfolio=portfolio, watchlist=watchlist, phase=brief_phase)
        watchlist_movers = build_watchlist_movers(symbols, summaries, portfolio, db_path=db_path, watchlist=watchlist)
        portfolio_brief = build_portfolio_brief(symbols, summaries, portfolio)
        catalyst_board = build_catalyst_board(db_path=db_path, portfolio=portfolio, watchlist=watchlist)
        earnings_alert = build_earnings_nearby_alert(summaries)
        position_alert = build_position_alert(db_path=db_path, portfolio=portfolio)
        thesis_break_reason = build_thesis_break_reason(summaries, portfolio, db_path=db_path)
        staleness_warning = build_staleness_warning(db_path=db_path)
        breaking_line = build_breaking_line(db_path=db_path, portfolio=portfolio, watchlist=watchlist)
        social_signal_line = build_social_signal_line(symbols) if should_include_social_signal(request_text, mode) else None
        yfinance_lines = []
        if any(keyword in request_text.lower() for keyword in ["yfinance", "yf", "야후", "옵션"]):
            for symbol in symbols[:2]:
                yfinance_lines.extend(build_yfinance_focus_lines(fetch_yfinance_market_pack(symbol), max_lines=4))
        technical_snapshots = [build_technical_snapshot(symbol) for symbol in symbols[:2]]
        technical_lines = [snap["brief_line"] for snap in technical_snapshots]
        toss_brief_lines = [line[2:] if line.startswith('- ') else line for line in build_toss_market_brief(db_path, portfolio_symbols=portfolio).splitlines()[1:]]
        saveticker_brief_lines = [line[2:] if line.startswith('- ') else line for line in build_saveticker_brief(db_path, portfolio_symbols=portfolio).splitlines()[1:]]
        if "[토스증권 주요 뉴스]" in toss_brief_lines:
            split_idx = toss_brief_lines.index("[토스증권 주요 뉴스]")
            toss_index_lines = toss_brief_lines[:split_idx]
            toss_news_lines = toss_brief_lines[split_idx + 1 : split_idx + 4]
        else:
            toss_index_lines = toss_brief_lines[:3]
            toss_news_lines = []
        saveticker_news_lines = saveticker_brief_lines[1:4] if len(saveticker_brief_lines) > 1 else []
        focus = [
            market_summary,
        ] + ([watchlist_movers] if watchlist_movers else []) + ([portfolio_brief] if portfolio_brief else []) + ([catalyst_board] if catalyst_board else []) + ([earnings_alert] if earnings_alert else []) + ([position_alert] if position_alert else []) + ([thesis_break_reason] if thesis_break_reason else []) + ([staleness_warning] if staleness_warning else []) + ([social_signal_line] if social_signal_line else []) + yfinance_lines + ([breaking_line] if breaking_line else []) + technical_lines + [
            f"{item['symbol']} 강세: {item['bullish']}" for item in summaries[:2]
        ] + [
            f"{item['symbol']} 뉴스: {item['headline']}" for item in summaries[:2]
        ] + [
            f"{item['symbol']} 실적: {item['earnings']}" for item in summaries[:2]
        ] + toss_index_lines + toss_news_lines + saveticker_news_lines
        next_actions = [
            "장전 체크: 개장 전 실적 일정과 주요 뉴스만 다시 확인",
            "보유 미국주 종목이면 thesis와 충돌하는 이벤트가 있는지 체크",
            "급등락 시 가격보다 이유와 매크로 변수부터 기록",
        ] if brief_phase == "pre_market" else [
            "장후 체크: 애프터마켓 가격반응과 가이던스 문구를 먼저 확인",
            "마감 이후 나온 실적/뉴스가 내일 시가에 미칠 영향 정리",
            "보유 종목은 마감 후 thesis 변화 여부를 짧게 메모",
        ]
    elif mode == "portfolio_guard":
        summary = f"포트폴리오 가드 관점에서 {', '.join(symbols)} 재점검 포인트를 정리했습니다."
        focus = [f"{item['symbol']} 위험도={item['risk_level']} / {item['risk']} / {item['bearish']} / 뉴스={item['headline']} / 실적={item['earnings']}" for item in summaries]
        next_actions = [
            "보유 미국주 thesis_note와 최근 악재 뉴스 충돌 여부 확인",
            "실적 발표 2일 전 알림 우선순위 높이기",
            "소셜 시그널은 참고만 하고 뉴스/실적/가이던스로 교차검증",
        ]
    elif mode == "compare":
        focus, summary = build_compare_view(symbols, summaries, portfolio, db_path=db_path, watchlist=watchlist)
        next_actions = [
            "1등 종목부터 뉴스/실적/차트 순서로 다시 확인",
            "두 종목 모두 좋으면 먼저 볼 종목과 나중에 볼 종목만 분리",
            "비교 결과는 최신 속보가 들어오면 바로 바뀔 수 있으니 재실행",
        ]
    else:
        summary = f"종목 리뷰 관점에서 {', '.join(symbols)} 핵심 포인트를 정리했습니다."
        focus = [f"{item['symbol']} 촉매: {item['catalyst']} / 리스크: {item['bearish']} / 뉴스: {item['headline']} / 실적: {item['earnings']}" for item in summaries]
        next_actions = [
            "강세 논리와 약세 논리를 1:1로 적어보기",
            "미국장 기준 가장 가까운 이벤트 일정 확인",
            "실제 매매보다 판단 근거 업데이트를 우선",
        ]

    return {
        "agent": "stock-research-agent",
        "mode": mode,
        "summary": summary,
        "symbols": symbols,
        "focus": focus,
        "next_actions": next_actions,
        "features": runtime_context.get("features", []),
    }
