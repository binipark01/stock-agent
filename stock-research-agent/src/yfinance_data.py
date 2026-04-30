from __future__ import annotations

from datetime import datetime, timezone
import contextlib
import io
import json
import math
from typing import Any
import urllib.parse
import urllib.request


def _import_yfinance():
    try:
        import yfinance as yf  # type: ignore
    except Exception:
        return None
    return yf


def _safe_get(mapping: Any, *keys: str) -> Any:
    for key in keys:
        try:
            if isinstance(mapping, dict):
                value = mapping.get(key)
            elif hasattr(mapping, "get"):
                value = mapping.get(key)  # yfinance FastInfo is mapping-like but not dict
            else:
                value = None
            if value is not None:
                return value
        except Exception:
            pass
        try:
            value = getattr(mapping, key)
            if value is not None:
                return value
        except Exception:
            continue
    return None


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        numeric = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
    if math.isnan(numeric) or math.isinf(numeric):
        return None
    return numeric


def _safe_attr(obj: Any, attr: str, default: Any = None, warnings: list[str] | None = None) -> Any:
    try:
        return getattr(obj, attr)
    except Exception as exc:
        if warnings is not None:
            warnings.append(f"{attr} unavailable: {exc}")
        return default


def _to_int(value: Any) -> int:
    numeric = _to_float(value)
    return int(numeric) if numeric is not None else 0


def _round_or_none(value: Any, digits: int = 2) -> float | None:
    numeric = _to_float(value)
    if numeric is None:
        return None
    return round(numeric, digits)


def _table_to_records(table: Any, limit: int = 5) -> list[dict[str, Any]]:
    if table is None:
        return []
    try:
        if bool(getattr(table, "empty", False)):
            return []
    except Exception:
        pass
    try:
        head = table.head(limit) if hasattr(table, "head") else table
        if hasattr(head, "reset_index"):
            head = head.reset_index()
        if hasattr(head, "to_dict"):
            records = head.to_dict("records")
            if isinstance(records, list):
                return [dict(item) for item in records[:limit] if isinstance(item, dict)]
    except Exception:
        return []
    if isinstance(table, list):
        return [dict(item) for item in table[:limit] if isinstance(item, dict)]
    if isinstance(table, dict):
        return [dict(table)]
    return []


def _series_to_records(series: Any, value_key: str, limit: int = 5) -> list[dict[str, Any]]:
    if series is None:
        return []
    table_records = _table_to_records(series, limit=limit)
    if table_records:
        return table_records
    try:
        if hasattr(series, "items"):
            return [{"date": str(index), value_key: value} for index, value in list(series.items())[-limit:]]
    except Exception:
        return []
    return []


def _normalize_news(news_items: Any, limit: int = 5) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if not isinstance(news_items, list):
        return normalized
    for item in news_items[:limit]:
        if not isinstance(item, dict):
            continue
        content = item.get("content") if isinstance(item.get("content"), dict) else {}
        title = item.get("title") or content.get("title")
        publisher = item.get("publisher") or content.get("provider", {}).get("displayName") if isinstance(content.get("provider"), dict) else item.get("publisher")
        link = item.get("link") or item.get("url") or content.get("canonicalUrl", {}).get("url") if isinstance(content.get("canonicalUrl"), dict) else item.get("link") or item.get("url")
        published = item.get("providerPublishTime") or content.get("pubDate") or item.get("pubDate")
        normalized.append(
            {
                "title": title or "제목 없음",
                "publisher": publisher or "unknown",
                "link": link,
                "published": published,
            }
        )
    return normalized


def _normalize_calendar(calendar: Any) -> dict[str, Any]:
    if calendar is None:
        return {}
    if isinstance(calendar, dict):
        return dict(calendar)
    records = _table_to_records(calendar, limit=10)
    if records:
        return {str(key): value for row in records for key, value in row.items()}
    try:
        if hasattr(calendar, "to_dict"):
            data = calendar.to_dict()
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}
    return {}


def _sum_column(records: list[dict[str, Any]], key: str) -> int:
    return sum(_to_int(row.get(key)) for row in records)


def _top_strikes(records: list[dict[str, Any]], sort_key: str = "openInterest", limit: int = 3) -> list[dict[str, Any]]:
    ranked = sorted(records, key=lambda row: _to_int(row.get(sort_key)), reverse=True)
    result = []
    for row in ranked[:limit]:
        result.append(
            {
                "strike": _round_or_none(row.get("strike")),
                "openInterest": _to_int(row.get("openInterest")),
                "volume": _to_int(row.get("volume")),
                "lastPrice": _round_or_none(row.get("lastPrice")),
                "impliedVolatility": _round_or_none(row.get("impliedVolatility"), 4),
            }
        )
    return result


