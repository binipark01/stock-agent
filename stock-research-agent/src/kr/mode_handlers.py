"""Mode handlers for KRX/Korean-stock responses.

This module keeps KRX-specific response assembly out of main.py.  It is
intentionally thin: data collection still lives in dedicated Kiwoom/KRX modules,
and each handler returns the same response shape that build_response expects.
"""
from __future__ import annotations

from typing import Any

try:
    from .kiwoom.client import build_kiwoom_data_client
    from .condition.engine import build_krx_condition_scan_response, run_krx_condition_scan
    from .condition.universe import build_condition_universe_from_rank_scan
    from .theme.leader_scan import build_krx_theme_leader_report, build_krx_theme_leader_response, fetch_krx_theme_quotes
    from .session.flow_watch import build_krx_session_flow_watch_report, build_krx_session_flow_watch_response
    from .flow.symbol_flow import build_krx_symbol_flow_snapshot_v2, format_krx_symbol_flow_snapshot_v2
    from .flow.major_watch import build_krx_major_flow_watch_report, build_krx_major_flow_watch_response
    from .news.symbol_supply_news import build_krx_symbol_supply_news_report, format_krx_symbol_supply_news_report
    from .flow.kiwoom import build_krx_flow_rank_response, build_krx_flow_rank_scan, build_krx_flow_trade_candidates, build_krx_flow_rank_watch_report, build_krx_flow_rank_watch_response, build_krx_flow_response, build_krx_flow_snapshot, build_krx_flow_watch_report, build_krx_flow_watch_response
except ImportError:  # direct script execution
    from kr.kiwoom.client import build_kiwoom_data_client
    from kr.condition.engine import build_krx_condition_scan_response, run_krx_condition_scan
    from kr.condition.universe import build_condition_universe_from_rank_scan
    from kr.theme.leader_scan import build_krx_theme_leader_report, build_krx_theme_leader_response, fetch_krx_theme_quotes
    from kr.session.flow_watch import build_krx_session_flow_watch_report, build_krx_session_flow_watch_response
    from kr.flow.symbol_flow import build_krx_symbol_flow_snapshot_v2, format_krx_symbol_flow_snapshot_v2
    from kr.flow.major_watch import build_krx_major_flow_watch_report, build_krx_major_flow_watch_response
    from kr.news.symbol_supply_news import build_krx_symbol_supply_news_report, format_krx_symbol_supply_news_report
    from kr.flow.kiwoom import build_krx_flow_rank_response, build_krx_flow_rank_scan, build_krx_flow_trade_candidates, build_krx_flow_rank_watch_report, build_krx_flow_rank_watch_response, build_krx_flow_response, build_krx_flow_snapshot, build_krx_flow_watch_report, build_krx_flow_watch_response

KRX_MODE_HANDLERS = {
    "krx_condition_scan",
    "krx_session_flow_watch",
    "krx_symbol_brief",
    "krx_symbol_flow_v2",
    "krx_flow_snapshot",
    "krx_flow_watch",
    "krx_flow_rank_scan",
    "krx_flow_rank_watch",
    "krx_theme_leader_scan",
    "krx_major_flow_watch",
}


def _merge_features(runtime_context: dict[str, Any], *features: str) -> list[str]:
    return list(dict.fromkeys([*runtime_context.get("features", []), *features]))


def _first_symbol(payload: dict[str, Any], symbols: list[str]) -> str:
    provided = payload.get("symbols") or symbols
    if not provided:
        raise ValueError("KRX mode requires at least one symbol")
    return provided[0]



def build_krx_theme_leader_scan_mode_response(payload: dict[str, Any], runtime_context: dict[str, Any]) -> dict[str, Any]:
    report = payload.get("krx_theme_leader_scan") or runtime_context.get("krx_theme_leader_scan")
    if not report:
        watchlist_data = payload.get("watchlist_data") or runtime_context.get("watchlist_data")
        quotes = (
            payload.get("krx_theme_quotes")
            or runtime_context.get("krx_theme_quotes")
            or payload.get("theme_quotes")
            or runtime_context.get("theme_quotes")
            or {}
        )
        if not quotes:
            quotes = fetch_krx_theme_quotes(watchlist_data)
        report = build_krx_theme_leader_report(
            watchlist_data,
            quotes,
            collected_at=payload.get("collected_at") or runtime_context.get("collected_at"),
        )
    response = build_krx_theme_leader_response(report)
    response["features"] = _merge_features(runtime_context, "krx", "theme_leader")
    return response

