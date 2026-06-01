"""US OpenBB mode response handlers."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

try:
    from .market_data.openbb import build_openbb_history, build_openbb_history_response, build_openbb_profile, build_openbb_profile_response, build_openbb_quote, build_openbb_quote_response
except ImportError:  # direct script execution
    from us.market_data.openbb import build_openbb_history, build_openbb_history_response, build_openbb_profile, build_openbb_profile_response, build_openbb_quote, build_openbb_quote_response


def _extract_openbb_history_dates(request_text: str, payload: dict[str, Any], runtime_context: dict[str, Any]) -> tuple[str, str | None]:
    start_date = payload.get("start_date") or payload.get("start") or runtime_context.get("start_date") or runtime_context.get("start")
    end_date = payload.get("end_date") or payload.get("end") or runtime_context.get("end_date") or runtime_context.get("end")
    dates = re.findall(r"20\d{2}-\d{2}-\d{2}", request_text)
    if not start_date and dates:
        start_date = dates[0]
    if not end_date and len(dates) > 1:
        end_date = dates[1]
    if not start_date:
        start_date = (datetime.now(timezone.utc) - timedelta(days=365)).date().isoformat()
    return str(start_date), str(end_date) if end_date else None


def build_us_openbb_response(
    mode: str,
    payload: dict[str, Any],
    runtime_context: dict[str, Any],
    request_text: str,
    symbols: list[str],
) -> dict[str, Any] | None:
    if mode == "openbb_quote":
        openbb_quote = payload.get("openbb_quote") or runtime_context.get("openbb_quote")
        if not openbb_quote:
            openbb_quote = build_openbb_quote(
                symbols[0],
                python_path=payload.get("openbb_python") or runtime_context.get("openbb_python"),
            )
        response = build_openbb_quote_response(openbb_quote)
        response["features"] = list(dict.fromkeys([*runtime_context.get("features", []), *response.get("features", [])]))
        return response


    if mode == "openbb_history":
        openbb_history = payload.get("openbb_history") or runtime_context.get("openbb_history")
        if not openbb_history:
            start_date, end_date = _extract_openbb_history_dates(request_text, payload, runtime_context)
            openbb_history = build_openbb_history(
                symbols[0],
                start_date=start_date,
                end_date=end_date,
                python_path=payload.get("openbb_python") or runtime_context.get("openbb_python"),
            )
        response = build_openbb_history_response(openbb_history)
        response["features"] = list(dict.fromkeys([*runtime_context.get("features", []), *response.get("features", [])]))
        return response


    if mode == "openbb_profile":
        openbb_profile = payload.get("openbb_profile") or runtime_context.get("openbb_profile")
        if not openbb_profile:
            openbb_profile = build_openbb_profile(
                symbols[0],
                python_path=payload.get("openbb_python") or runtime_context.get("openbb_python"),
            )
        response = build_openbb_profile_response(openbb_profile)
        response["features"] = list(dict.fromkeys([*runtime_context.get("features", []), *response.get("features", [])]))
        return response


    return None