def fetch_yfinance_options_summary(ticker: Any, max_expirations: int = 1) -> dict[str, Any]:
    expirations = list(getattr(ticker, "options", []) or [])
    if not expirations:
        return {
            "expirations_count": 0,
            "nearest_expiration": None,
            "call_open_interest": 0,
            "put_open_interest": 0,
            "call_volume": 0,
            "put_volume": 0,
            "put_call_open_interest_ratio": None,
            "put_call_volume_ratio": None,
            "top_call_strikes_by_oi": [],
            "top_put_strikes_by_oi": [],
        }

    all_calls: list[dict[str, Any]] = []
    all_puts: list[dict[str, Any]] = []
    for expiration in expirations[:max_expirations]:
        try:
            chain = ticker.option_chain(expiration)
        except Exception:
            continue
        all_calls.extend(_table_to_records(getattr(chain, "calls", None), limit=500))
        all_puts.extend(_table_to_records(getattr(chain, "puts", None), limit=500))

    call_oi = _sum_column(all_calls, "openInterest")
    put_oi = _sum_column(all_puts, "openInterest")
    call_volume = _sum_column(all_calls, "volume")
    put_volume = _sum_column(all_puts, "volume")
    return {
        "expirations_count": len(expirations),
        "nearest_expiration": expirations[0],
        "sampled_expirations": expirations[:max_expirations],
        "call_open_interest": call_oi,
        "put_open_interest": put_oi,
        "call_volume": call_volume,
        "put_volume": put_volume,
        "put_call_open_interest_ratio": round(put_oi / call_oi, 2) if call_oi else None,
        "put_call_volume_ratio": round(put_volume / call_volume, 2) if call_volume else None,
        "top_call_strikes_by_oi": _top_strikes(all_calls),
        "top_put_strikes_by_oi": _top_strikes(all_puts),
    }


def _build_quote_from_fast_info(symbol: str, fast_info: Any, fallback_info: dict[str, Any] | None = None) -> dict[str, Any]:
    info = fallback_info or {}
    price = _safe_get(fast_info, "last_price", "lastPrice", "regularMarketPrice", "currentPrice")
    previous = _safe_get(fast_info, "previous_close", "previousClose", "regularMarketPreviousClose")
    if price is None:
        price = _safe_get(info, "regularMarketPrice", "currentPrice", "last_price")
    if previous is None:
        previous = _safe_get(info, "regularMarketPreviousClose", "previousClose")
    price_float = _to_float(price)
    previous_float = _to_float(previous)
    pct_change = None
    if price_float is not None and previous_float not in (None, 0):
        pct_change = round(((price_float - float(previous_float)) / float(previous_float)) * 100, 2)
    return {
        "price": round(price_float, 2) if price_float is not None else None,
        "previous_close": round(previous_float, 2) if previous_float is not None else None,
        "pct_change": pct_change,
        "currency": _safe_get(fast_info, "currency") or info.get("currency"),
        "exchange": _safe_get(fast_info, "exchange", "exchangeName") or info.get("exchange"),
        "market_cap": _safe_get(fast_info, "market_cap", "marketCap") or info.get("marketCap"),
    }


def _quote_from_yahoo_chart_result(symbol: str, result: dict[str, Any]) -> dict[str, Any]:
    meta = result.get("meta") if isinstance(result.get("meta"), dict) else {}
    timestamps = result.get("timestamp") if isinstance(result.get("timestamp"), list) else []
    quote_blocks = result.get("indicators", {}).get("quote", []) if isinstance(result.get("indicators"), dict) else []
    quote_block = quote_blocks[0] if quote_blocks and isinstance(quote_blocks[0], dict) else {}
    closes = quote_block.get("close") if isinstance(quote_block.get("close"), list) else []
    points = [(ts, close) for ts, close in zip(timestamps, closes) if _to_float(close) is not None]
    if not points:
        raise ValueError("yahoo chart has no close points")
    last_ts, last_price = points[-1]
    price_float = _to_float(last_price)
    # During pre/post market, Yahoo chartPreviousClose can point to an older chart-range close.
    # regularMarketPrice is the last regular-session close in that state and matches broker UI premarket %.
    previous = _safe_get(meta, "regularMarketPrice", "previousClose", "chartPreviousClose")
    previous_float = _to_float(previous)
    pct_change = None
    if price_float is not None and previous_float not in (None, 0):
        pct_change = round(((price_float - float(previous_float)) / float(previous_float)) * 100, 2)
    return {
        "price": round(price_float, 2) if price_float is not None else None,
        "previous_close": round(previous_float, 2) if previous_float is not None else None,
        "pct_change": pct_change,
        "currency": meta.get("currency"),
        "exchange": meta.get("exchangeName") or meta.get("exchange"),
        "timestamp": datetime.fromtimestamp(int(last_ts), timezone.utc).isoformat() if last_ts else None,
        "regular_market_price": _round_or_none(meta.get("regularMarketPrice")),
        "chart_previous_close": _round_or_none(meta.get("chartPreviousClose")),
        "regular_market_time": datetime.fromtimestamp(int(meta["regularMarketTime"]), timezone.utc).isoformat() if meta.get("regularMarketTime") else None,
    }


