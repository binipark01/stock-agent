"""US options mode response handlers."""
from __future__ import annotations

from typing import Any

try:
    from .options.flow import build_options_flow_report, build_watchlist_options_sweep
    from ..watchlists import filter_watchlist_scope, flatten_watchlist_symbols, infer_watchlist_scope
except ImportError:  # direct script execution
    from us.options.flow import build_options_flow_report, build_watchlist_options_sweep
    from watchlists import filter_watchlist_scope, flatten_watchlist_symbols, infer_watchlist_scope


def build_us_options_response(
    mode: str,
    payload: dict[str, Any],
    runtime_context: dict[str, Any],
    request_text: str,
    symbols: list[str],
    watchlist_data: dict[str, Any],
) -> dict[str, Any] | None:
    if mode == "options_sweep":
        scope = payload.get("watchlist_scope") or payload.get("list") or runtime_context.get("watchlist_scope") or infer_watchlist_scope(request_text, watchlist_data)
        scoped_watchlist_data = filter_watchlist_scope(watchlist_data, scope)
        sweep_symbols = payload.get("symbols") or flatten_watchlist_symbols(scoped_watchlist_data)
        options_payloads = payload.get("options_payloads") or runtime_context.get("options_payloads") or {}
        sweep_report = build_watchlist_options_sweep(sweep_symbols, payloads=options_payloads, limit=int(payload.get("limit") or runtime_context.get("limit") or 12))
        focus_lines = list(sweep_report["focus_lines"])
        if scope:
            focus_lines.insert(0, f"옵션 스윕 범위: {scope}")
        return {
            "agent": "stock-research-agent",
            "mode": mode,
            "summary": sweep_report["summary"] if not scope else f"{scope} options sweep - {sweep_report['summary']}",
            "symbols": sweep_report["symbols"],
            "focus": focus_lines,
            "next_actions": sweep_report["next_actions"],
            "features": list(dict.fromkeys([*runtime_context.get("features", []), "options_sweep", "options_flow"])),
            "data": {"options_sweep": sweep_report},
        }


    if mode == "options_flow":
        options_report = build_options_flow_report(symbols[0] if symbols else "UNKNOWN", cboe_payload=payload.get("options_payload") or runtime_context.get("options_payload"))
        return {
            "agent": "stock-research-agent",
            "mode": mode,
            "summary": options_report["summary"],
            "symbols": symbols,
            "focus": options_report["focus_lines"],
            "next_actions": options_report["next_actions"],
            "features": list(dict.fromkeys([*runtime_context.get("features", []), "options_flow"])),
            "data": {"options_flow": options_report},
        }


    return None