def build_krx_condition_scan_mode_response(
    payload: dict[str, Any],
    runtime_context: dict[str, Any],
    request_text: str,
    symbols: list[str],
) -> dict[str, Any]:
    condition_report = payload.get("krx_condition_scan_report") or runtime_context.get("krx_condition_scan_report")
    if not condition_report:
        condition_universe = None
        stocks = (
            payload.get("krx_condition_universe")
            or payload.get("stocks")
            or runtime_context.get("krx_condition_universe")
            or runtime_context.get("stocks")
            or []
        )
        if isinstance(stocks, dict) and "stocks" in stocks:
            condition_universe = stocks
            stocks = stocks.get("stocks") or []
        if not stocks:
            rank_scan = (
                payload.get("krx_flow_rank_scan")
                or runtime_context.get("krx_flow_rank_scan")
                or (payload.get("data") or {}).get("krx_flow_rank_scan")
            )
            trade_candidates = payload.get("trade_candidates") or runtime_context.get("trade_candidates")
            if not rank_scan:
                client = build_kiwoom_data_client()
                cfg = client.config
                rank_scan = build_krx_flow_rank_scan(
                    client,
                    collected_at=payload.get("collected_at") or runtime_context.get("collected_at"),
                )
                rank_scan.setdefault("source_environment", getattr(cfg, "env", None))
                rank_scan.setdefault("base_url", getattr(cfg, "rest_base_url", None))
            if trade_candidates is None:
                trade_candidates = build_krx_flow_trade_candidates(rank_scan)
            condition_universe = build_condition_universe_from_rank_scan(rank_scan, candidates=trade_candidates)
            stocks = condition_universe.get("stocks") or []
        condition_names = payload.get("condition_names") or runtime_context.get("condition_names")
        condition_report = run_krx_condition_scan(
            stocks,
            condition_names=condition_names,
            collected_at=runtime_context.get("collected_at") or payload.get("collected_at") or (condition_universe or {}).get("collected_at"),
        )
        if condition_universe:
            condition_report["condition_universe"] = condition_universe
            condition_report["source_environment"] = condition_universe.get("source_environment")
            condition_report["base_url"] = condition_universe.get("base_url")
            condition_report["caveats"] = list(dict.fromkeys([*(condition_report.get("caveats") or []), *(condition_universe.get("caveats") or [])]))
    response = build_krx_condition_scan_response(condition_report)
    response["request"] = request_text
    response["symbols"] = symbols
    return response


def build_krx_session_flow_watch_mode_response(
    payload: dict[str, Any],
    runtime_context: dict[str, Any],
) -> dict[str, Any]:
    session_report = payload.get("krx_session_flow_watch_report") or runtime_context.get("krx_session_flow_watch_report")
    session_snapshots = (
        payload.get("krx_session_flow_snapshots")
        or payload.get("session_snapshots")
        or runtime_context.get("krx_session_flow_snapshots")
        or runtime_context.get("session_snapshots")
    )
    if not session_report:
        session_report = build_krx_session_flow_watch_report(session_snapshots or [])
    response = build_krx_session_flow_watch_response(session_report)
    response["features"] = _merge_features(runtime_context, *response.get("features", []))
    return response


def build_krx_symbol_brief_mode_response(
    payload: dict[str, Any],
    runtime_context: dict[str, Any],
    symbols: list[str],
) -> dict[str, Any]:
    report = payload.get("krx_symbol_supply_news_report") or runtime_context.get("krx_symbol_supply_news_report")
    if not report:
        client = build_kiwoom_data_client()
        cfg = client.config
        report = build_krx_symbol_supply_news_report(
            _first_symbol(payload, symbols),
            client=client,
            as_of_date=payload.get("as_of_date") or runtime_context.get("as_of_date"),
            flow_snapshot=payload.get("krx_symbol_flow_snapshot_v2") or runtime_context.get("krx_symbol_flow_snapshot_v2"),
            integration=payload.get("naver_stock_integration") or runtime_context.get("naver_stock_integration"),
            news_items=payload.get("naver_stock_news") or runtime_context.get("naver_stock_news"),
        )
    return {
        "agent": "stock-research-agent",
        "mode": "krx_symbol_brief",
        "summary": f"{report.get('name')}({report.get('symbol')}) 수급+뉴스: {report.get('supply_signal')}",
        "symbols": [report.get("symbol")],
        "focus": format_krx_symbol_supply_news_report(report),
        "next_actions": report.get("next_actions") or [],
        "features": _merge_features(runtime_context, "krx_symbol_supply_news_template", "kiwoom_symbol_flow_v2", "naver_stock_news"),
        "krx_symbol_supply_news_report": report,
    }