def fetch_yahoo_chart_quote_pack(symbol: str, range_: str = "1d", interval: str = "1m") -> dict[str, Any]:
    encoded = urllib.parse.quote(symbol, safe="")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}?range={range_}&interval={interval}&includePrePost=true"
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
        result = (((payload.get("chart") or {}).get("result") or [None])[0])
        if not isinstance(result, dict):
            raise ValueError("yahoo chart result missing")
        quote = _quote_from_yahoo_chart_result(symbol, result)
    except Exception as exc:
        return {
            "available": False,
            "source": "yahoo_chart_quote_error",
            "symbol": symbol,
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "warning": str(exc),
        }
    return {
        "available": True,
        "source": "yahoo_chart_quote",
        "symbol": symbol,
        "collected_at": quote.get("timestamp") or datetime.now(timezone.utc).isoformat(),
        "quote": quote,
        "warnings": [],
    }


def fetch_yfinance_quote_pack(symbol: str) -> dict[str, Any]:
    yf = _import_yfinance()
    if yf is None:
        return {
            "available": False,
            "source": "yfinance_missing",
            "symbol": symbol,
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "warning": "yfinance 미설치 또는 import 실패",
        }

    try:
        ticker = yf.Ticker(symbol)
        fast_info = getattr(ticker, "fast_info", None) or {}
    except Exception as exc:
        return {
            "available": False,
            "source": "yfinance_quote_error",
            "symbol": symbol,
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "warning": str(exc),
        }

    quote_stderr = io.StringIO()
    with contextlib.redirect_stderr(quote_stderr):
        quote = _build_quote_from_fast_info(symbol, fast_info)
    warnings = [line.strip() for line in quote_stderr.getvalue().splitlines() if line.strip()]
    return {
        "available": True,
        "source": "yfinance_quote",
        "symbol": symbol,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "quote": quote,
        "warnings": warnings,
    }


def fetch_yfinance_market_pack(symbol: str, max_news: int = 5) -> dict[str, Any]:
    yf = _import_yfinance()
    if yf is None:
        return {
            "available": False,
            "source": "yfinance_missing",
            "symbol": symbol,
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "warning": "yfinance 미설치 또는 import 실패",
        }

    try:
        ticker = yf.Ticker(symbol)
    except Exception as exc:
        return {
            "available": False,
            "source": "yfinance_error",
            "symbol": symbol,
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "warning": str(exc),
        }

    warnings: list[str] = []
    fast_info = getattr(ticker, "fast_info", None) or {}
    try:
        info = getattr(ticker, "info", None) or {}
    except Exception as exc:
        info = {}
        warnings.append(f"info unavailable: {exc}")

    quote = _build_quote_from_fast_info(symbol, fast_info, info)

    fundamentals = {
        "long_name": info.get("longName") or info.get("shortName") or symbol,
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "market_cap": info.get("marketCap") or quote.get("market_cap"),
        "enterprise_value": info.get("enterpriseValue"),
        "trailing_pe": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "price_to_sales": info.get("priceToSalesTrailing12Months"),
        "price_to_book": info.get("priceToBook"),
        "beta": info.get("beta"),
        "short_percent_float": info.get("shortPercentOfFloat"),
        "shares_outstanding": info.get("sharesOutstanding"),
        "website": info.get("website"),
    }

    try:
        options = fetch_yfinance_options_summary(ticker)
    except Exception as exc:
        options = {"error": str(exc)}
        warnings.append(f"options unavailable: {exc}")

    holders = {
        "major_holders": _table_to_records(_safe_attr(ticker, "major_holders", None, warnings), limit=5),
        "institutional_holders": _table_to_records(_safe_attr(ticker, "institutional_holders", None, warnings), limit=5),
        "mutualfund_holders": _table_to_records(_safe_attr(ticker, "mutualfund_holders", None, warnings), limit=5),
        "insider_transactions": _table_to_records(_safe_attr(ticker, "insider_transactions", None, warnings), limit=5),
    }

    actions = {
        "actions": _table_to_records(_safe_attr(ticker, "actions", None, warnings), limit=5),
        "dividends": _series_to_records(_safe_attr(ticker, "dividends", None, warnings), "dividend", limit=5),
        "splits": _series_to_records(_safe_attr(ticker, "splits", None, warnings), "split", limit=5),
    }

    recommendations = _table_to_records(_safe_attr(ticker, "recommendations", None, warnings), limit=5)
    earnings_dates = _table_to_records(_safe_attr(ticker, "earnings_dates", None, warnings), limit=5)

    return {
        "available": True,
        "source": "yfinance",
        "symbol": symbol,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "quote": quote,
        "fundamentals": fundamentals,
        "options": options,
        "news": _normalize_news(getattr(ticker, "news", []), limit=max_news),
        "calendar": _normalize_calendar(getattr(ticker, "calendar", None)),
        "earnings_dates": earnings_dates,
        "holders": holders,
        "actions": actions,
        "recommendations": recommendations,
        "warnings": warnings,
    }


