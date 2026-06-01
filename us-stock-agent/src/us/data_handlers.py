"""Facade for US data/news/social/earnings/technical handlers."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

try:
    from .social.threads import search_threads_seed_accounts
    from .earnings_handlers import build_us_earnings_response
    from .ingest_handlers import build_us_ingest_response
    from .market_data_handlers import build_us_market_data_response
    from .news_handlers import build_us_news_response
    from .social_handlers import build_social_search_payload, build_us_social_response, extract_social_search_query
    from .technical_handlers import build_us_technical_response
except ImportError:  # direct script execution
    from us.social.threads import search_threads_seed_accounts
    from us.earnings_handlers import build_us_earnings_response
    from us.ingest_handlers import build_us_ingest_response
    from us.market_data_handlers import build_us_market_data_response
    from us.news_handlers import build_us_news_response
    from us.social_handlers import build_social_search_payload, build_us_social_response, extract_social_search_query
    from us.technical_handlers import build_us_technical_response


def build_us_data_response(
    mode: str,
    payload: dict[str, Any],
    runtime_context: dict[str, Any],
    request_text: str,
    symbols: list[str],
    portfolio: set[str],
    watchlist: set[str],
    db_path: Path,
    ingest_func: Callable[[list[str], Path], dict[str, Any]] | None = None,
    social_search_func=search_threads_seed_accounts,
    sec_filings_fetch_func=None,
) -> dict[str, Any] | None:
    for response in (
        build_us_market_data_response(mode, payload, runtime_context, request_text, symbols, db_path),
        build_us_news_response(mode, payload, runtime_context, symbols, portfolio, watchlist, db_path, sec_filings_fetch_func=sec_filings_fetch_func),
        build_us_ingest_response(mode, runtime_context, symbols, db_path, ingest_func=ingest_func),
        build_us_earnings_response(mode, runtime_context, symbols, db_path),
        build_us_technical_response(mode, runtime_context, symbols),
        build_us_social_response(mode, payload, runtime_context, request_text, symbols, social_search_func=social_search_func),
    ):
        if response is not None:
            return response
    return None