def build_krx_symbol_flow_v2_mode_response(
    payload: dict[str, Any],
    runtime_context: dict[str, Any],
    symbols: list[str],
) -> dict[str, Any]:
    snapshot = payload.get("krx_symbol_flow_snapshot_v2") or runtime_context.get("krx_symbol_flow_snapshot_v2")
    if not snapshot:
        client = build_kiwoom_data_client()
        cfg = client.config
        snapshot = build_krx_symbol_flow_snapshot_v2(
            client,
            _first_symbol(payload, symbols),
            as_of_date=payload.get("as_of_date") or runtime_context.get("as_of_date"),
        )
    signal = snapshot.get("supply_signal") or "수급확인"
    return {
        "agent": "stock-research-agent",
        "mode": "krx_symbol_flow_v2",
        "summary": f"{snapshot.get('symbol')} Kiwoom 개별종목 수급 v2: {signal}",
        "symbols": [snapshot.get("symbol")],
        "focus": format_krx_symbol_flow_snapshot_v2(snapshot),
        "next_actions": [
            "당일 기관/외인 data_dates가 requested_date와 같은지 먼저 확인",
            "프로그램 순매수/순매도는 ka90008 개별종목 시간별 row로 확인",
            "랭킹 bucket 값은 후보 발굴용으로만 사용하고 개별 수급 판단 근거로 쓰지 않기",
        ],
        "features": _merge_features(runtime_context, "kiwoom_symbol_flow_v2", "kiwoom_official_tr_examples"),
        "krx_symbol_flow_snapshot_v2": snapshot,
    }



def build_krx_major_flow_watch_mode_response(payload: dict[str, Any], runtime_context: dict[str, Any]) -> dict[str, Any]:
    report = payload.get("krx_major_flow_watch_report") or runtime_context.get("krx_major_flow_watch_report")
    if not report:
        snapshots = (
            payload.get("krx_major_flow_snapshots")
            or runtime_context.get("krx_major_flow_snapshots")
            or payload.get("snapshots")
            or runtime_context.get("snapshots")
        )
        symbols = payload.get("krx_major_symbols") or runtime_context.get("krx_major_symbols")
        client = None if snapshots else build_kiwoom_data_client()
        report = build_krx_major_flow_watch_report(
            client,
            symbols=symbols,
            snapshots=snapshots,
            collected_at=payload.get("collected_at") or runtime_context.get("collected_at"),
        )
    response = build_krx_major_flow_watch_response(report)
    response["features"] = _merge_features(runtime_context, *response.get("features", []))
    return response

def build_krx_flow_rank_watch_mode_response(payload: dict[str, Any], runtime_context: dict[str, Any]) -> dict[str, Any]:
    rank_watch_report = payload.get("krx_flow_rank_watch_report") or runtime_context.get("krx_flow_rank_watch_report")
    previous_rank_scan = payload.get("previous_krx_flow_rank_scan") or runtime_context.get("previous_krx_flow_rank_scan")
    current_rank_scan = payload.get("current_krx_flow_rank_scan") or runtime_context.get("current_krx_flow_rank_scan")
    if not rank_watch_report:
        if not current_rank_scan:
            current_rank_scan = build_krx_flow_rank_scan(collected_at=payload.get("collected_at") or runtime_context.get("collected_at"))
        if not previous_rank_scan:
            previous_rank_scan = {"mode": "krx_flow_rank_scan", "sections": {}, "collected_at": None}
        rank_watch_report = build_krx_flow_rank_watch_report(previous_rank_scan, current_rank_scan)
    response = build_krx_flow_rank_watch_response(rank_watch_report)
    response["features"] = _merge_features(runtime_context, *response.get("features", []))
    return response


