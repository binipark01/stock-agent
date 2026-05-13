"""KRX theme money-flow and leader-stock scan."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

try:
    from ...watchlists import load_watchlist
except ImportError:  # pragma: no cover - direct script fallback
    from watchlists import load_watchlist

USER_AGENT = "Mozilla/5.0 (stock-research-agent)"

THEME_DISPLAY_NAMES = {
    "krx_stockcrew_semiconductors": "반도체/HBM",
    "krx_stockcrew_battery": "2차전지",
    "krx_stockcrew_power_infra": "전력/전선/전력인프라",
    "krx_stockcrew_defense": "방산",
    "krx_stockcrew_shipbuilding": "조선/기자재",
    "krx_stockcrew_robotics": "로봇",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().replace(microsecond=0).isoformat()


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace("%", "")
    if text.startswith("+"):
        text = text[1:]
    if text.startswith("--"):
        text = "-" + text.lstrip("-")
    try:
        return float(text)
    except ValueError:
        return None


def _pct_from_quote(quote_row: dict[str, Any]) -> float | None:
    for key in ("pct_change", "change_pct", "regularMarketChangePercent"):
        value = _to_float(quote_row.get(key))
        if value is not None:
            return value
    price = _to_float(quote_row.get("price") or quote_row.get("regularMarketPrice") or quote_row.get("current_price"))
    previous = _to_float(
        quote_row.get("previous_close")
        or quote_row.get("regularMarketPreviousClose")
        or quote_row.get("prev_close")
    )
    if price is None or previous in (None, 0):
        return None
    return (price - previous) / previous * 100.0


def _price_from_quote(quote_row: dict[str, Any]) -> float | None:
    return _to_float(quote_row.get("price") or quote_row.get("regularMarketPrice") or quote_row.get("current_price"))


def _trade_value_from_quote(quote_row: dict[str, Any]) -> float:
    trade_value = _to_float(quote_row.get("trade_value") or quote_row.get("trading_value") or quote_row.get("amount"))
    if trade_value is not None:
        return max(0.0, trade_value)
    price = _price_from_quote(quote_row)
    volume = _to_float(quote_row.get("volume") or quote_row.get("regularMarketVolume"))
    if price is None or volume is None:
        return 0.0
    return max(0.0, price * volume)


def _flow_score(row: dict[str, Any]) -> float:
    score = 0.0
    for key, weight in (("foreign_net_buy", 1.1), ("institution_net_buy", 1.1), ("program_net_buy", 1.4)):
        value = _to_float(row.get(key))
        if value is None:
            continue
        if value > 0:
            score += weight
        elif value < 0:
            score -= weight
    return score


def _symbol_key(symbol: str) -> str:
    return str(symbol).upper().strip()


def _theme_lists(watchlist_data: dict[str, Any]) -> dict[str, list[str]]:
    lists = watchlist_data.get("lists") or {}
    return {
        key: list(symbols or [])
        for key, symbols in lists.items()
        if key.startswith("krx_stockcrew_") and key != "krx_stockcrew_leaders"
    }


def _format_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"


def _format_krw(value: float) -> str:
    if value >= 1_0000_0000_0000:
        return f"{value / 1_0000_0000_0000:.1f}조"
    if value >= 1_0000_0000:
        return f"{value / 1_0000_0000:.0f}억"
    if value >= 1_0000:
        return f"{value / 1_0000:.0f}만"
    return f"{value:.0f}"


def _build_stock_row(symbol: str, quote_row: dict[str, Any]) -> dict[str, Any] | None:
    pct = _pct_from_quote(quote_row)
    price = _price_from_quote(quote_row)
    trade_value = _trade_value_from_quote(quote_row)
    if pct is None and trade_value <= 0:
        return None
    flow = _flow_score(quote_row)
    liquidity_score = math.log10(trade_value + 1.0) / 2.5 if trade_value > 0 else 0.0
    pct_score = pct or 0.0
    leader_score = pct_score * 1.7 + liquidity_score + flow
    name = quote_row.get("name") or quote_row.get("shortName") or quote_row.get("symbol") or symbol
    return {
        "symbol": symbol,
        "code": symbol.split(".")[0],
        "name": name,
        "price": price,
        "pct_change": pct,
        "trade_value": trade_value,
        "foreign_net_buy": _to_float(quote_row.get("foreign_net_buy")),
        "institution_net_buy": _to_float(quote_row.get("institution_net_buy")),
        "program_net_buy": _to_float(quote_row.get("program_net_buy")),
        "leader_score": round(leader_score, 3),
        "flow_score": round(flow, 3),
    }


def build_krx_theme_leader_report(
    watchlist_data: dict[str, Any] | None = None,
    quotes: dict[str, dict[str, Any]] | None = None,
    *,
    collected_at: str | None = None,
    top_n: int = 5,
) -> dict[str, Any]:
    """Rank KRX themes first, then rank leader stocks inside each theme."""
    watchlist_data = watchlist_data or load_watchlist()
    quotes = {_symbol_key(k): dict(v) for k, v in (quotes or {}).items() if isinstance(v, dict)}
    collected_at = collected_at or _now_iso()
    themes: list[dict[str, Any]] = []

    for theme_key, symbols in _theme_lists(watchlist_data).items():
        stocks = []
        for raw_symbol in symbols:
            symbol = _symbol_key(raw_symbol)
            quote_row = quotes.get(symbol)
            if not quote_row:
                continue
            quote_row.setdefault("symbol", symbol)
            stock = _build_stock_row(symbol, quote_row)
            if stock:
                stocks.append(stock)
        if not stocks:
            continue
        stocks.sort(key=lambda row: row["leader_score"], reverse=True)
        pct_values = [row["pct_change"] for row in stocks if row.get("pct_change") is not None]
        avg_pct = sum(pct_values) / len(pct_values) if pct_values else 0.0
        breadth = sum(1 for value in pct_values if value > 0) / len(pct_values) * 100.0 if pct_values else 0.0
        total_trade_value = sum(row.get("trade_value") or 0.0 for row in stocks)
        flow_score = sum(row.get("flow_score") or 0.0 for row in stocks)
        leader = stocks[0]
        money_flow_score = (
            avg_pct * 2.2
            + breadth / 18.0
            + math.log10(total_trade_value + 1.0) / 2.2
            + flow_score
            + max(0.0, leader.get("pct_change") or 0.0) * 0.9
        )
        themes.append(
            {
                "theme_key": theme_key,
                "theme_name": THEME_DISPLAY_NAMES.get(theme_key, theme_key.replace("krx_stockcrew_", "")),
                "money_flow_score": round(money_flow_score, 3),
                "average_pct_change": round(avg_pct, 3),
                "breadth_positive_pct": round(breadth, 1),
                "total_trade_value": round(total_trade_value, 3),
                "leader": leader,
                "stocks": stocks[:top_n],
                "covered_symbols": len(stocks),
            }
        )

    themes.sort(key=lambda row: row["money_flow_score"], reverse=True)
    focus_lines = [f"어느 테마에 돈이 들어오나: {len(themes)}개 KRX 테마 비교 / 기준 {collected_at}"]
    if themes:
        theme_bits = []
        for theme in themes[:top_n]:
            leader = theme["leader"]
            theme_bits.append(
                f"{theme['theme_name']} 점수 {theme['money_flow_score']:.1f} / 평균 {_format_pct(theme['average_pct_change'])} / "
                f"상승비율 {theme['breadth_positive_pct']:.0f}% / 대장 {leader['symbol']} {_format_pct(leader.get('pct_change'))}"
            )
        focus_lines.append("주도테마: " + " | ".join(theme_bits))
        for theme in themes[: min(3, top_n)]:
            leaders = " / ".join(
                f"{stock['symbol']} {_format_pct(stock.get('pct_change'))} 거래대금 {_format_krw(stock.get('trade_value') or 0)}"
                for stock in theme.get("stocks", [])[:3]
            )
            focus_lines.append(f"{theme['theme_name']} 내부 대장 후보: {leaders}")
    else:
        focus_lines.append("주도테마: quote 데이터 부족으로 판단 불가")

    return {
        "mode": "krx_theme_leader_scan",
        "summary": f"국장 주도테마/대장주 스캔: {themes[0]['theme_name']} 우위" if themes else "국장 주도테마/대장주 스캔: 데이터 부족",
        "collected_at": collected_at,
        "themes": themes,
        "focus_lines": focus_lines,
        "next_actions": [
            "1순위: 점수 상위 테마의 대장주가 거래대금/고가권을 유지하는지 확인",
            "2순위: 같은 테마 2~3등이 같이 따라오는지 확인해 주도테마 지속성 판단",
            "수급 확정 표현은 개별종목 krx_symbol_flow_v2로 외인/기관/프로그램을 재확인",
        ],
        "caveats": [
            "테마 스캔은 후보 발견용이며 주문/자동매매가 아님",
            "quote 기반 거래대금은 가격*거래량 proxy일 수 있음",
        ],
    }


def build_krx_theme_leader_response(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "agent": "stock-research-agent",
        "mode": "krx_theme_leader_scan",
        "summary": report.get("summary") or "국장 주도테마/대장주 스캔",
        "symbols": [theme.get("leader", {}).get("symbol") for theme in report.get("themes", [])[:5] if theme.get("leader")],
        "focus": list(report.get("focus_lines") or []),
        "next_actions": list(report.get("next_actions") or []),
        "features": ["krx", "theme_leader", "watchlist"],
        "data": {"krx_theme_leader_scan": report},
    }


def fetch_yahoo_quote(symbol: str) -> dict[str, Any] | None:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol)}?range=5d&interval=1d"
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None
    result = ((payload.get("chart") or {}).get("result") or [None])[0]
    if not result:
        return None
    meta = result.get("meta") or {}
    quote_data = (((result.get("indicators") or {}).get("quote") or [{}])[0])
    closes = [v for v in quote_data.get("close") or [] if v is not None]
    volumes = [v for v in quote_data.get("volume") or [] if v is not None]
    price = meta.get("regularMarketPrice") or (closes[-1] if closes else None)
    prev = meta.get("previousClose") or (closes[-2] if len(closes) >= 2 else None)
    volume = meta.get("regularMarketVolume") or (volumes[-1] if volumes else None)
    return {
        "symbol": symbol,
        "price": price,
        "previous_close": prev,
        "volume": volume,
        "currency": meta.get("currency"),
        "exchange": meta.get("exchangeName"),
        "timestamp": meta.get("regularMarketTime"),
    }


def fetch_krx_theme_quotes(watchlist_data: dict[str, Any] | None = None, *, limit: int = 50) -> dict[str, dict[str, Any]]:
    watchlist_data = watchlist_data or load_watchlist()
    symbols: list[str] = []
    for values in _theme_lists(watchlist_data).values():
        for symbol in values:
            key = _symbol_key(symbol)
            if key not in symbols:
                symbols.append(key)
    quotes: dict[str, dict[str, Any]] = {}
    for symbol in symbols[:limit]:
        row = fetch_yahoo_quote(symbol)
        if row:
            quotes[symbol] = row
    return quotes
