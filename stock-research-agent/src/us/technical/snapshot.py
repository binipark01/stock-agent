from __future__ import annotations

import math
from typing import Any

try:
    from ..market_data.core import fetch_price_history, fetch_price_ohlcv_history
except ImportError:  # direct script execution
    from market_data import fetch_price_history, fetch_price_ohlcv_history


def _simple_sma(values: list[float], period: int) -> float:
    window = values[-period:] if len(values) >= period else values
    return round(sum(window) / len(window), 2) if window else 0.0


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


def _ema_series(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    multiplier = 2 / (period + 1)
    ema_values = [float(values[0])]
    for value in values[1:]:
        ema_values.append((float(value) - ema_values[-1]) * multiplier + ema_values[-1])
    return ema_values


def _stddev(values: list[float]) -> float:
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return math.sqrt(variance)


def _bollinger_bands(closes: list[float], period: int = 20, width: float = 2.0) -> dict[str, float]:
    window = closes[-period:] if len(closes) >= period else closes
    middle = sum(window) / len(window) if window else 0.0
    deviation = _stddev(window)
    upper = middle + width * deviation
    lower = middle - width * deviation
    latest = closes[-1] if closes else 0.0
    span = upper - lower
    percent_b = ((latest - lower) / span) if span else 0.5
    width_pct = (span / middle) * 100 if middle else 0.0
    return {
        "bb_upper": round(upper, 2),
        "bb_middle": round(middle, 2),
        "bb_lower": round(lower, 2),
        "bb_percent_b": round(percent_b, 2),
        "bb_width_pct": round(width_pct, 2),
    }


def _macd(closes: list[float]) -> dict[str, float | str]:
    ema12_series = _ema_series(closes, 12)
    ema26_series = _ema_series(closes, 26)
    macd_series = [fast - slow for fast, slow in zip(ema12_series, ema26_series)]
    signal_series = _ema_series(macd_series, 9)
    macd_value = macd_series[-1] if macd_series else 0.0
    signal_value = signal_series[-1] if signal_series else 0.0
    hist_value = macd_value - signal_value
    prev_hist = (macd_series[-2] - signal_series[-2]) if len(macd_series) >= 2 and len(signal_series) >= 2 else hist_value
    if hist_value > prev_hist:
        direction = "hist 상승"
    elif hist_value < prev_hist:
        direction = "hist 하락"
    else:
        direction = "hist 보합"
    return {
        "ema12": round(ema12_series[-1], 2) if ema12_series else 0.0,
        "ema26": round(ema26_series[-1], 2) if ema26_series else 0.0,
        "macd": round(macd_value, 2),
        "signal": round(signal_value, 2),
        "hist": round(hist_value, 2),
        "macd_direction": direction,
    }


def _slow_stochastic(closes: list[float], highs: list[float], lows: list[float], period: int = 14, smooth: int = 3) -> dict[str, float | str]:
    if not closes:
        return {"stoch_k": 50.0, "stoch_d": 50.0, "stoch_signal": "중립"}
    if len(highs) != len(closes) or len(lows) != len(closes):
        highs = closes
        lows = closes

    k_values: list[float] = []
    for idx in range(len(closes)):
        start = max(0, idx - period + 1)
        high = max(highs[start : idx + 1])
        low = min(lows[start : idx + 1])
        span = high - low
        k_values.append(50.0 if span == 0 else ((closes[idx] - low) / span) * 100)

    latest_k = k_values[-1]
    d_window = k_values[-smooth:] if len(k_values) >= smooth else k_values
    latest_d = sum(d_window) / len(d_window) if d_window else 50.0

    if latest_k >= 80 and latest_d >= 80:
        signal = "과열"
    elif latest_k <= 20 and latest_d <= 20:
        signal = "과매도"
    elif latest_k > latest_d:
        signal = "상향 우위"
    elif latest_k < latest_d:
        signal = "하향 우위"
    else:
        signal = "중립"

    return {"stoch_k": round(latest_k, 2), "stoch_d": round(latest_d, 2), "stoch_signal": signal}


def _atr(closes: list[float], highs: list[float], lows: list[float], period: int = 14) -> float:
    if len(closes) < 2:
        return 0.0
    if len(highs) != len(closes) or len(lows) != len(closes):
        ranges = [abs(closes[idx] - closes[idx - 1]) for idx in range(1, len(closes))]
    else:
        ranges = []
        for idx in range(1, len(closes)):
            high = highs[idx]
            low = lows[idx]
            previous_close = closes[idx - 1]
            ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
    window = ranges[-period:] if len(ranges) >= period else ranges
    return round(sum(window) / len(window), 2) if window else 0.0


def _volume_ratio(volumes: list[float], period: int = 20) -> float | None:
    if not volumes:
        return None
    window = volumes[-period:] if len(volumes) >= period else volumes
    average = sum(window) / len(window) if window else 0.0
    if average == 0:
        return None
    return round(volumes[-1] / average, 2)


def _records_to_series(records: list[dict[str, Any]]) -> tuple[list[float], list[float], list[float], list[float]]:
    closes: list[float] = []
    highs: list[float] = []
    lows: list[float] = []
    volumes: list[float] = []
    for record in records:
        close = record.get("close")
        if close is None:
            continue
        try:
            close_float = float(close)
        except (TypeError, ValueError):
            continue
        closes.append(close_float)
        try:
            highs.append(float(record.get("high", close_float)))
        except (TypeError, ValueError):
            highs.append(close_float)
        try:
            lows.append(float(record.get("low", close_float)))
        except (TypeError, ValueError):
            lows.append(close_float)
        try:
            volumes.append(float(record.get("volume", 0) or 0))
        except (TypeError, ValueError):
            volumes.append(0.0)
    return closes, highs, lows, volumes


def _load_technical_series(symbol: str) -> tuple[list[float], list[float], list[float], list[float]]:
    records = fetch_price_ohlcv_history(symbol)
    closes, highs, lows, volumes = _records_to_series(records)
    if len(closes) >= 2:
        return closes, highs, lows, volumes
    closes = fetch_price_history(symbol)
    return closes, closes, closes, []


def build_technical_snapshot(symbol: str) -> dict[str, Any]:
    closes, highs, lows, volumes = _load_technical_series(symbol)
    latest = round(closes[-1], 2)
    sma20 = _simple_sma(closes, 20)
    sma50 = _simple_sma(closes, 50)
    sma200 = _simple_sma(closes, 200)
    rsi14 = _simple_rsi(closes, 14)
    macd_pack = _macd(closes)
    macd = float(macd_pack["macd"])
    signal = float(macd_pack["signal"])
    hist = float(macd_pack["hist"])
    support_series = lows[-20:] if lows else closes[-20:]
    resistance_series = highs[-20:] if highs else closes[-20:]
    support = round(min(support_series), 2)
    resistance = round(max(resistance_series), 2)
    bb_pack = _bollinger_bands(closes)
    stoch_pack = _slow_stochastic(closes, highs, lows)
    atr14 = _atr(closes, highs, lows)
    atr_pct = round((atr14 / latest) * 100, 2) if latest else 0.0
    volume_ratio20 = _volume_ratio(volumes)

    if latest >= sma20 >= sma50:
        trend = "상승 추세"
    elif latest <= sma20 <= sma50:
        trend = "하락 추세"
    else:
        trend = "박스권/혼조"

    if rsi14 >= 75:
        momentum = "과열 구간"
    elif rsi14 <= 25:
        momentum = "과매도 구간"
    else:
        momentum = "중립 구간"

    event_tags: list[str]
    base_stop_price: float
    if latest > resistance * 0.98 and hist > 0:
        interpretation = "저항 돌파 시도 구간이라 추세 추종 관점이지만 과열·거래량 확인 필요"
        action_bias = "손절 경계"
        event_tags = ["저항 돌파 시도", "과열 경계"] if rsi14 >= 75 else ["저항 돌파 시도"]
        base_stop_price = round(sma20, 2)
    elif latest < support * 1.02 and rsi14 < 40:
        interpretation = "지지 테스트 구간이라 반등 확인 전까지는 관망 우선"
        action_bias = "관망 관점"
        event_tags = ["지지 이탈 위험"]
        base_stop_price = round(support * 0.98, 2)
    else:
        interpretation = "지지/저항 사이 중립 구간이라 추격보다 확인 매매가 유리"
        action_bias = "매수 관점" if latest >= sma20 and hist >= 0 else "관망 관점"
        if rsi14 >= 75:
            event_tags = ["과열 경계"]
        elif action_bias == "매수 관점":
            event_tags = ["저항 돌파 시도"]
        else:
            event_tags = ["지지 이탈 위험"]
        base_stop_price = round(support * 0.99, 2)

    if bb_pack["bb_percent_b"] >= 0.9:
        event_tags.append("BB 상단 근접")
    elif bb_pack["bb_percent_b"] <= 0.1:
        event_tags.append("BB 하단 근접")
    if volume_ratio20 is not None and volume_ratio20 >= 1.5:
        event_tags.append("거래량 동반")
    event_tags = list(dict.fromkeys(event_tags))

    atr_stop_price = round(latest - (1.5 * atr14), 2) if atr14 else base_stop_price
    stop_price = round(max(base_stop_price, atr_stop_price), 2) if atr_stop_price < latest else base_stop_price
    stop_distance_pct = round(((latest - stop_price) / latest) * 100, 2) if latest else 0.0

    if atr_pct >= 6:
        risk_note = "고변동성: 포지션 축소/분할 진입 우선"
    elif atr_pct >= 3:
        risk_note = "중간 변동성: ATR 손절폭 확인"
    else:
        risk_note = "저변동성: 돌파 시 변동성 확장 여부 확인"

    event_text = f" / {', '.join(event_tags)}" if event_tags else ""
    volume_text = f" / Vol x{volume_ratio20:.2f}" if volume_ratio20 is not None else ""
    brief_line = (
        f"차트 한줄: {symbol} / {trend} / RSI {rsi14:.2f} / MACD {hist:+.2f}({macd_pack['macd_direction']}) "
        f"/ Stoch {stoch_pack['stoch_k']:.2f}/{stoch_pack['stoch_d']:.2f} {stoch_pack['stoch_signal']} "
        f"/ BB %B {bb_pack['bb_percent_b']:.2f} / ATR {atr_pct:.2f}%{volume_text} "
        f"/ {action_bias}{event_text} / 손절 {stop_price:.2f} ({stop_distance_pct:+.2f}%)"
    )

    return {
        "symbol": symbol,
        "latest": latest,
        "sma20": sma20,
        "sma50": sma50,
        "sma200": sma200,
        "rsi14": rsi14,
        "ema12": macd_pack["ema12"],
        "ema26": macd_pack["ema26"],
        "macd": macd,
        "signal": signal,
        "hist": hist,
        "macd_direction": macd_pack["macd_direction"],
        "stoch_k": stoch_pack["stoch_k"],
        "stoch_d": stoch_pack["stoch_d"],
        "stoch_signal": stoch_pack["stoch_signal"],
        "bb_upper": bb_pack["bb_upper"],
        "bb_middle": bb_pack["bb_middle"],
        "bb_lower": bb_pack["bb_lower"],
        "bb_percent_b": bb_pack["bb_percent_b"],
        "bb_width_pct": bb_pack["bb_width_pct"],
        "atr14": atr14,
        "atr_pct": atr_pct,
        "volume_ratio20": volume_ratio20,
        "support": support,
        "resistance": resistance,
        "stop_price": stop_price,
        "stop_distance_pct": stop_distance_pct,
        "trend": trend,
        "momentum": momentum,
        "interpretation": interpretation,
        "action_bias": action_bias,
        "event_tags": event_tags,
        "risk_note": risk_note,
        "brief_line": brief_line,
    }
