from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from typing import Any, Callable

try:
    from .options_flow import build_options_flow_report
    from .sector_theme_config import USER_SUB_THEME_BASKETS, USER_THEME_BASKETS
    from .technical_snapshot import build_technical_snapshot
    from .yfinance_data import build_yfinance_signal_lines
except ImportError:  # direct script execution
    from options_flow import build_options_flow_report  # type: ignore
    from sector_theme_config import USER_SUB_THEME_BASKETS, USER_THEME_BASKETS  # type: ignore
    from technical_snapshot import build_technical_snapshot  # type: ignore
    from yfinance_data import build_yfinance_signal_lines  # type: ignore


AgentRunner = Callable[[str], dict[str, Any]]


def normalize_tradingview_symbol(raw_symbol: str | None) -> str:
    symbol = str(raw_symbol or "").strip().upper()
    if ":" in symbol:
        symbol = symbol.split(":")[-1]
    return symbol.replace("$", "") or "UNKNOWN"


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def _format_int(value: Any) -> str | None:
    numeric = _coerce_float(value)
    if numeric is None:
        return None
    return f"{int(numeric):,}"


def _themes_for_symbol(symbol: str) -> list[str]:
    upper = normalize_tradingview_symbol(symbol)
    themes: list[str] = []
    for basket in USER_THEME_BASKETS.values():
        symbols = {str(item).upper() for item in basket.get("symbols", ())}
        if upper in symbols:
            themes.append(str(basket.get("name") or "테마"))
    for basket in USER_SUB_THEME_BASKETS.values():
        symbols = {str(item).upper() for item in basket.get("symbols", ())}
        if upper in symbols:
            themes.append(str(basket.get("name") or "세부테마"))
    return list(dict.fromkeys(themes))


def _alert_action_judgment(alert_name: str, live_quote: dict[str, Any], technical_snapshot: dict[str, Any] | None = None) -> str:
    pct = _coerce_float(live_quote.get("change_pct") or live_quote.get("pct_change"))
    lowered = str(alert_name or "").lower()
    if pct is not None and pct >= 5:
        base = "당일 급등권이라 추격 위험, VWAP/직전 돌파선 지지 확인"
    elif pct is not None and pct >= 2:
        base = "모멘텀은 살아있지만 추격보다 눌림 확인 우선"
    elif pct is not None and pct <= -3:
        base = "약세 알림이면 반등매수보다 지지선 회복 확인 우선"
    else:
        base = "방향 확인 전에는 신호 발생 캔들 고점/저점 재확인"
    if any(keyword in lowered for keyword in ["break", "돌파", "고점", "high"]):
        base = "돌파 알림: 첫 캔들 추격보다 리테스트/VWAP 지지 확인"
    if any(keyword in lowered for keyword in ["이탈", "breakdown", "crossing down", "하향"]):
        base = "이탈 알림: 지지선 회복 전까지 신규 진입 보류"
    if technical_snapshot and technical_snapshot.get("action_bias"):
        base += f" / 기술적 bias: {technical_snapshot['action_bias']}"
    return base


def parse_tradingview_payload(raw_body: str) -> dict[str, Any]:
    text = (raw_body or "").strip()
    if text:
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                data.setdefault("raw_message", raw_body)
                return data
        except json.JSONDecodeError:
            pass

    symbol = "UNKNOWN"
    symbol_match = re.search(r"\b(?:NASDAQ|NYSE|AMEX|ARCA|CBOE|OTC):[A-Z0-9._-]+\b", text, flags=re.IGNORECASE)
    if symbol_match:
        symbol = symbol_match.group(0).upper()
    else:
        bare_match = re.search(r"\b[A-Z]{1,5}\b", text)
        if bare_match:
            symbol = bare_match.group(0).upper()

    price = None
    price_match = re.search(r"(?:price|close|last|@)?\s*([$]?[0-9]+(?:\.[0-9]+)?)", text, flags=re.IGNORECASE)
    if price_match:
        price = price_match.group(1).replace("$", "")

    return {
        "symbol": symbol,
        "price": price,
        "alert": text or "TradingView alert",
        "raw_message": raw_body,
    }


def _default_agent_runner(request: str, runtime_context: dict[str, Any] | None = None, explicit_mode: str | None = None) -> dict[str, Any]:
    try:
        from .main import build_response
    except ImportError:  # direct script execution
        from main import build_response  # type: ignore
    return build_response(request, runtime_context=runtime_context, explicit_mode=explicit_mode)


def fetch_current_quote_cnbc(symbol: str) -> dict[str, Any]:
    query = urllib.parse.urlencode(
        {
            "symbols": symbol,
            "requestMethod": "quick",
            "noform": "1",
            "partnerId": "2",
            "fund": "1",
            "exthrs": "1",
            "output": "json",
        }
    )
    url = f"https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol?{query}"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    data = json.loads(urllib.request.urlopen(request, timeout=20).read())
    quote_rows = data.get("FormattedQuoteResult", {}).get("FormattedQuote", [])
    if not quote_rows:
        raise ValueError(f"quote not found: {symbol}")
    row = quote_rows[0]
    return {
        "source": "CNBC quote",
        "symbol": symbol,
        "price": _coerce_float(row.get("last")),
        "timestamp": row.get("last_time") or row.get("last_timedate"),
        "change": _coerce_float(row.get("change")),
        "change_pct": _coerce_float(str(row.get("change_pct", "")).replace("%", "")),
        "volume": row.get("volume"),
        "real_time": str(row.get("realTime", "")).lower() == "true",
    }