def _fmt_num(value: Any) -> str:
    numeric = _to_float(value)
    if numeric is None:
        return "n/a"
    if abs(numeric) >= 1_000_000_000_000:
        return f"{numeric / 1_000_000_000_000:.2f}T"
    if abs(numeric) >= 1_000_000_000:
        return f"{numeric / 1_000_000_000:.2f}B"
    if abs(numeric) >= 1_000_000:
        return f"{numeric / 1_000_000:.2f}M"
    return f"{numeric:g}"


def build_yfinance_focus_lines(pack: dict[str, Any], max_lines: int = 8) -> list[str]:
    symbol = str(pack.get("symbol") or "UNKNOWN")
    if not pack.get("available"):
        return [f"YF Pack: {symbol} / yfinance 미설치 또는 호출 불가"]

    quote = pack.get("quote") or {}
    fundamentals = pack.get("fundamentals") or {}
    options = pack.get("options") or {}
    news = pack.get("news") or []
    calendar = pack.get("calendar") or {}
    holders = pack.get("holders") or {}
    recommendations = pack.get("recommendations") or []
    actions = pack.get("actions") or {}

    lines = []
    price = quote.get("price")
    price_text = f"{price:g}" if isinstance(price, (int, float)) else "n/a"
    change = quote.get("pct_change")
    change_text = f" / {change:+.2f}%" if isinstance(change, (int, float)) else ""
    lines.append(f"YF Quote: {symbol} {price_text}{change_text} / {quote.get('exchange') or 'unknown'} / {quote.get('currency') or 'n/a'}")

    if options:
        lines.append(
            "YF Options: "
            f"near {options.get('nearest_expiration') or 'n/a'} / "
            f"call OI {options.get('call_open_interest', 0)} / put OI {options.get('put_open_interest', 0)} / "
            f"P/C vol {options.get('put_call_volume_ratio') if options.get('put_call_volume_ratio') is not None else 'n/a'}"
        )
        top_calls = options.get("top_call_strikes_by_oi") or []
        top_puts = options.get("top_put_strikes_by_oi") or []
        if top_calls or top_puts:
            call_text = ",".join(str(item.get("strike")) for item in top_calls[:2]) or "n/a"
            put_text = ",".join(str(item.get("strike")) for item in top_puts[:2]) or "n/a"
            lines.append(f"YF Option strikes: calls {call_text} / puts {put_text}")

    lines.append(
        "YF Fundamentals: "
        f"{fundamentals.get('long_name') or symbol} / {fundamentals.get('sector') or 'sector n/a'} / "
        f"mcap {_fmt_num(fundamentals.get('market_cap'))} / fPE {_fmt_num(fundamentals.get('forward_pe'))} / beta {_fmt_num(fundamentals.get('beta'))}"
    )

    if news:
        top_news = news[0]
        lines.append(f"YF News: {top_news.get('title')} / {top_news.get('publisher')}")
    if calendar:
        calendar_items = [f"{key}={value}" for key, value in list(calendar.items())[:2]]
        lines.append(f"YF Calendar: {' / '.join(calendar_items)}")

    inst = (holders.get("institutional_holders") or [])[:1]
    if inst:
        holder = inst[0]
        holder_name = holder.get("Holder") or holder.get("holder") or str(holder)[:60]
        lines.append(f"YF Holders: top institution {holder_name}")
    if recommendations:
        lines.append(f"YF Recommendations: {recommendations[0]}")
    if actions.get("dividends") or actions.get("splits"):
        lines.append(f"YF Actions: dividends {len(actions.get('dividends') or [])} / splits {len(actions.get('splits') or [])}")

    return lines[:max_lines]


def build_yfinance_signal_lines(symbol: str, max_lines: int = 4) -> list[str]:
    return build_yfinance_focus_lines(fetch_yfinance_market_pack(symbol), max_lines=max_lines)
