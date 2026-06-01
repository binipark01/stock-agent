from __future__ import annotations

from datetime import datetime, timezone
import contextlib
import io
import json
import math
from typing import Any
import urllib.parse
import urllib.request

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore


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


TOSS_WTS_PRODUCT_CODES: dict[str, str] = {
    "SPY": "US19930122001",
    "SOXX": "US20010713001",
    "NVDA": "US19990122001",
    "PLTR": "US20200930014",
    "RKLB": "US20210825002",
    "RDW": "US20210903005",
    "RDDT": "NYS0240321001",
    "AMD": "US20150102001",
    "SMCI": "US20200114002",
    "OKLO": "US20210701009",
    "JOBY": "US20210811006",
    "ASTS": "US20210407001",
    "COIN": "US20210414003",
    "MSTR": "US19980611001",
}
_PRODUCT_CODE_TO_SYMBOL = {code: symbol for symbol, code in TOSS_WTS_PRODUCT_CODES.items()}


def _toss_session_label(raw: Any) -> str:
    text = str(raw or "").strip()
    upper = text.upper()
    if not upper:
        return "데이터 없음"
    if "DAY" in upper or "주간" in text or "데이" in text:
        return "토스 데이마켓/주간거래"
    if "PRE" in upper or "BEFORE" in upper or "프리" in text:
        return "프리마켓"
    if "AFTER" in upper or "POST" in upper or "애프터" in text:
        return "애프터장"
    if "REGULAR" in upper or "NORMAL" in upper or "정규" in text:
        return "정규장"
    if "CLOSE" in upper or "휴장" in text:
        return "휴장/데이터 없음"
    return text


def _extract_toss_price_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("result", "data", "prices", "stockPrices", "stock_prices"):
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    if isinstance(payload.get("result"), dict):
        return _extract_toss_price_rows(payload.get("result"))
    if isinstance(payload.get("data"), dict):
        return _extract_toss_price_rows(payload.get("data"))
    return []


def _toss_row_symbol(row: dict[str, Any]) -> str | None:
    code = str(row.get("productCode") or row.get("product_code") or row.get("code") or "").strip()
    if code and code in _PRODUCT_CODE_TO_SYMBOL:
        return _PRODUCT_CODE_TO_SYMBOL[code]
    symbol = str(row.get("symbol") or row.get("ticker") or row.get("tickerSymbol") or "").strip().upper()
    return symbol or None


def _quote_from_toss_wts_row(symbol: str, row: dict[str, Any]) -> dict[str, Any] | None:
    price = _to_float(row.get("close"))
    base = _to_float(row.get("base"))
    if price is None:
        return None
    pct_change = round(((price - float(base)) / float(base)) * 100, 2) if base not in (None, 0) else None
    session_raw = row.get("session")
    session_label = _toss_session_label(session_raw)
    quote = {
        "price": round(price, 2),
        "previous_close": round(float(base), 2) if base is not None else None,
        "pct_change": pct_change,
        "volume": _to_int(row.get("volume")),
        "currency": "USD",
        "exchange": row.get("exchange") or row.get("market") or "Toss WTS",
        "session": session_raw,
        "session_label": session_label,
        "pct_change_basis": "Toss base 대비",
        "price_source": "toss_wts_stock_prices",
        "is_stale_regular_close": False,
    }
    return quote