def build_agent_request_from_tradingview(payload: dict[str, Any]) -> str:
    symbol = normalize_tradingview_symbol(payload.get("symbol") or payload.get("ticker"))
    alert_name = str(payload.get("alert") or payload.get("alert_name") or "TradingView alert").strip()
    price = payload.get("price") or payload.get("close")
    interval = payload.get("interval") or payload.get("timeframe")
    trigger_time = payload.get("time") or payload.get("timenow")
    request_text = f"{symbol} TradingView 알림 체크: {alert_name} / trigger_price={price} / interval={interval} / time={trigger_time}"
    return json.dumps(
        {
            "mode": "brief",
            "symbols": [symbol],
            "request": request_text,
            "tradingview_alert": payload,
        },
        ensure_ascii=False,
    )


def build_tradingview_webhook_response(
    payload: dict[str, Any],
    agent_runner: Callable[..., dict[str, Any]] | None = None,
    quote_fetcher: Callable[[str], dict[str, Any]] | None = None,
    runtime_context: dict[str, Any] | None = None,
    technical_snapshot_builder: Callable[[str], dict[str, Any]] | None = None,
    options_report_builder: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    runner = agent_runner or _default_agent_runner
    symbol = normalize_tradingview_symbol(payload.get("symbol") or payload.get("ticker"))
    price = _coerce_float(payload.get("price") or payload.get("close"))
    alert_name = str(payload.get("alert") or payload.get("alert_name") or "TradingView alert").strip()
    interval = str(payload.get("interval") or payload.get("timeframe") or "").strip()
    trigger_time = str(payload.get("time") or payload.get("timenow") or "").strip()
    agent_request = build_agent_request_from_tradingview(payload)
    try:
        live_quote = (quote_fetcher or fetch_current_quote_cnbc)(symbol)
    except Exception as exc:
        live_quote = {"source": "quote_fetch_failed", "error": str(exc), "symbol": symbol}
    agent_payload = runner(agent_request, runtime_context=runtime_context or {}, explicit_mode="brief")
    themes = _themes_for_symbol(symbol)
    try:
        technical_snapshot = (technical_snapshot_builder or build_technical_snapshot)(symbol) if symbol != "UNKNOWN" else None
    except Exception:
        technical_snapshot = None
    try:
        options_report = (options_report_builder or build_options_flow_report)(symbol) if symbol != "UNKNOWN" else None
    except Exception:
        options_report = None

    price_text = f"{price:g}" if price is not None else "가격 미제공"
    header = f"TradingView alert: {symbol} @ {price_text}"
    if interval:
        header += f" / {interval}"
    if alert_name:
        header += f" / {alert_name}"

    message_lines = [header]
    if trigger_time:
        message_lines.append(f"trigger time: {trigger_time}")
    if live_quote.get("price") is not None:
        quote_line = f"현재가: {live_quote['price']:g} / {live_quote.get('source', 'quote')}"
        if live_quote.get("change_pct") is not None:
            quote_line += f" / {live_quote['change_pct']:+g}%"
        if live_quote.get("timestamp"):
            quote_line += f" / {live_quote['timestamp']}"
        message_lines.append(quote_line)
        volume_text = _format_int(live_quote.get("volume") or live_quote.get("regularMarketVolume"))
        if volume_text:
            message_lines.append(f"거래량: {volume_text}")
    elif live_quote.get("error"):
        message_lines.append(f"현재가 확인 실패: {live_quote['error']}")
    message_lines.append(f"테마: {', '.join(themes[:3]) if themes else '매핑 없음'}")
    if technical_snapshot:
        support = technical_snapshot.get("support")
        resistance = technical_snapshot.get("resistance")
        if support is not None or resistance is not None:
            message_lines.append(f"지지/저항: 지지 {support if support is not None else 'n/a'} / 저항 {resistance if resistance is not None else 'n/a'}")
    message_lines.append(f"추격/눌림 판단: {_alert_action_judgment(alert_name, live_quote, technical_snapshot)}")
    if options_report and options_report.get("available"):
        for line in list(options_report.get("focus_lines") or [])[:4]:
            message_lines.append(str(line))
    elif options_report and options_report.get("summary"):
        message_lines.append(str(options_report.get("summary")))
    summary = agent_payload.get("summary")
    if summary:
        message_lines.append(f"분석: {summary}")
    try:
        message_lines.extend(build_yfinance_signal_lines(symbol, max_lines=4))
    except Exception as exc:
        message_lines.append(f"YF Pack: {symbol} / 호출 실패: {exc}")
    for item in list(agent_payload.get("focus") or [])[:6]:
        message_lines.append(str(item))
    next_actions = list(agent_payload.get("next_actions") or [])[:2]
    for item in next_actions:
        message_lines.append(f"다음: {item}")

    return {
        "status": "ok",
        "symbol": symbol,
        "trigger": {
            "price": price,
            "time": trigger_time,
            "interval": interval,
            "alert": alert_name,
        },
        "agent_request": agent_request,
        "live_quote": live_quote,
        "agent_payload": agent_payload,
        "message_lines": message_lines,
        "message": "\n".join(message_lines),
    }


def verify_webhook_secret(headers: dict[str, str], query: dict[str, list[str]], expected_secret: str | None) -> bool:
    if not expected_secret:
        return True
    lower_headers = {str(k).lower(): str(v) for k, v in headers.items()}
    candidates = [
        lower_headers.get("x-tradingview-secret"),
        lower_headers.get("x-webhook-secret"),
        lower_headers.get("x-api-key"),
    ]
    auth = lower_headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        candidates.append(auth.split(" ", 1)[1])
    for key in ["secret", "token", "key"]:
        candidates.extend(query.get(key, []))
    return any(candidate == expected_secret for candidate in candidates if candidate is not None)
