from __future__ import annotations

from typing import Any

try:
    from .market_data import fetch_price_history
except ImportError:  # direct script execution
    from market_data import fetch_price_history


def _simple_sma(values: list[float], period: int) -> float:
    window = values[-period:] if len(values) >= period else values
    return round(sum(window) / len(window), 2)


def _simple_rsi(values: list[float], period: int = 14) -> float:
    if len(values) < 2:
        return 50.0
    changes = [values[idx] - values[idx - 1] for idx in range(1, len(values))]
    window = changes[-period:] if len(changes) >= period else changes
    gains = [change for change in window if change > 0]
    losses = [-change for change in window if change < 0]
    avg_gain = sum(gains) / len(window) if window else 0.0
    avg_loss = sum(losses) / len(window) if window else 0.0
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def build_technical_snapshot(symbol: str) -> dict[str, Any]:
    closes = fetch_price_history(symbol)
    latest = round(closes[-1], 2)
    sma20 = _simple_sma(closes, 20)
    sma50 = _simple_sma(closes, 50)
    sma200 = _simple_sma(closes, 200)
    rsi14 = _simple_rsi(closes, 14)
    ema12 = _simple_sma(closes, 12)
    ema26 = _simple_sma(closes, 26)
    macd = round(ema12 - ema26, 2)
    signal = round(macd * 0.8, 2)
    hist = round(macd - signal, 2)
    support = round(min(closes[-20:]), 2)
    resistance = round(max(closes[-20:]), 2)

    if latest >= sma20 >= sma50:
        trend = "상승 추세"
    elif latest <= sma20 <= sma50:
        trend = "하락 추세"
    else:
        trend = "박스권/혼조"

    if rsi14 >= 70:
        momentum = "과열 구간"
    elif rsi14 <= 30:
        momentum = "과매도 구간"
    else:
        momentum = "중립 구간"

    if latest > resistance * 0.98 and hist > 0:
        interpretation = "저항 돌파 시도 구간이라 추세 추종 관점이지만 과열 체크 필요"
        action_bias = "손절 경계"
        event_tags = ["저항 돌파 시도", "과열 경계"] if rsi14 >= 70 else ["저항 돌파 시도"]
        stop_price = round(sma20, 2)
    elif latest < support * 1.02 and rsi14 < 40:
        interpretation = "지지 테스트 구간이라 반등 확인 전까지는 관망 우선"
        action_bias = "관망 관점"
        event_tags = ["지지 이탈 위험"]
        stop_price = round(support * 0.98, 2)
    else:
        interpretation = "지지/저항 사이 중립 구간이라 추격보다 확인 매매가 유리"
        action_bias = "매수 관점" if latest >= sma20 and hist >= 0 else "관망 관점"
        if rsi14 >= 70:
            event_tags = ["과열 경계"]
        elif action_bias == "매수 관점":
            event_tags = ["저항 돌파 시도"]
        else:
            event_tags = ["지지 이탈 위험"]
        stop_price = round(support * 0.99, 2)

    stop_distance_pct = round(((latest - stop_price) / latest) * 100, 2) if latest else 0.0
    event_text = f" / {', '.join(event_tags)}" if event_tags else ""
    brief_line = f"차트 한줄: {symbol} / {trend} / RSI {rsi14:.2f} / {action_bias}{event_text} / 손절 {stop_price:.2f} ({stop_distance_pct:+.2f}%)"

    return {
        "symbol": symbol,
        "latest": latest,
        "sma20": sma20,
        "sma50": sma50,
        "sma200": sma200,
        "rsi14": rsi14,
        "macd": macd,
        "signal": signal,
        "hist": hist,
        "support": support,
        "resistance": resistance,
        "stop_price": stop_price,
        "stop_distance_pct": stop_distance_pct,
        "trend": trend,
        "momentum": momentum,
        "interpretation": interpretation,
        "action_bias": action_bias,
        "event_tags": event_tags,
        "brief_line": brief_line,
    }