def fetch_toss_wts_quote_packs(symbols: list[str] | tuple[str, ...] | set[str]) -> dict[str, dict[str, Any]]:
    selected_codes = []
    code_to_symbol: dict[str, str] = {}
    for raw_symbol in symbols:
        symbol = str(raw_symbol).upper()
        code = TOSS_WTS_PRODUCT_CODES.get(symbol)
        if not code:
            continue
        selected_codes.append(code)
        code_to_symbol[code] = symbol
    if not selected_codes:
        return {}
    query = urllib.parse.urlencode({"productCodes": ",".join(selected_codes)})
    url = f"https://wts-info-api.tossinvest.com/api/v1/product/stock-prices?{query}"
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    collected_at = datetime.now(timezone.utc).isoformat()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
        rows = _extract_toss_price_rows(payload)
    except Exception as exc:
        return {
            symbol: {
                "available": False,
                "source": "toss_wts_stock_prices_error",
                "symbol": symbol,
                "collected_at": collected_at,
                "warning": str(exc),
            }
            for symbol in code_to_symbol.values()
        }
    packs: dict[str, dict[str, Any]] = {}
    for row in rows:
        symbol = _toss_row_symbol(row)
        if not symbol:
            code = str(row.get("productCode") or row.get("product_code") or row.get("code") or "").strip()
            symbol = code_to_symbol.get(code)
        if not symbol or symbol not in set(str(item).upper() for item in symbols):
            continue
        quote = _quote_from_toss_wts_row(symbol, row)
        if quote is None:
            continue
        packs[symbol] = {
            "available": True,
            "source": "toss_wts_stock_prices",
            "symbol": symbol,
            "collected_at": collected_at,
            "quote": quote,
            "warnings": [],
        }
    for symbol in code_to_symbol.values():
        packs.setdefault(
            symbol,
            {
                "available": False,
                "source": "toss_wts_stock_prices_missing",
                "symbol": symbol,
                "collected_at": collected_at,
                "warning": "Toss WTS row missing",
            },
        )
    return packs


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


def _intraday_pct(points: list[tuple[Any, Any]], minutes: int) -> float | None:
    if len(points) <= minutes:
        return None
    latest = _to_float(points[-1][1])
    baseline = _to_float(points[-1 - minutes][1])
    if latest is None or baseline in (None, 0):
        return None
    return round(((latest - float(baseline)) / float(baseline)) * 100, 2)


def _simple_rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) < 2:
        return None
    changes = [values[idx] - values[idx - 1] for idx in range(1, len(values))]
    window = changes[-period:] if len(changes) >= period else changes
    if not window:
        return None
    gains = [change for change in window if change > 0]
    losses = [-change for change in window if change < 0]
    avg_gain = sum(gains) / len(window)
    avg_loss = sum(losses) / len(window)
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def _bollinger_state(position_pct: float | None) -> str | None:
    if position_pct is None:
        return None
    if position_pct >= 90:
        return "상단권"
    if position_pct >= 70:
        return "상단근접"
    if position_pct <= 10:
        return "하단권"
    if position_pct <= 30:
        return "하단근접"
    return "중립"


def _ema_series(values: list[float], period: int) -> list[float]:
    if len(values) < period:
        return []
    multiplier = 2 / (period + 1)
    ema = sum(values[:period]) / period
    series = [ema]
    for value in values[period:]:
        ema = ((value - ema) * multiplier) + ema
        series.append(ema)
    return series


def _macd_state(histogram: float | None) -> str | None:
    if histogram is None:
        return None
    if histogram > 0:
        return "상방"
    if histogram < 0:
        return "하방"
    return "중립"


def _stochastic_state(k_value: float | None) -> str | None:
    if k_value is None:
        return None
    if k_value >= 80:
        return "과열"
    if k_value <= 20:
        return "침체"
    return "중립"


def _bollinger_snapshot(closes: list[float]) -> tuple[float, float, float, float | None, float | None] | None:
    if len(closes) < 20:
        return None
    window = closes[-20:]
    mid = sum(window) / len(window)
    variance = sum((value - mid) ** 2 for value in window) / len(window)
    std = math.sqrt(variance)
    upper = mid + (2 * std)
    lower = mid - (2 * std)
    latest = closes[-1]
    position = ((latest - lower) / (upper - lower)) * 100 if upper != lower else None
    bandwidth = ((upper - lower) / mid) * 100 if mid else None
    return mid, upper, lower, position, bandwidth


