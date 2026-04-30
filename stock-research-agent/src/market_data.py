from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

import requests


USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

DEFAULT_NEWS = {
    "NVDA": "AI 인프라 수요와 실적 기대가 동시에 과열되는지 체크 필요",
    "TSLA": "마진 압박과 판매 둔화 반복 여부 확인 필요",
    "AAPL": "서비스 성장 방어력과 중국 판매 둔화 충돌 관찰",
    "MSFT": "Azure 성장과 AI capex 부담 사이 균형 확인 필요",
    "AMZN": "AWS 성장 회복과 리테일 마진 방어력 동시 체크 필요",
    "META": "광고 성장과 AI 투자비 증가의 균형을 체크해야 함",
    "GOOGL": "검색 방어력과 클라우드 성장, AI 경쟁 구도를 같이 봐야 함",
    "AMD": "데이터센터 확장 기대와 AI 경쟁력 검증이 동시에 필요",
    "AVGO": "AI 네트워킹·커스텀 칩 기대와 고객 집중 리스크를 같이 체크",
    "TSM": "첨단 공정 수요와 지정학 리스크를 동시에 체크 필요",
    "PLTR": "상업 부문 성장 지속성과 밸류에이션 부담 확인 필요",
    "QQQ": "빅테크 실적과 금리 방향성이 ETF 흐름에 직접 반영됨",
    "SPY": "미국 대형주 전반 흐름과 매크로 이벤트 영향 체크 필요",
    "SOXX": "반도체 사이클 기대와 변동성 확대를 같이 봐야 함",
    "005930.KS": "메모리 업황 회복과 HBM 수요 지속 여부가 핵심",
    "000660.KS": "HBM 기대는 강하지만 업황 변동성도 같이 큼",
}

DEFAULT_EARNINGS_DAYS = {
    "NVDA": 6,
    "TSLA": 11,
    "AAPL": 8,
    "MSFT": 5,
    "AMZN": 9,
    "META": 7,
    "GOOGL": 10,
    "AMD": 12,
    "AVGO": 14,
    "TSM": 4,
    "PLTR": 13,
    "QQQ": 15,
    "SPY": 16,
    "SOXX": 17,
    "005930.KS": 20,
    "000660.KS": 18,
}


def _fetch_json(url: str) -> dict[str, Any] | None:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def _fetch_text(url: str) -> str | None:
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
        response.raise_for_status()
        return response.text
    except Exception:
        request = Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urlopen(request, timeout=20) as response:
                return response.read().decode("utf-8", errors="replace")
        except (URLError, TimeoutError, OSError):
            return None


def fetch_price_snapshot(symbol: str) -> dict[str, Any]:
    quote_symbol = quote(symbol)
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote_symbol}?range=5d&interval=1d"
    payload = _fetch_json(url)
    now = datetime.now(timezone.utc).isoformat()

    if payload:
        result = ((payload.get("chart") or {}).get("result") or [None])[0] or {}
        meta = result.get("meta") or {}
        indicators = result.get("indicators") or {}
        quotes = (indicators.get("quote") or [{}])[0]
        closes = quotes.get("close") or []
        opens = quotes.get("open") or []
        valid_closes = [float(item) for item in closes if item is not None]
        valid_opens = [float(item) for item in opens if item is not None]
        if valid_closes:
            latest = valid_closes[-1]
            previous = valid_closes[-2] if len(valid_closes) >= 2 else (valid_opens[-1] if valid_opens else latest)
            pct_change = 0.0 if previous == 0 else round(((latest - previous) / previous) * 100, 2)
            return {
                "symbol": symbol,
                "collected_at": now,
                "price": round(latest, 2),
                "pct_change": pct_change,
                "source": "yahoo_finance",
                "note": f"exchange={meta.get('exchangeName', 'unknown')}",
            }

    yfinance_snapshot = fetch_price_snapshot_yfinance(symbol)
    if yfinance_snapshot:
        return yfinance_snapshot

    fallback_price = float(100 + (sum(ord(c) for c in symbol) % 200))
    fallback_change = round(((sum(ord(c) for c in symbol) % 15) - 7) * 0.8, 2)
    return {
        "symbol": symbol,
        "collected_at": now,
        "price": fallback_price,
        "pct_change": fallback_change,
        "source": "fallback",
        "note": "live fetch unavailable; deterministic fallback used",
    }