def build_krx_flow_rank_scan_mode_response(payload: dict[str, Any], runtime_context: dict[str, Any]) -> dict[str, Any]:
    rank_scan = payload.get("krx_flow_rank_scan") or runtime_context.get("krx_flow_rank_scan")
    if not rank_scan:
        rank_scan = build_krx_flow_rank_scan(collected_at=payload.get("collected_at") or runtime_context.get("collected_at"))
    response = build_krx_flow_rank_response(rank_scan)
    response["features"] = _merge_features(runtime_context, *response.get("features", []))
    return response


def build_krx_flow_snapshot_or_watch_mode_response(
    mode: str,
    payload: dict[str, Any],
    runtime_context: dict[str, Any],
    symbols: list[str],
) -> dict[str, Any]:
    watch_report = payload.get("krx_flow_watch_report") or runtime_context.get("krx_flow_watch_report")
    previous_snapshot = payload.get("previous_krx_flow_snapshot") or runtime_context.get("previous_krx_flow_snapshot")
    current_snapshot = payload.get("current_krx_flow_snapshot") or runtime_context.get("current_krx_flow_snapshot")
    if mode == "krx_flow_watch" and (watch_report or (previous_snapshot and current_snapshot)):
        if not watch_report:
            watch_report = build_krx_flow_watch_report(previous_snapshot, current_snapshot)
        response = build_krx_flow_watch_response(watch_report)
        response["features"] = _merge_features(runtime_context, *response.get("features", []))
        return response
    snapshot = payload.get("krx_flow_snapshot") or runtime_context.get("krx_flow_snapshot")
    if not snapshot:
        snapshot_symbols = payload.get("symbols") or symbols
        snapshot = build_krx_flow_snapshot(
            snapshot_symbols,
            collected_at=payload.get("collected_at") or runtime_context.get("collected_at"),
        )
    response = build_krx_flow_response(snapshot)
    if mode == "krx_flow_watch":
        response["mode"] = "krx_flow_watch"
        response["summary"] = response["summary"].replace("스냅샷", "감시 준비")
        response["features"] = list(dict.fromkeys([*response.get("features", []), "kiwoom_websocket", "krx_flow_watch"]))
        response["next_actions"] = [
            "WebSocket 0B(체결)·0D(호가)·0w(종목프로그램)을 등록해 몇 분 단위 변화만 요약",
            "투자자별 순매수는 REST TR 재조회 기준시각을 붙여 비교하고 실시간으로 과장하지 않기",
            *response.get("next_actions", []),
        ]
    response["features"] = _merge_features(runtime_context, *response.get("features", []))
    return response


def build_krx_mode_response(
    mode: str,
    payload: dict[str, Any],
    runtime_context: dict[str, Any],
    request_text: str,
    symbols: list[str],
) -> dict[str, Any] | None:
    if mode == "krx_flow_rank_watch":
        return build_krx_flow_rank_watch_mode_response(payload, runtime_context)
    if mode == "krx_flow_rank_scan":
        return build_krx_flow_rank_scan_mode_response(payload, runtime_context)
    if mode == "krx_major_flow_watch":
        return build_krx_major_flow_watch_mode_response(payload, runtime_context)
    if mode == "krx_theme_leader_scan":
        return build_krx_theme_leader_scan_mode_response(payload, runtime_context)
    if mode in {"krx_flow_snapshot", "krx_flow_watch"}:
        return build_krx_flow_snapshot_or_watch_mode_response(mode, payload, runtime_context, symbols)
    if mode == "krx_condition_scan":
        return build_krx_condition_scan_mode_response(payload, runtime_context, request_text, symbols)
    if mode == "krx_session_flow_watch":
        return build_krx_session_flow_watch_mode_response(payload, runtime_context)
    if mode == "krx_symbol_brief":
        return build_krx_symbol_brief_mode_response(payload, runtime_context, symbols)
    if mode == "krx_symbol_flow_v2":
        return build_krx_symbol_flow_v2_mode_response(payload, runtime_context, symbols)
    return None
