"""Facade for US/global stock mode handlers.

This module keeps the public build_us_mode_response entrypoint stable while
sub-handlers are split by domain.  main.py should call only this facade.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

try:
    from .social.threads import search_threads_seed_accounts
    from .data_handlers import build_us_data_response, build_social_search_payload, extract_social_search_query
    from .openbb_handlers import build_us_openbb_response
    from .options_handlers import build_us_options_response
    from .sector_handlers import build_us_sector_response
except ImportError:  # direct script execution
    from us.social.threads import search_threads_seed_accounts
    from us.data_handlers import build_us_data_response, build_social_search_payload, extract_social_search_query
    from us.openbb_handlers import build_us_openbb_response
    from us.options_handlers import build_us_options_response
    from us.sector_handlers import build_us_sector_response

US_MODE_HANDLERS = {
    "day_market",
    "earnings",
    "earnings_preview",
    "market_regime",
    "oil_vix",
    "openbb_history",
    "openbb_profile",
    "openbb_quote",
    "options_flow",
    "options_sweep",
    "saveticker_breaking",
    "saveticker_sync",
    "sec_filings",
    "sector_strength",
    "sector_intelligence",
    "premarket_plan",
    "closing_review",
    "social_search",
    "technical_snapshot",
    "threads_view_scan",
    "topic_hub",
    "toss_sync",
    "watchlist_scan",
    "yfinance_pack",
    "ingest",
}


def build_us_mode_response(
    mode: str,
    payload: dict[str, Any],
    runtime_context: dict[str, Any],
    request_text: str,
    symbols: list[str],
    watchlist_data: dict[str, Any],
    watchlist: set[str],
    portfolio: set[str],
    db_path: Path,
    ingest_func: Callable[[list[str], Path], dict[str, Any]] | None = None,
    social_search_func=search_threads_seed_accounts,
    sec_filings_fetch_func=None,
) -> dict[str, Any] | None:
    for response in (
        build_us_openbb_response(mode, payload, runtime_context, request_text, symbols),
        build_us_sector_response(mode, payload, runtime_context, request_text, symbols, watchlist_data),
        build_us_options_response(mode, payload, runtime_context, request_text, symbols, watchlist_data),
        build_us_data_response(
            mode,
            payload,
            runtime_context,
            request_text,
            symbols,
            portfolio,
            watchlist,
            db_path,
            ingest_func=ingest_func,
            social_search_func=social_search_func,
            sec_filings_fetch_func=sec_filings_fetch_func,
        ),
    ):
        if response is not None:
            return response
    return None