def fetch_price_snapshot_yfinance(symbol: str) -> dict[str, Any] | None:
    """Optional yfinance fallback.

    yfinance is intentionally not a hard dependency. If it is not installed or
    Yahoo blocks the call, keep the existing raw Yahoo chart path/fallback alive.
    """
    try:
        import yfinance as yf  # type: ignore
    except Exception:
        return None

    try:
        ticker = yf.Ticker(symbol)
        fast_info = getattr(ticker, "fast_info", None) or {}
        price = (
            fast_info.get("last_price")
            or fast_info.get("lastPrice")
            or fast_info.get("regularMarketPrice")
            or fast_info.get("currentPrice")
        )
        previous = fast_info.get("previous_close") or fast_info.get("previousClose") or fast_info.get("regularMarketPreviousClose")
        if price is None:
            info = getattr(ticker, "info", None) or {}
            price = info.get("regularMarketPrice") or info.get("currentPrice")
            previous = previous or info.get("regularMarketPreviousClose") or info.get("previousClose")
        if price is None:
            return None
        price_float = float(price)
        previous_float = float(previous) if previous not in (None, 0) else price_float
        pct_change = 0.0 if previous_float == 0 else round(((price_float - previous_float) / previous_float) * 100, 2)
        exchange = fast_info.get("exchange") or fast_info.get("exchangeName") or "unknown"
        return {
            "symbol": symbol,
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "price": round(price_float, 2),
            "pct_change": pct_change,
            "source": "yfinance",
            "note": f"exchange={exchange}; optional yfinance fallback",
        }
    except Exception:
        return None


def fetch_symbol_news(symbol: str) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc).isoformat()
    headline = DEFAULT_NEWS.get(symbol, f"{symbol} 관련 주요 뉴스 흐름 확인 필요")
    query = quote(symbol)
    return [
        {
            "symbol": symbol,
            "headline": headline,
            "url": f"https://finance.yahoo.com/quote/{query}",
            "source": "seed",
            "collected_at": now,
        }
    ]


def fetch_earnings_event(symbol: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc)

    if not symbol.endswith('.KS'):
        html = _fetch_text(f"https://finance.yahoo.com/quote/{quote(symbol)}/")
        if html:
            match = re.search(r'title="Earnings Date">\s*Earnings Date\s*</span>\s*<span[^>]*class="value[^"]*">([^<]+)</span>', html, re.I)
            if match:
                raw_value = match.group(1).strip()
                date_match = re.search(r'([A-Z][a-z]{2}\s+\d{1,2},\s+\d{4})', raw_value)
                if date_match:
                    earnings_date = datetime.strptime(date_match.group(1), "%b %d, %Y").date().isoformat()
                    session = "unknown"
                    lowered = raw_value.lower()
                    if 'before market open' in lowered or 'before open' in lowered:
                        session = 'before_open'
                    elif 'after market close' in lowered or 'after close' in lowered:
                        session = 'after_close'
                    return {
                        "symbol": symbol,
                        "earnings_date": earnings_date,
                        "session": session,
                        "source": "yahoo_quote_html",
                        "note": f"Yahoo quote page earnings date: {raw_value}",
                        "collected_at": now.isoformat(),
                    }

    offset_days = DEFAULT_EARNINGS_DAYS.get(symbol, 14)
    earnings_date = (now + timedelta(days=offset_days)).date().isoformat()
    session = "after_close" if sum(ord(c) for c in symbol) % 2 == 0 else "before_open"
    return {
        "symbol": symbol,
        "earnings_date": earnings_date,
        "session": session,
        "source": "seed",
        "note": f"미국주 메인 워치리스트 기준 가상 earnings seed ({offset_days}일 후)",
        "collected_at": now.isoformat(),
    }


def fetch_price_history(symbol: str, range_period: str = "6mo", interval: str = "1d") -> list[float]:
    quote_symbol = quote(symbol)
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote_symbol}?range={range_period}&interval={interval}"
    payload = _fetch_json(url)
    if payload:
        result = ((payload.get("chart") or {}).get("result") or [None])[0] or {}
        indicators = result.get("indicators") or {}
        quotes = (indicators.get("quote") or [{}])[0]
        closes = quotes.get("close") or []
        valid_closes = [float(item) for item in closes if item is not None]
        if len(valid_closes) >= 30:
            return valid_closes

    yfinance_history = fetch_price_history_yfinance(symbol, range_period=range_period, interval=interval)
    if len(yfinance_history) >= 30:
        return yfinance_history

    seed = sum(ord(c) for c in symbol)
    base = float(80 + (seed % 120))
    trend = ((seed % 11) - 5) / 10
    history: list[float] = []
    price = base
    for idx in range(90):
        seasonal = ((idx % 7) - 3) * 0.35
        drift = trend + seasonal / 10
        price = max(5.0, price + drift)
        history.append(round(price, 2))
    return history


def fetch_price_history_yfinance(symbol: str, range_period: str = "6mo", interval: str = "1d") -> list[float]:
    """Optional yfinance fallback for technical snapshots."""
    try:
        import yfinance as yf  # type: ignore
    except Exception:
        return []

    try:
        history = yf.Ticker(symbol).history(period=range_period, interval=interval, auto_adjust=False)
        closes = history["Close"].dropna().tolist()
        return [float(item) for item in closes if item is not None]
    except Exception:
        return []