def _technical_fields_from_closes(closes: list[float]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    rsi = _simple_rsi(closes, 14)
    if rsi is not None:
        fields["rsi14"] = round(rsi, 1)
        previous_rsi = _simple_rsi(closes[:-1], 14) if len(closes) > 2 else None
        if previous_rsi is not None:
            fields["rsi14_prev"] = round(previous_rsi, 1)
            fields["rsi14_delta"] = round(rsi - previous_rsi, 1)
    current_bollinger = _bollinger_snapshot(closes)
    if current_bollinger is not None:
        mid, upper, lower, position, bandwidth = current_bollinger
        fields["bollinger_mid"] = round(mid, 2)
        fields["bollinger_upper"] = round(upper, 2)
        fields["bollinger_lower"] = round(lower, 2)
        if position is not None:
            fields["bollinger_position_pct"] = round(position, 1)
        if bandwidth is not None:
            fields["bollinger_bandwidth_pct"] = round(bandwidth, 1)
        previous_bollinger = _bollinger_snapshot(closes[:-1]) if len(closes) >= 21 else None
        if previous_bollinger is not None:
            _, _, _, previous_position, previous_bandwidth = previous_bollinger
            if position is not None and previous_position is not None:
                fields["bollinger_position_prev"] = round(previous_position, 1)
                fields["bollinger_position_delta"] = round(position - previous_position, 1)
            if bandwidth is not None and previous_bandwidth is not None:
                fields["bollinger_bandwidth_prev"] = round(previous_bandwidth, 1)
                fields["bollinger_bandwidth_delta"] = round(bandwidth - previous_bandwidth, 1)
        fields["bollinger_state"] = _bollinger_state(position)
    if len(closes) >= 34:
        ema12 = _ema_series(closes, 12)
        ema26 = _ema_series(closes, 26)
        macd_values = [ema12[original_idx - 11] - ema26[original_idx - 25] for original_idx in range(25, len(closes))]
        signal_values = _ema_series(macd_values, 9)
        if macd_values and signal_values:
            macd_line = macd_values[-1]
            signal = signal_values[-1]
            histogram = macd_line - signal
            fields["macd_line"] = round(macd_line, 2)
            fields["macd_signal"] = round(signal, 2)
            fields["macd_histogram"] = round(histogram, 2)
            if len(signal_values) >= 2 and len(macd_values) >= 2:
                previous_macd_line = macd_values[-2]
                previous_signal = signal_values[-2]
                previous_histogram = previous_macd_line - previous_signal
                fields["macd_line_prev"] = round(previous_macd_line, 2)
                fields["macd_signal_prev"] = round(previous_signal, 2)
                fields["macd_histogram_prev"] = round(previous_histogram, 2)
                fields["macd_histogram_delta"] = round(histogram - previous_histogram, 2)
            fields["macd_state"] = _macd_state(histogram)
    return fields


def _ichimoku_cloud_state(latest_close: float, cloud_top: float, cloud_bottom: float) -> str:
    if latest_close > cloud_top:
        return "구름 위"
    if latest_close < cloud_bottom:
        return "구름 아래"
    return "구름 안"


def _technical_fields_from_ohlc(closes: list[float], highs: list[float], lows: list[float]) -> dict[str, Any]:
    fields = _technical_fields_from_closes(closes)
    if len(closes) >= 16 and len(highs) >= 16 and len(lows) >= 16:
        fast_k_values: list[float] = []
        for end_idx in range(13, len(closes)):
            high_window = highs[end_idx - 13 : end_idx + 1]
            low_window = lows[end_idx - 13 : end_idx + 1]
            high_14 = max(high_window)
            low_14 = min(low_window)
            if high_14 != low_14:
                fast_k_values.append(((closes[end_idx] - low_14) / (high_14 - low_14)) * 100)
        slow_k_values = [sum(fast_k_values[idx - 2 : idx + 1]) / 3 for idx in range(2, len(fast_k_values))]
        slow_d_values = [sum(slow_k_values[idx - 2 : idx + 1]) / 3 for idx in range(2, len(slow_k_values))]
        if slow_k_values:
            stochastic_k = slow_k_values[-1]
            stochastic_d = slow_d_values[-1] if slow_d_values else sum(slow_k_values[-3:]) / len(slow_k_values[-3:])
            fields["stochastic_k"] = round(stochastic_k, 1)
            fields["stochastic_d"] = round(stochastic_d, 1)
            if len(slow_k_values) >= 2:
                fields["stochastic_k_prev"] = round(slow_k_values[-2], 1)
                fields["stochastic_k_delta"] = round(stochastic_k - slow_k_values[-2], 1)
            if len(slow_d_values) >= 2:
                fields["stochastic_d_prev"] = round(slow_d_values[-2], 1)
                fields["stochastic_d_delta"] = round(stochastic_d - slow_d_values[-2], 1)
            fields["stochastic_state"] = _stochastic_state(stochastic_k)
    if len(closes) < 52 or len(highs) < 52 or len(lows) < 52:
        return fields

    conversion = (max(highs[-9:]) + min(lows[-9:])) / 2
    base = (max(highs[-26:]) + min(lows[-26:])) / 2
    span_a = (conversion + base) / 2
    span_b = (max(highs[-52:]) + min(lows[-52:])) / 2
    cloud_top = max(span_a, span_b)
    cloud_bottom = min(span_a, span_b)
    latest_close = closes[-1]
    if latest_close > cloud_top:
        cloud_distance = ((latest_close - cloud_top) / latest_close) * 100
    elif latest_close < cloud_bottom:
        cloud_distance = ((latest_close - cloud_bottom) / latest_close) * 100
    else:
        cloud_distance = 0.0
    fields.update(
        {
            "ichimoku_conversion": round(conversion, 2),
            "ichimoku_base": round(base, 2),
            "ichimoku_span_a": round(span_a, 2),
            "ichimoku_span_b": round(span_b, 2),
            "ichimoku_cloud_top": round(cloud_top, 2),
            "ichimoku_cloud_bottom": round(cloud_bottom, 2),
            "ichimoku_cloud_distance_pct": round(cloud_distance, 1),
            "ichimoku_conversion_base_spread": round(conversion - base, 2),
            "ichimoku_cloud_state": _ichimoku_cloud_state(latest_close, cloud_top, cloud_bottom),
        }
    )
    return fields


def _timestamp_in_yahoo_period(timestamp: Any, period: Any) -> bool:
    if not isinstance(period, dict):
        return False
    ts = _to_float(timestamp)
    start = _to_float(period.get("start"))
    end = _to_float(period.get("end"))
    if ts is None or start is None or end is None:
        return False
    return float(start) <= float(ts) < float(end)


def _is_yahoo_regular_session_quote(meta: dict[str, Any], last_ts: Any) -> bool:
    periods = meta.get("currentTradingPeriod") if isinstance(meta.get("currentTradingPeriod"), dict) else {}
    if _timestamp_in_yahoo_period(last_ts, periods.get("regular")):
        return True
    market_state = str(meta.get("marketState") or "").upper()
    return market_state == "REGULAR"


def _yahoo_session_label(meta: dict[str, Any], last_ts: Any) -> str:
    periods = meta.get("currentTradingPeriod") if isinstance(meta.get("currentTradingPeriod"), dict) else {}
    if _timestamp_in_yahoo_period(last_ts, periods.get("pre")):
        return "프리마켓"
    if _timestamp_in_yahoo_period(last_ts, periods.get("regular")):
        return "정규장"
    if _timestamp_in_yahoo_period(last_ts, periods.get("post")):
        return "애프터장"
    market_state = str(meta.get("marketState") or "").upper()
    if "PRE" in market_state:
        return "프리마켓"
    if market_state == "REGULAR":
        return "정규장"
    if "POST" in market_state or "AFTER" in market_state:
        return "애프터장"
    if "CLOSED" in market_state or "CLOSE" in market_state:
        return "휴장/데이터 없음"
    return market_state or "데이터 없음"


def _is_yahoo_stale_regular_close(meta: dict[str, Any], last_ts: Any, price: Any) -> bool:
    if _is_yahoo_regular_session_quote(meta, last_ts):
        return False
    session = _yahoo_session_label(meta, last_ts)
    if session not in {"프리마켓", "애프터장", "휴장/데이터 없음", "데이터 없음"}:
        return False
    price_float = _to_float(price)
    regular_price = _to_float(meta.get("regularMarketPrice"))
    regular_time = _to_float(meta.get("regularMarketTime"))
    last_time = _to_float(last_ts)
    if price_float is not None and regular_price is not None and abs(price_float - regular_price) < 0.0001:
        return True
    if regular_time is not None and last_time is not None and int(regular_time) == int(last_time):
        return True
    return False


def _select_yahoo_previous_close(meta: dict[str, Any], last_ts: Any) -> Any:
    regular_session_previous = _safe_get(meta, "previousClose", "chartPreviousClose", "regularMarketPreviousClose")
    regular_market_price = _safe_get(meta, "regularMarketPrice")
    if _is_yahoo_regular_session_quote(meta, last_ts):
        return regular_session_previous if _to_float(regular_session_previous) is not None else regular_market_price
    return regular_market_price if _to_float(regular_market_price) is not None else regular_session_previous


def _yahoo_session_date_key(timestamp: Any) -> str | None:
    numeric = _to_float(timestamp)
    if numeric is None:
        return None
    dt = datetime.fromtimestamp(int(numeric), timezone.utc)
    if ZoneInfo is not None:
        dt = dt.astimezone(ZoneInfo("America/New_York"))
    return dt.date().isoformat()


def _yahoo_volume_totals_by_session_date(timestamps: list[Any], volumes: list[Any]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for timestamp, volume in zip(timestamps, volumes):
        key = _yahoo_session_date_key(timestamp)
        volume_float = _to_float(volume)
        if key is None or volume_float is None:
            continue
        totals[key] = totals.get(key, 0.0) + volume_float
    return totals


def _quote_from_yahoo_chart_result(symbol: str, result: dict[str, Any]) -> dict[str, Any]:
    meta = result.get("meta") if isinstance(result.get("meta"), dict) else {}
    timestamps = result.get("timestamp") if isinstance(result.get("timestamp"), list) else []
    quote_blocks = result.get("indicators", {}).get("quote", []) if isinstance(result.get("indicators"), dict) else []
    quote_block = quote_blocks[0] if quote_blocks and isinstance(quote_blocks[0], dict) else {}
    closes = quote_block.get("close") if isinstance(quote_block.get("close"), list) else []
    highs = quote_block.get("high") if isinstance(quote_block.get("high"), list) else []
    lows = quote_block.get("low") if isinstance(quote_block.get("low"), list) else []
    volumes = quote_block.get("volume") if isinstance(quote_block.get("volume"), list) else []
    points = [(ts, close) for ts, close in zip(timestamps, closes) if _to_float(close) is not None]
    close_values = [float(_to_float(close)) for _, close in points]
    ohlc_points = [
        (float(close_float), float(high_float), float(low_float))
        for close, high, low in zip(closes, highs, lows)
        for close_float, high_float, low_float in [(_to_float(close), _to_float(high), _to_float(low))]
        if close_float is not None and high_float is not None and low_float is not None
    ]
    if not points:
        raise ValueError("yahoo chart has no close points")
    last_ts, last_price = points[-1]
    price_float = _to_float(last_price)
    # During regular hours, Yahoo regularMarketPrice updates to the current tick;
    # using it as the baseline makes every alert show ~0%. Use prior regular close
    # in regular session, but keep regularMarketPrice as the pre/post baseline where
    # Yahoo exposes it as the last regular-session close.
    previous = _select_yahoo_previous_close(meta, last_ts)
    previous_float = _to_float(previous)
    pct_change = None
    if price_float is not None and previous_float not in (None, 0):
        pct_change = round(((price_float - float(previous_float)) / float(previous_float)) * 100, 2)
    volume_totals = _yahoo_volume_totals_by_session_date(timestamps, volumes)
    current_session_date = _yahoo_session_date_key(last_ts)
    day_volume = volume_totals.get(current_session_date or "") if current_session_date else None
    if day_volume is None:
        volume_points = [(_to_float(volume) or 0.0) for volume in volumes]
        day_volume = sum(volume_points) if volume_points else None
    previous_volume = None
    if current_session_date:
        previous_dates = [key for key in sorted(volume_totals) if key < current_session_date]
        if previous_dates:
            previous_volume = volume_totals[previous_dates[-1]]
    trading_value_points = []
    for timestamp, close, volume in zip(timestamps, closes, volumes):
        if current_session_date and _yahoo_session_date_key(timestamp) != current_session_date:
            continue
        close_float = _to_float(close)
        volume_float = _to_float(volume)
        if close_float is not None and volume_float is not None:
            trading_value_points.append(close_float * volume_float)
    trading_value = sum(trading_value_points) if trading_value_points else None
    vwap = (trading_value / day_volume) if trading_value is not None and day_volume not in (None, 0) else None
    vwap_position_pct = None
    if price_float is not None and vwap not in (None, 0):
        vwap_position_pct = ((price_float - float(vwap)) / float(vwap)) * 100
    quote = {
        "price": round(price_float, 2) if price_float is not None else None,
        "previous_close": round(previous_float, 2) if previous_float is not None else None,
        "pct_change": pct_change,
        "pct_change_1m": _intraday_pct(points, 1),
        "pct_change_5m": _intraday_pct(points, 5),
        "pct_change_15m": _intraday_pct(points, 15),
        "volume": int(day_volume) if day_volume is not None else None,
        "day_volume": int(day_volume) if day_volume is not None else None,
        "previous_volume": int(previous_volume) if previous_volume is not None else None,
        "volume_vs_previous_pct": round(((day_volume - previous_volume) / previous_volume) * 100, 1) if day_volume is not None and previous_volume not in (None, 0) else None,
        "trading_value": round(trading_value, 2) if trading_value is not None else None,
        "vwap": round(vwap, 2) if vwap is not None else None,
        "vwap_position_pct": round(vwap_position_pct, 2) if vwap_position_pct is not None else None,
        "currency": meta.get("currency"),
        "exchange": meta.get("exchangeName") or meta.get("exchange"),
        "timestamp": datetime.fromtimestamp(int(last_ts), timezone.utc).isoformat() if last_ts else None,
        "regular_market_price": _round_or_none(meta.get("regularMarketPrice")),
        "chart_previous_close": _round_or_none(meta.get("chartPreviousClose")),
        "regular_market_time": datetime.fromtimestamp(int(meta["regularMarketTime"]), timezone.utc).isoformat() if meta.get("regularMarketTime") else None,
        "market_state": meta.get("marketState"),
        "session_label": _yahoo_session_label(meta, last_ts),
        "price_source": "yahoo_chart_quote",
        "pct_change_basis": "정규장 종가 대비" if _is_yahoo_regular_session_quote(meta, last_ts) else "이전 정규장/마지막 정규가 대비",
        "is_stale_regular_close": _is_yahoo_stale_regular_close(meta, last_ts, price_float),
    }
    if quote.get("is_stale_regular_close"):
        quote["stale_note"] = "정규장 종가 기준(확장/주간거래 실시간가 미확인)"
    if ohlc_points:
        quote.update(
            _technical_fields_from_ohlc(
                [point[0] for point in ohlc_points],
                [point[1] for point in ohlc_points],
                [point[2] for point in ohlc_points],
            )
        )
    else:
        quote.update(_technical_fields_from_closes(close_values))
    return quote


def fetch_yahoo_chart_quote_pack(symbol: str, range_: str = "2d", interval: str = "1m") -> dict[str, Any]:
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
