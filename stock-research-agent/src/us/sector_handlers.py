"""US watchlist, sector-strength, regime, and risk mode handlers."""
from __future__ import annotations

from typing import Any

try:
    from .sector.strength import build_market_regime_report, build_oil_vix_report, build_sector_strength_report, fetch_sector_strength_quotes
    from ..watchlists import build_watchlist_scan, filter_watchlist_scope, flatten_watchlist_symbols, infer_watchlist_scope
except ImportError:  # direct script execution
    from us.sector.strength import build_market_regime_report, build_oil_vix_report, build_sector_strength_report, fetch_sector_strength_quotes
    from watchlists import build_watchlist_scan, filter_watchlist_scope, flatten_watchlist_symbols, infer_watchlist_scope


def build_us_sector_response(
    mode: str,
    payload: dict[str, Any],
    runtime_context: dict[str, Any],
    request_text: str,
    symbols: list[str],
    watchlist_data: dict[str, Any],
) -> dict[str, Any] | None:
    if mode == "watchlist_scan":
        scope = payload.get("watchlist_scope") or payload.get("list") or runtime_context.get("watchlist_scope") or infer_watchlist_scope(request_text, watchlist_data)
        scoped_watchlist_data = filter_watchlist_scope(watchlist_data, scope)
        watchlist_quotes = payload.get("watchlist_quotes") or payload.get("sector_quotes") or runtime_context.get("watchlist_quotes") or runtime_context.get("sector_quotes")
        if not watchlist_quotes:
            watch_symbols = list(dict.fromkeys(["SPY", *flatten_watchlist_symbols(scoped_watchlist_data)]))
            watchlist_quotes = fetch_sector_strength_quotes(watch_symbols)
        scan = build_watchlist_scan(
            scoped_watchlist_data,
            watchlist_quotes,
            collected_at=payload.get("collected_at") or runtime_context.get("collected_at"),
        )
        focus_lines = list(scan["focus_lines"])
        if scope:
            focus_lines.insert(0, f"관심종목 범위: {scope}")
        return {
            "agent": "stock-research-agent",
            "mode": mode,
            "summary": scan["summary"] if not scope else f"{scope} watchlist - {scan['summary']}",
            "symbols": flatten_watchlist_symbols(scoped_watchlist_data),
            "focus": focus_lines,
            "next_actions": scan["next_actions"],
            "features": list(dict.fromkeys([*runtime_context.get("features", []), "watchlist_scan"])),
            "data": {"watchlist_scan": scan},
        }


    if mode == "market_regime":
        regime_quotes = payload.get("sector_quotes") or runtime_context.get("sector_quotes")
        if not regime_quotes:
            regime_quotes = fetch_sector_strength_quotes()
        regime_report = build_market_regime_report(
            regime_quotes,
            collected_at=payload.get("collected_at") or runtime_context.get("collected_at"),
        )
        return {
            "agent": "stock-research-agent",
            "mode": mode,
            "summary": regime_report["summary"],
            "symbols": symbols,
            "focus": regime_report["focus_lines"],
            "next_actions": regime_report["next_actions"],
            "features": list(dict.fromkeys([*runtime_context.get("features", []), "market_regime"])),
            "data": {"market_regime": regime_report},
        }


    if mode == "oil_vix":
        oil_vix_quotes = payload.get("sector_quotes") or runtime_context.get("sector_quotes")
        if not oil_vix_quotes:
            oil_vix_quotes = fetch_sector_strength_quotes()
        oil_vix_report = build_oil_vix_report(
            oil_vix_quotes,
            collected_at=payload.get("collected_at") or runtime_context.get("collected_at"),
        )
        return {
            "agent": "stock-research-agent",
            "mode": mode,
            "summary": oil_vix_report["summary"],
            "symbols": symbols,
            "focus": oil_vix_report["focus_lines"],
            "next_actions": oil_vix_report["next_actions"],
            "features": list(dict.fromkeys([*runtime_context.get("features", []), "oil_vix"])),
            "data": {"oil_vix": oil_vix_report},
        }


    if mode == "sector_strength":
        sector_quotes = payload.get("sector_quotes") or runtime_context.get("sector_quotes")
        if not sector_quotes:
            sector_quotes = fetch_sector_strength_quotes()
        report = build_sector_strength_report(
            sector_quotes,
            collected_at=payload.get("collected_at") or runtime_context.get("collected_at"),
        )
        features = list(dict.fromkeys([*runtime_context.get("features", []), "sector_strength", "market_regime"]))
        return {
            "agent": "stock-research-agent",
            "mode": mode,
            "summary": report["summary"],
            "symbols": symbols,
            "focus": report["focus_lines"],
            "next_actions": report["next_actions"],
            "features": features,
            "data": {"sector_strength": report},
        }


    return None
