from __future__ import annotations

from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import math
import os
from typing import Any, Iterable

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

try:
    from .theme_config import (
        BENCHMARK_SYMBOLS,
        CORE_SECTOR_ETFS,
        DEFAULT_SECTOR_STRENGTH_SYMBOLS,
        REGIME_SYMBOLS,
        THEME_ETFS,
        USER_SUB_THEME_BASKETS,
        USER_THEME_BASKETS,
    )
except ImportError:  # direct script execution
    from us.sector.theme_config import (
        BENCHMARK_SYMBOLS,
        CORE_SECTOR_ETFS,
        DEFAULT_SECTOR_STRENGTH_SYMBOLS,
        REGIME_SYMBOLS,
        THEME_ETFS,
        USER_SUB_THEME_BASKETS,
        USER_THEME_BASKETS,
    )


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


def _pct_change(quote: dict[str, Any]) -> float | None:
    direct = _to_float(quote.get("pct_change") or quote.get("change_pct") or quote.get("regularMarketChangePercent"))
    if direct is not None:
        return round(direct, 2)
    price = _to_float(quote.get("price") or quote.get("last") or quote.get("last_price") or quote.get("regularMarketPrice"))
    previous = _to_float(quote.get("previous_close") or quote.get("previousClose") or quote.get("regularMarketPreviousClose"))
    if price is None or previous in (None, 0):
        return None
    return round(((price - float(previous)) / float(previous)) * 100, 2)


def _normalize_quote(symbol: str, raw: Any) -> dict[str, Any]:
    raw = raw or {}
    if isinstance(raw, dict) and isinstance(raw.get("quote"), dict):
        quote = dict(raw.get("quote") or {})
        quote.setdefault("source", raw.get("source"))
        quote.setdefault("timestamp", raw.get("collected_at"))
    elif isinstance(raw, dict):
        quote = dict(raw)
    else:
        quote = {}
    quote["symbol"] = str(quote.get("symbol") or symbol).upper()
    quote["pct_change"] = _pct_change(quote)
    return quote


def _fmt_pct(value: Any) -> str:
    numeric = _to_float(value)
    return "n/a" if numeric is None else f"{numeric:+.2f}%"


def _fmt_price(value: Any) -> str:
    numeric = _to_float(value)
    return "n/a" if numeric is None else f"{numeric:g}"


def _expected_session_label(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    if ZoneInfo is not None:
        et = now.astimezone(ZoneInfo("America/New_York"))
        kst = now.astimezone(ZoneInfo("Asia/Seoul"))
    else:  # pragma: no cover
        et = now.astimezone(timezone.utc)
        kst = now.astimezone(timezone.utc)
    et_minutes = et.hour * 60 + et.minute
    kst_minutes = kst.hour * 60 + kst.minute
    if et.weekday() < 5 and 4 * 60 <= et_minutes < 9 * 60 + 30:
        return "프리마켓"
    if et.weekday() < 5 and 9 * 60 + 30 <= et_minutes < 16 * 60:
        return "정규장"
    if et.weekday() < 5 and 16 * 60 <= et_minutes < 20 * 60:
        return "애프터장"
    # Toss day-market/주간거래 is useful to Korean users after the US close.
    # The exact window can change by broker; this covers the common daytime slot.
    if kst.weekday() < 5 and 10 * 60 <= kst_minutes < 18 * 60:
        return "토스 데이마켓/주간거래"
    return "휴장/데이터 없음"


def _session_needs_live_price(label: str | None) -> bool:
    return str(label or "") in {"프리마켓", "애프터장", "토스 데이마켓/주간거래"}


def _quote_session_label(quote: dict[str, Any]) -> str:
    label = str(quote.get("session_label") or "").strip()
    return label or _expected_session_label()


def _et_session_date_key(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        dt = datetime.fromtimestamp(float(value), timezone.utc)
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except Exception:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    if ZoneInfo is not None:
        dt = dt.astimezone(ZoneInfo("America/New_York"))
    return dt.date().isoformat()


def _display_meta_fields(quote: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "session_label": _quote_session_label(quote),
        "price_source": quote.get("price_source") or quote.get("source"),
        "pct_change_basis": quote.get("pct_change_basis"),
    }
    if quote.get("is_stale_regular_close"):
        fields["is_stale_regular_close"] = True
        fields["stale_note"] = quote.get("stale_note") or "정규장 종가 기준(확장/주간거래 실시간가 미확인)"
    return fields


def _row_price_session_text(row: dict[str, Any]) -> str:
    price = _to_float(row.get("price"))
    session = str(row.get("session_label") or "").strip()
    basis = str(row.get("pct_change_basis") or "").strip()
    stale = str(row.get("stale_note") or "").strip() if row.get("is_stale_regular_close") else ""
    parts: list[str] = []
    volume_text = _volume_inline_text(row)
    if price is not None:
        parts.append(f"가격 {_fmt_price(price)}{volume_text}")
    elif volume_text:
        parts.append(volume_text.removeprefix(" / "))
    if session:
        parts.append(session)
    if basis:
        parts.append(basis)
    if stale:
        parts.append(stale)
    return ", ".join(parts)


def _session_context_line(normalized: dict[str, dict[str, Any]]) -> str:
    spy = normalized.get("SPY", {})
    session = _quote_session_label(spy)
    source = str(spy.get("price_source") or spy.get("source") or "unknown")
    basis = str(spy.get("pct_change_basis") or "").strip()
    stale = spy.get("stale_note") if spy.get("is_stale_regular_close") else None
    if stale:
        detail = f"{session} / {stale} / source {source}"
    else:
        detail = f"{session} / {basis or '정규장 종가 대비'} / source {source}"
    return f"세션: {detail}"


_TECHNICAL_FIELD_NAMES = (
    "rsi14",
    "rsi14_prev",
    "rsi14_delta",
    "bollinger_mid",
    "bollinger_upper",
    "bollinger_lower",
    "bollinger_position_pct",
    "bollinger_position_prev",
    "bollinger_position_delta",
    "bollinger_bandwidth_pct",
    "bollinger_bandwidth_prev",
    "bollinger_bandwidth_delta",
    "bollinger_state",
    "ichimoku_conversion",
    "ichimoku_base",
    "ichimoku_span_a",
    "ichimoku_span_b",
    "ichimoku_cloud_top",
    "ichimoku_cloud_bottom",
    "ichimoku_cloud_distance_pct",
    "ichimoku_conversion_base_spread",
    "ichimoku_cloud_state",
    "macd_line",
    "macd_signal",
    "macd_histogram",
    "macd_line_prev",
    "macd_signal_prev",
    "macd_histogram_prev",
    "macd_histogram_delta",
    "macd_state",
    "stochastic_k",
    "stochastic_d",
    "stochastic_k_prev",
    "stochastic_d_prev",
    "stochastic_k_delta",
    "stochastic_d_delta",
    "stochastic_state",
)


def _technical_fields(quote: dict[str, Any]) -> dict[str, Any]:
    return {field: quote.get(field) for field in _TECHNICAL_FIELD_NAMES if quote.get(field) is not None}


def _clear_technical_fields(quote: dict[str, Any]) -> None:
    for field in _TECHNICAL_FIELD_NAMES:
        quote.pop(field, None)


def _fmt_indicator_value(value: Any, digits: int = 2) -> str:
    numeric = _to_float(value)
    if numeric is None:
        return "n/a"
    if digits <= 0:
        return f"{numeric:.0f}"
    text = f"{numeric:.{digits}f}".rstrip("0").rstrip(".")
    return text or "0"


def _fmt_signed(value: Any, digits: int = 0) -> str:
    numeric = _to_float(value)
    if numeric is None:
        return ""
    return f"{numeric:+.{digits}f}"


def _fmt_delta_paren(value: Any, digits: int = 0) -> str:
    signed = _fmt_signed(value, digits)
    return f"({signed})" if signed else ""


def _rsi_interpretation(rsi: float, delta: float | None = None) -> str:
    if delta is not None:
        if rsi >= 75 and delta > 0:
            return "과열권 추가 진입, 추격 부담 확대"
        if rsi >= 50 and delta >= 3:
            return "50선 위에서 재가속, 매수세 회복"
        if rsi >= 50 and delta <= -3:
            return "50선 위지만 탄력 둔화"
        if rsi <= 25 and delta < 0:
            return "과매도권 추가 진입, 반등 확인 전"
        if rsi < 45 and delta >= 3:
            return "저점권 반등 시도, 확인 필요"
        if rsi < 45 and delta <= -3:
            return "약세권 추가 이탈, 매수세 부재"
    if rsi >= 75:
        return "과열권, 추격 부담"
    if rsi <= 25:
        return "과매도권, 반등 확인 필요"
    if rsi >= 60:
        return "상승 탄력 양호"
    if rsi >= 45:
        return "중립권"
    if rsi >= 35:
        return "저점권이나 반등 탄력 약함"
    return "저점권이나 반등 확인 전"


def _macd_interpretation(line: float | None, signal: float | None, histogram: float | None, histogram_delta: float | None, state: str | None) -> str:
    if line is not None and signal is not None:
        relation = "신호선 위" if line > signal else "신호선 아래" if line < signal else "신호선 접점"
        if histogram is not None and histogram_delta is not None:
            if histogram > 0 and histogram_delta > 0:
                return f"{relation}·히스토그램 확대, 상승 모멘텀 강화"
            if histogram > 0 and histogram_delta < 0:
                return f"{relation}이나 히스토그램 축소, 상승 탄력 둔화"
            if histogram < 0 and histogram_delta < 0:
                return f"{relation}·히스토그램 악화, 하방 모멘텀 강화"
            if histogram < 0 and histogram_delta > 0:
                return f"{relation}이나 히스토그램 개선, 하락 둔화"
        if state == "상방":
            return f"{relation}, 상방 추세"
        if state == "하방":
            return f"{relation}, 하방 전환 주의"
    if state == "상방":
        return "상방 추세"
    if state == "하방":
        return "하방 추세"
    return "방향성 약함"


def _stochastic_interpretation(k_value: float | None, d_value: float | None, k_delta: float | None, state: str | None) -> str:
    relation = "K>D" if k_value is not None and d_value is not None and k_value > d_value else "K<D" if k_value is not None and d_value is not None and k_value < d_value else "K≈D"
    if state == "과열" or (k_value is not None and k_value >= 80):
        if relation == "K>D":
            return "과열권 K>D 유지, 강하지만 꺾이면 눌림"
        return "과열권에서 K<D, 단기 꺾임 주의"
    if state == "침체" or (k_value is not None and k_value <= 20):
        if relation == "K>D":
            return "침체권 K>D 회복 시도, 반등 확인"
        return "침체권 K<D, 반등 확인 필요"
    if k_delta is not None and k_delta < -3:
        return f"중립권 {relation} 약화"
    if k_delta is not None and k_delta > 3:
        return f"중립권 {relation} 개선"
    return f"중립권 {relation}, 방향 확인"


def _ichimoku_interpretation(state: str, spread: float | None = None) -> str:
    bullish_cross = spread is not None and spread > 0
    bearish_cross = spread is not None and spread < 0
    if "위" in state:
        if bullish_cross:
            return "중기 상승추세·구름 지지"
        return "구름 위지만 전환/기준선 확인 필요"
    if "아래" in state:
        if bearish_cross:
            return "중기 하락추세·구름 저항"
        return "구름 아래, 회복 확인 필요"
    if bullish_cross:
        return "구름 안이나 전환선 우위, 돌파 확인"
    if bearish_cross:
        return "추세 확인 필요"
    return "추세 확인 필요"


def _bollinger_interpretation(state: str, position: float | None, position_delta: float | None = None, bandwidth_delta: float | None = None) -> str:
    expanding = (bandwidth_delta is not None and bandwidth_delta > 0) or (position_delta is not None and position_delta > 3)
    contracting = bandwidth_delta is not None and bandwidth_delta < 0
    if "상단" in state or (position is not None and position >= 80):
        if expanding:
            return "상단 확장, 추격 부담"
        return "상단권, 추격 부담"
    if "하단" in state or (position is not None and position <= 20):
        if expanding:
            return "하단 이탈 확대, 칼잡기 위험"
        return "낙폭 확대, 반등 확인 필요"
    if contracting:
        return "밴드 수축, 방향성 대기"
    return "방향성 확인 필요"


def _technical_summary(row: dict[str, Any]) -> str:
    rsi = _to_float(row.get("rsi14"))
    rsi_delta = _to_float(row.get("rsi14_delta"))
    macd_hist = _to_float(row.get("macd_histogram"))
    macd_hist_delta = _to_float(row.get("macd_histogram_delta"))
    stoch_k = _to_float(row.get("stochastic_k"))
    stoch_delta = _to_float(row.get("stochastic_k_delta"))
    bb_position = _to_float(row.get("bollinger_position_pct"))
    bb_state = str(row.get("bollinger_state") or "")

    trend_positive = (macd_hist is not None and macd_hist > 0) and (rsi is not None and rsi >= 50)
    trend_negative = (macd_hist is not None and macd_hist < 0) and (rsi is not None and rsi < 50)
    momentum_improving = sum(
        1
        for value in (rsi_delta, macd_hist_delta, stoch_delta)
        if value is not None and value > 0
    ) >= 2
    momentum_weakening = sum(
        1
        for value in (rsi_delta, macd_hist_delta, stoch_delta)
        if value is not None and value < 0
    ) >= 2
    overheated = (rsi is not None and rsi >= 75) or (stoch_k is not None and stoch_k >= 80) or (bb_position is not None and bb_position >= 80) or "상단" in bb_state
    washed_out = (rsi is not None and rsi <= 25) or (stoch_k is not None and stoch_k <= 20) or (bb_position is not None and bb_position <= 20) or "하단" in bb_state

    if trend_positive and momentum_improving and overheated:
        return "모멘텀 개선 중이나 과열권, 눌림/돌파 확인"
    if trend_positive and momentum_improving:
        return "모멘텀 개선 중, 돌파 지속 확인"
    if trend_positive and momentum_weakening:
        return "상방은 유지되나 모멘텀 둔화, 추격 자제"
    if trend_negative and momentum_weakening:
        return "모멘텀 악화, 반등 확인 전 회피"
    if momentum_weakening:
        return "상승은 있지만 모멘텀 둔화, 돌파 확인"
    if overheated:
        return "단기 과열 부담, 추격보다 눌림 대기"
    if washed_out:
        return "낙폭은 크지만 반등 신호 확인 필요"
    return "방향성 혼재, 돌파 확인 전 분할/대기"


def _technical_suffix(row: dict[str, Any]) -> str:
    parts: list[str] = []

    rsi = _to_float(row.get("rsi14"))
    rsi_delta = _to_float(row.get("rsi14_delta"))
    if rsi is not None:
        parts.append(f"RSI {rsi:.0f}{_fmt_delta_paren(rsi_delta, 0)}: {_rsi_interpretation(rsi, rsi_delta)}")

    macd_line = _to_float(row.get("macd_line"))
    macd_signal = _to_float(row.get("macd_signal"))
    macd_hist = _to_float(row.get("macd_histogram"))
    macd_hist_delta = _to_float(row.get("macd_histogram_delta"))
    macd_state = str(row.get("macd_state") or "")
    if macd_line is not None and macd_signal is not None:
        hist_text = f" h{_fmt_signed(macd_hist, 2)}{_fmt_delta_paren(macd_hist_delta, 2)}" if macd_hist is not None else ""
        parts.append(
            f"MACD {_fmt_indicator_value(macd_line)}/{_fmt_indicator_value(macd_signal)}{hist_text}: "
            f"{_macd_interpretation(macd_line, macd_signal, macd_hist, macd_hist_delta, macd_state or None)}"
        )
    elif macd_state:
        parts.append(f"MACD {macd_state}: {_macd_interpretation(macd_line, macd_signal, macd_hist, macd_hist_delta, macd_state)}")

    stoch_k = _to_float(row.get("stochastic_k"))
    stoch_d = _to_float(row.get("stochastic_d"))
    stoch_k_delta = _to_float(row.get("stochastic_k_delta"))
    stoch_state = str(row.get("stochastic_state") or "")
    if stoch_k is not None and stoch_d is not None:
        parts.append(
            f"Stochastic Slow {stoch_k:.0f}/{stoch_d:.0f}{_fmt_delta_paren(stoch_k_delta, 0)}: "
            f"{_stochastic_interpretation(stoch_k, stoch_d, stoch_k_delta, stoch_state or None)}"
        )
    elif stoch_state:
        parts.append(f"Stochastic Slow {stoch_state}: {_stochastic_interpretation(stoch_k, stoch_d, stoch_k_delta, stoch_state)}")

    bb_state = str(row.get("bollinger_state") or "")
    bb_position = _to_float(row.get("bollinger_position_pct"))
    bb_position_delta = _to_float(row.get("bollinger_position_delta"))
    bb_bandwidth_delta = _to_float(row.get("bollinger_bandwidth_delta"))
    if bb_state:
        bb_value = f"{bb_position:.0f}%{_fmt_delta_paren(bb_position_delta, 0)} {bb_state}" if bb_position is not None else bb_state
        parts.append(f"BB {bb_value}: {_bollinger_interpretation(bb_state, bb_position, bb_position_delta, bb_bandwidth_delta)}")

    if parts:
        parts.append(f"종합: {_technical_summary(row)}")
    return " — " + "; ".join(parts) if parts else ""


def _fmt_trading_value(value: Any) -> str:
    numeric = _to_float(value)
    if numeric is None:
        return "n/a"
    if abs(numeric) >= 1_000_000_000:
        return f"${numeric / 1_000_000_000:.1f}B"
    if abs(numeric) >= 1_000_000:
        return f"${numeric / 1_000_000:.1f}M"
    if abs(numeric) >= 1_000:
        return f"${numeric / 1_000:.1f}K"
    return f"${numeric:.0f}"


def _fmt_volume(value: Any) -> str:
    numeric = _to_float(value)
    if numeric is None:
        return "n/a"
    if abs(numeric) >= 1_000_000_000:
        return f"{numeric / 1_000_000_000:.1f}B"
    if abs(numeric) >= 1_000_000:
        return f"{numeric / 1_000_000:.1f}M"
    if abs(numeric) >= 1_000:
        return f"{numeric / 1_000:.1f}K"
    return f"{numeric:.0f}"


def _first_numeric(*values: Any) -> float | None:
    for value in values:
        numeric = _to_float(value)
        if numeric is not None:
            return numeric
    return None


def _first_positive_numeric(*values: Any) -> float | None:
    for value in values:
        numeric = _to_float(value)
        if numeric is not None and numeric > 0:
            return numeric
    return None


def _quote_day_volume(quote: dict[str, Any]) -> float | None:
    positive = _first_positive_numeric(quote.get("day_volume"), quote.get("volume"), quote.get("regularMarketVolume"))
    if positive is not None:
        return positive
    return _first_numeric(quote.get("day_volume"), quote.get("volume"), quote.get("regularMarketVolume"))


def _quote_previous_volume(quote: dict[str, Any]) -> float | None:
    return _first_numeric(quote.get("previous_volume"), quote.get("previousRegularMarketVolume"))


def _quote_volume_vs_previous_pct(quote: dict[str, Any]) -> float | None:
    direct = _first_numeric(quote.get("volume_vs_previous_pct"), quote.get("volumeVsPreviousPct"))
    if direct is not None:
        return round(direct, 1)
    day_volume = _quote_day_volume(quote)
    previous_volume = _quote_previous_volume(quote)
    if day_volume is None or previous_volume in (None, 0):
        return None
    return round(((day_volume - float(previous_volume)) / float(previous_volume)) * 100, 1)


def _quote_volume_fields(quote: dict[str, Any]) -> dict[str, Any]:
    return {
        "day_volume": _quote_day_volume(quote),
        "previous_volume": _quote_previous_volume(quote),
        "volume_vs_previous_pct": _quote_volume_vs_previous_pct(quote),
    }


def _aggregate_volume_fields(rows: list[dict[str, Any]]) -> dict[str, Any]:
    day_values = [_quote_day_volume(row) for row in rows]
    day_values = [value for value in day_values if value is not None]
    previous_values = [_to_float(row.get("previous_volume")) for row in rows]
    previous_values = [value for value in previous_values if value is not None]
    day_total = sum(day_values) if day_values else None
    previous_total = sum(previous_values) if previous_values else None
    volume_vs_previous_pct = None
    if day_total is not None and previous_total not in (None, 0):
        volume_vs_previous_pct = round(((day_total - float(previous_total)) / float(previous_total)) * 100, 1)
    return {
        "day_volume": round(day_total) if day_total is not None else None,
        "previous_volume": round(previous_total) if previous_total is not None else None,
        "volume_vs_previous_pct": volume_vs_previous_pct,
    }


def _volume_inline_text(row: dict[str, Any]) -> str:
    day_volume = _quote_day_volume(row)
    previous_volume = _to_float(row.get("previous_volume"))
    if day_volume is None and previous_volume is None:
        return ""
    volume_vs_previous_pct = _quote_volume_vs_previous_pct(row)
    if day_volume is not None and previous_volume is not None:
        pct_text = f"({_fmt_pct(volume_vs_previous_pct)})" if volume_vs_previous_pct is not None else ""
        return f" / 거래량 {_fmt_volume(day_volume)}/{_fmt_volume(previous_volume)}{pct_text}"
    if day_volume is not None:
        return f" / 거래량 {_fmt_volume(day_volume)}"
    return f" / 거래량 n/a/{_fmt_volume(previous_volume)}"


def _quote_volume(quote: dict[str, Any]) -> float | None:
    return _quote_day_volume(quote)


def _quote_trading_value(quote: dict[str, Any]) -> float | None:
    direct = _to_float(quote.get("trading_value") or quote.get("turnover") or quote.get("dollar_volume"))
    if direct is not None:
        return direct
    volume = _quote_volume(quote)
    price = _to_float(quote.get("price") or quote.get("last") or quote.get("last_price") or quote.get("regularMarketPrice"))
    if volume is None or price is None:
        return None
    return volume * price


def _quote_previous_day_pct(quote: dict[str, Any]) -> float | None:
    return _first_numeric(quote.get("previous_day_pct_change"), quote.get("previous_session_pct_change"))


def _quote_previous_day_volume(quote: dict[str, Any]) -> float | None:
    return _first_numeric(quote.get("previous_day_volume"), quote.get("previous_session_volume"))


def _quote_previous_day_trading_value(quote: dict[str, Any]) -> float | None:
    direct = _first_numeric(quote.get("previous_day_trading_value"), quote.get("previous_session_trading_value"))
    if direct is not None:
        return direct
    close = _first_numeric(quote.get("previous_day_close"), quote.get("previous_session_close"))
    volume = _quote_previous_day_volume(quote)
    if close is None or volume is None:
        return None
    return close * volume


def _quote_trading_value_vs_previous_pct(quote: dict[str, Any]) -> float | None:
    direct = _first_numeric(quote.get("trading_value_vs_previous_pct"), quote.get("turnover_vs_previous_pct"))
    if direct is not None:
        return round(direct, 1)
    current = _quote_trading_value(quote)
    previous = _quote_previous_day_trading_value(quote)
    if current is None or previous in (None, 0):
        return None
    return round(((current - float(previous)) / float(previous)) * 100, 1)


def _previous_day_volume_inline_text(row: dict[str, Any]) -> str:
    volume = _quote_previous_day_volume(row)
    return f" / 전일 거래량 {_fmt_volume(volume)}" if volume is not None else ""


def _aggregate_previous_day_volume_fields(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = [_quote_previous_day_volume(row) for row in rows]
    values = [value for value in values if value is not None]
    return {"previous_day_volume": round(sum(values)) if values else None}


def _quote_vwap(quote: dict[str, Any]) -> float | None:
    return _to_float(quote.get("vwap") or quote.get("intraday_vwap") or quote.get("avg_price"))


def _quote_vwap_position_pct(quote: dict[str, Any]) -> float | None:
    direct = _to_float(quote.get("vwap_position_pct") or quote.get("price_vs_vwap_pct"))
    if direct is not None:
        return direct
    vwap = _quote_vwap(quote)
    price = _to_float(quote.get("price") or quote.get("last") or quote.get("last_price") or quote.get("regularMarketPrice"))
    if vwap in (None, 0) or price is None:
        return None
    return round(((price - float(vwap)) / float(vwap)) * 100, 2)


def _korean_regime_label(label: str) -> str:
    return {"risk_off": "리스크오프", "risk_on": "리스크온", "neutral": "중립"}.get(label, label)


def _classify_regime(quotes: dict[str, dict[str, Any]]) -> dict[str, Any]:
    signals: list[str] = []
    risk_off_score = 0
    risk_on_score = 0

    vix = quotes.get("^VIX", {})
    vix_price = _to_float(vix.get("price"))
    vix_pct = _pct_change(vix)
    if vix_price is not None:
        if vix_price >= 25:
            risk_off_score += 3
            signals.append(f"VIX {vix_price:g} 고위험권")
        elif vix_price >= 20:
            risk_off_score += 2
            signals.append(f"VIX {vix_price:g} 20 상회")
        elif vix_price <= 16:
            risk_on_score += 1
            signals.append(f"VIX {vix_price:g} 안정권")
    if vix_pct is not None and vix_pct >= 8:
        risk_off_score += 2
        signals.append(f"VIX 급등 {_fmt_pct(vix_pct)}")
    elif vix_pct is not None and vix_pct <= -5:
        risk_on_score += 1
        signals.append(f"VIX 하락 {_fmt_pct(vix_pct)}")
    vix9d_price = _to_float(quotes.get("^VIX9D", {}).get("price"))
    vix3m_price = _to_float(quotes.get("^VIX3M", {}).get("price"))
    if vix_price is not None and vix3m_price is not None:
        vix_curve = vix_price - vix3m_price
        if vix_curve >= 1:
            risk_off_score += 2
            signals.append(f"VIX 백워데이션 VIX-3M {vix_curve:+.1f}p")
        elif vix_curve <= -4 and vix_price < 20:
            risk_on_score += 1
            signals.append(f"VIX 콘탱고 VIX-3M {vix_curve:+.1f}p")
    if vix_price is not None and vix9d_price is not None and vix9d_price > vix_price + 1:
        risk_off_score += 1
        signals.append(f"단기 변동성 9D가 VIX 상회 {vix9d_price - vix_price:+.1f}p")

    for symbol, name in (("CL=F", "WTI"), ("BZ=F", "Brent")):
        quote = quotes.get(symbol, {})
        pct = _pct_change(quote)
        if pct is not None and pct >= 2:
            risk_off_score += 1
            signals.append(f"{name}/오일 상승 {_fmt_pct(pct)}")
        elif pct is not None and pct <= -2:
            risk_on_score += 1
            signals.append(f"{name}/오일 하락 {_fmt_pct(pct)}")
    oil_proxy_pcts = [_pct_change(quotes.get(symbol, {})) for symbol in ("XLE", "OIH", "XOP")]
    oil_proxy_pcts = [pct for pct in oil_proxy_pcts if pct is not None]
    crude_pcts = [_pct_change(quotes.get(symbol, {})) for symbol in ("CL=F", "BZ=F")]
    crude_pcts = [pct for pct in crude_pcts if pct is not None]
    if crude_pcts and max(crude_pcts) >= 4:
        risk_off_score += 1
        signals.append(f"유가 급등 평균 {_fmt_pct(sum(crude_pcts) / len(crude_pcts))}")
    if crude_pcts and oil_proxy_pcts and sum(crude_pcts) / len(crude_pcts) > 2 and sum(oil_proxy_pcts) / len(oil_proxy_pcts) < 0:
        risk_off_score += 1
        signals.append("유가 상승에도 에너지주 약세: 스태그/수요불안형")

    tnx_pct = _pct_change(quotes.get("^TNX", {}))
    if tnx_pct is not None and tnx_pct >= 1:
        risk_off_score += 1
        signals.append(f"10Y 금리 상승 {_fmt_pct(tnx_pct)}")
    elif tnx_pct is not None and tnx_pct <= -1:
        risk_on_score += 1
        signals.append(f"10Y 금리 하락 {_fmt_pct(tnx_pct)}")

    dxy_pct = _pct_change(quotes.get("DX-Y.NYB", {}))
    if dxy_pct is not None and dxy_pct >= 0.8:
        risk_off_score += 1
        signals.append(f"DXY 강세 {_fmt_pct(dxy_pct)}")
    elif dxy_pct is not None and dxy_pct <= -0.8:
        risk_on_score += 1
        signals.append(f"DXY 약세 {_fmt_pct(dxy_pct)}")

    if risk_off_score >= 3:
        label = "risk_off"
    elif risk_on_score > risk_off_score and risk_on_score >= 2:
        label = "risk_on"
    else:
        label = "neutral"
    if not signals:
        signals.append("VIX/오일/금리/DXY 뚜렷한 충격 없음")
    return {"label": label, "korean_label": _korean_regime_label(label), "risk_off_score": risk_off_score, "risk_on_score": risk_on_score, "signals": signals}


def _rank_sector_quotes(quotes: dict[str, dict[str, Any]], spy_pct: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    names = {**CORE_SECTOR_ETFS, **THEME_ETFS}
    for symbol, name in names.items():
        quote = quotes.get(symbol)
        if not quote:
            continue
        pct = _pct_change(quote)
        if pct is None:
            continue
        relative_to_spy = round(pct - spy_pct, 2)
        score = round(pct + relative_to_spy, 3)
        row = {
            "symbol": symbol,
            "name": name,
            "pct_change": round(pct, 2),
            "relative_to_spy_pct": relative_to_spy,
            "strength_score": score,
            "price": quote.get("price"),
            "volume": _quote_volume(quote),
            "trading_value": _quote_trading_value(quote),
            "source": quote.get("source"),
            "timestamp": quote.get("timestamp") or quote.get("collected_at"),
        }
        row.update(_display_meta_fields(quote))
        rows.append(row)
    return sorted(rows, key=lambda row: row["strength_score"], reverse=True)


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2


def _rank_metric_scores(rows: list[dict[str, Any]], field: str) -> dict[str, float]:
    values: list[tuple[str, float]] = []
    for row in rows:
        symbol = str(row.get("symbol") or "").strip()
        value = _to_float(row.get(field))
        if symbol and value is not None:
            values.append((symbol, value))
    if not values:
        return {}
    values.sort(key=lambda item: item[1], reverse=True)
    if len(values) == 1:
        return {values[0][0]: 100.0}
    if values[0][1] == values[-1][1]:
        return {symbol: 100.0 for symbol, _value in values}
    denominator = len(values) - 1
    scores: dict[str, float] = {}
    index = 0
    while index < len(values):
        value = values[index][1]
        end = index + 1
        while end < len(values) and values[end][1] == value:
            end += 1
        rank_scores = [100.0 * (denominator - rank) / denominator for rank in range(index, end)]
        tied_score = sum(rank_scores) / len(rank_scores)
        for symbol, _value in values[index:end]:
            scores[symbol] = round(tied_score, 3)
        index = end
    return scores


def _anchor_symbol_scores(rows: list[dict[str, Any]], anchor_symbols: Iterable[str] | None = None) -> dict[str, float]:
    if not anchor_symbols:
        return {}
    present_symbols = {str(row.get("symbol") or "").upper().strip() for row in rows}
    ordered = [
        str(symbol).upper().strip()
        for symbol in anchor_symbols
        if str(symbol).strip() and str(symbol).upper().strip() in present_symbols
    ]
    ordered = list(dict.fromkeys(ordered))
    if not ordered:
        return {}
    if len(ordered) == 1:
        return {ordered[0]: 100.0}
    denominator = len(ordered) - 1
    return {symbol: round(100.0 * (denominator - rank) / denominator, 3) for rank, symbol in enumerate(ordered)}


THEME_LEADER_CANDIDATE_LIMIT = 8


def _rank_theme_leaders(rows: list[dict[str, Any]], limit: int = 3, anchor_symbols: Iterable[str] | None = None) -> list[dict[str, Any]]:
    """테마 안 주도주를 등락률 단독이 아니라 돈/거래 증가까지 섞어 고른다.

    SPY 상대강도와 RSI는 의도적으로 점수에 넣지 않는다.
    """
    if not rows:
        return []
    pct_scores = _rank_metric_scores(rows, "pct_change")
    value_scores = _rank_metric_scores(rows, "trading_value")
    value_growth_scores = _rank_metric_scores(rows, "trading_value_vs_previous_pct")
    volume_growth_scores = _rank_metric_scores(rows, "volume_vs_previous_pct")
    theme_leader_scores = _anchor_symbol_scores(rows, anchor_symbols)
    scored: list[dict[str, Any]] = []
    for row in rows:
        symbol = str(row.get("symbol") or "").strip()
        if not symbol:
            continue
        pct_score = pct_scores.get(symbol, 0.0)
        value_score = value_scores.get(symbol, 0.0)
        value_growth_score = value_growth_scores.get(symbol, 0.0)
        volume_growth_score = volume_growth_scores.get(symbol, 0.0)
        theme_leader_score = theme_leader_scores.get(symbol.upper(), 0.0)
        leader_score = (
            pct_score * 0.35
            + value_score * 0.25
            + value_growth_score * 0.25
            + volume_growth_score * 0.05
            + theme_leader_score * 0.10
        )
        enriched = dict(row)
        enriched["leader_score"] = round(leader_score, 3)
        enriched["leader_score_basis"] = {
            "pct_change_rank": round(pct_score, 1),
            "trading_value_rank": round(value_score, 1),
            "trading_value_vs_previous_rank": round(value_growth_score, 1),
            "volume_vs_previous_rank": round(volume_growth_score, 1),
            "theme_leader_rank": round(theme_leader_score, 1),
        }
        scored.append(enriched)
    return sorted(
        scored,
        key=lambda row: (
            _to_float(row.get("leader_score")) or 0.0,
            _to_float(row.get("pct_change")) or -999.0,
            _to_float(row.get("trading_value")) or 0.0,
        ),
        reverse=True,
    )[:limit]


def _rank_theme_baskets(quotes: dict[str, dict[str, Any]], spy_pct: float) -> list[dict[str, Any]]:
    baskets: list[dict[str, Any]] = []
    for key, basket in USER_THEME_BASKETS.items():
        symbols = tuple(str(symbol).upper() for symbol in basket.get("symbols", ()))
        excluded = {str(symbol).upper() for symbol in basket.get("excluded_from_score", ())}
        constituents: list[dict[str, Any]] = []
        score_rows: list[dict[str, Any]] = []
        for symbol in symbols:
            quote = quotes.get(symbol)
            if not quote:
                continue
            pct = _pct_change(quote)
            if pct is None:
                continue
            row = {
                "symbol": symbol,
                "pct_change": round(pct, 2),
                "relative_to_spy_pct": round(pct - spy_pct, 2),
                "price": quote.get("price"),
                "volume": _quote_volume(quote),
                **_quote_volume_fields(quote),
                "trading_value": _quote_trading_value(quote),
                "previous_day_trading_value": _quote_previous_day_trading_value(quote),
                "trading_value_vs_previous_pct": _quote_trading_value_vs_previous_pct(quote),
                "pct_change_5m": _intraday_pct_change(quote, 5),
                "vwap": _quote_vwap(quote),
                "vwap_position_pct": _quote_vwap_position_pct(quote),
                "source": quote.get("source"),
                "timestamp": quote.get("timestamp") or quote.get("collected_at"),
                "score_eligible": symbol not in excluded,
            }
            row.update(_display_meta_fields(quote))
            row.update(_technical_fields(quote))
            constituents.append(row)
            if row["score_eligible"]:
                score_rows.append(row)
        if not score_rows:
            continue
        pct_values = [float(row["pct_change"]) for row in score_rows]
        trading_values = [_to_float(row.get("trading_value")) for row in score_rows]
        trading_values = [value for value in trading_values if value is not None]
        volume_fields = _aggregate_volume_fields(score_rows)
        avg_pct = sum(pct_values) / len(pct_values)
        median_pct = _median(pct_values)
        breadth_positive_pct = (sum(1 for value in pct_values if value > 0) / len(pct_values)) * 100
        avg_relative_to_spy = avg_pct - spy_pct
        breadth_bonus = (breadth_positive_pct - 50.0) / 25.0
        strength_score = avg_pct + avg_relative_to_spy + breadth_bonus
        leader_candidates = _rank_theme_leaders(score_rows, limit=THEME_LEADER_CANDIDATE_LIMIT, anchor_symbols=basket.get("anchor_symbols", ()))
        leaders = leader_candidates[:3]
        laggards = sorted(score_rows, key=lambda row: row["pct_change"])[:3]
        baskets.append(
            {
                "key": key,
                "name": str(basket.get("name") or key),
                "symbols": list(symbols),
                "covered_symbols": [row["symbol"] for row in constituents],
                "excluded_symbols": sorted(symbol for symbol in excluded if symbol in {row["symbol"] for row in constituents}),
                "constituents": sorted(constituents, key=lambda row: row["pct_change"], reverse=True),
                "score_symbols": [row["symbol"] for row in score_rows],
                "average_pct_change": round(avg_pct, 2),
                "median_pct_change": round(float(median_pct), 2) if median_pct is not None else None,
                "breadth_positive_pct": round(breadth_positive_pct, 1),
                "relative_to_spy_pct": round(avg_relative_to_spy, 2),
                "trading_value": round(sum(trading_values), 2) if trading_values else None,
                **volume_fields,
                "strength_score": round(strength_score, 3),
                "leader_candidates": leader_candidates,
                "leaders": leaders,
                "laggards": laggards,
            }
        )
    return sorted(baskets, key=lambda row: row["strength_score"], reverse=True)


def _rank_previous_day_theme_baskets(quotes: dict[str, dict[str, Any]], spy_previous_day_pct: float | None) -> list[dict[str, Any]]:
    baskets: list[dict[str, Any]] = []
    benchmark_pct = spy_previous_day_pct or 0.0
    for key, basket in USER_THEME_BASKETS.items():
        symbols = tuple(str(symbol).upper() for symbol in basket.get("symbols", ()))
        excluded = {str(symbol).upper() for symbol in basket.get("excluded_from_score", ())}
        constituents: list[dict[str, Any]] = []
        score_rows: list[dict[str, Any]] = []
        for symbol in symbols:
            quote = quotes.get(symbol)
            if not quote:
                continue
            pct = _quote_previous_day_pct(quote)
            if pct is None:
                continue
            row = {
                "symbol": symbol,
                "previous_day_pct_change": round(pct, 2),
                "pct_change": round(pct, 2),
                "relative_to_spy_pct": round(pct - benchmark_pct, 2),
                "previous_day_close": quote.get("previous_day_close"),
                "previous_day_volume": _quote_previous_day_volume(quote),
                "previous_day_trading_value": _quote_previous_day_trading_value(quote),
                "previous_day_date": quote.get("previous_day_date"),
                "source": quote.get("source"),
                "timestamp": quote.get("timestamp") or quote.get("collected_at"),
                "score_eligible": symbol not in excluded,
            }
            constituents.append(row)
            if row["score_eligible"]:
                score_rows.append(row)
        if not score_rows:
            continue
        pct_values = [float(row["previous_day_pct_change"]) for row in score_rows]
        trading_values = [_to_float(row.get("previous_day_trading_value")) for row in score_rows]
        trading_values = [value for value in trading_values if value is not None]
        volume_fields = _aggregate_previous_day_volume_fields(score_rows)
        avg_pct = sum(pct_values) / len(pct_values)
        median_pct = _median(pct_values)
        breadth_positive_pct = (sum(1 for value in pct_values if value > 0) / len(pct_values)) * 100
        avg_relative_to_spy = avg_pct - benchmark_pct
        breadth_bonus = (breadth_positive_pct - 50.0) / 25.0
        strength_score = avg_pct + avg_relative_to_spy + breadth_bonus
        leaders = sorted(score_rows, key=lambda row: row["previous_day_pct_change"], reverse=True)[:3]
        laggards = sorted(score_rows, key=lambda row: row["previous_day_pct_change"])[:3]
        session_dates = sorted(
            {
                str(row.get("previous_day_date"))
                for row in score_rows
                if row.get("previous_day_date") not in (None, "")
            }
        )
        baskets.append(
            {
                "key": key,
                "name": str(basket.get("name") or key),
                "symbols": list(symbols),
                "covered_symbols": [row["symbol"] for row in constituents],
                "excluded_symbols": sorted(symbol for symbol in excluded if symbol in {row["symbol"] for row in constituents}),
                "constituents": sorted(constituents, key=lambda row: row["previous_day_pct_change"], reverse=True),
                "score_symbols": [row["symbol"] for row in score_rows],
                "previous_day_average_pct_change": round(avg_pct, 2),
                "previous_day_median_pct_change": round(float(median_pct), 2) if median_pct is not None else None,
                "previous_day_breadth_positive_pct": round(breadth_positive_pct, 1),
                "previous_day_relative_to_spy_pct": round(avg_relative_to_spy, 2),
                "previous_day_trading_value": round(sum(trading_values), 2) if trading_values else None,
                "previous_day_date": session_dates[-1] if session_dates else None,
                **volume_fields,
                "strength_score": round(strength_score, 3),
                "leaders": leaders,
                "laggards": laggards,
            }
        )
    return sorted(baskets, key=lambda row: row["strength_score"], reverse=True)


def _rank_sub_theme_baskets(quotes: dict[str, dict[str, Any]], spy_pct: float) -> list[dict[str, Any]]:
    baskets: list[dict[str, Any]] = []
    parent_names = {key: str(value.get("name") or key) for key, value in USER_THEME_BASKETS.items()}
    for key, basket in USER_SUB_THEME_BASKETS.items():
        symbols = tuple(str(symbol).upper() for symbol in basket.get("symbols", ()))
        excluded = {str(symbol).upper() for symbol in basket.get("excluded_from_score", ())}
        parent_key = str(basket.get("parent") or "")
        parent_name = parent_names.get(parent_key, parent_key or "테마")
        constituents: list[dict[str, Any]] = []
        score_rows: list[dict[str, Any]] = []
        for symbol in symbols:
            quote = quotes.get(symbol)
            if not quote:
                continue
            pct = _pct_change(quote)
            if pct is None:
                continue
            row = {
                "symbol": symbol,
                "pct_change": round(pct, 2),
                "relative_to_spy_pct": round(pct - spy_pct, 2),
                "price": quote.get("price"),
                "volume": _quote_volume(quote),
                **_quote_volume_fields(quote),
                "trading_value": _quote_trading_value(quote),
                "previous_day_trading_value": _quote_previous_day_trading_value(quote),
                "trading_value_vs_previous_pct": _quote_trading_value_vs_previous_pct(quote),
                "pct_change_5m": _intraday_pct_change(quote, 5),
                "vwap": _quote_vwap(quote),
                "vwap_position_pct": _quote_vwap_position_pct(quote),
                "source": quote.get("source"),
                "timestamp": quote.get("timestamp") or quote.get("collected_at"),
                "score_eligible": symbol not in excluded,
            }
            row.update(_display_meta_fields(quote))
            row.update(_technical_fields(quote))
            constituents.append(row)
            if row["score_eligible"]:
                score_rows.append(row)
        if not score_rows:
            continue
        pct_values = [float(row["pct_change"]) for row in score_rows]
        trading_values = [_to_float(row.get("trading_value")) for row in score_rows]
        trading_values = [value for value in trading_values if value is not None]
        volume_fields = _aggregate_volume_fields(score_rows)
        avg_pct = sum(pct_values) / len(pct_values)
        median_pct = _median(pct_values)
        breadth_positive_pct = (sum(1 for value in pct_values if value > 0) / len(pct_values)) * 100
        avg_relative_to_spy = avg_pct - spy_pct
        breadth_bonus = (breadth_positive_pct - 50.0) / 25.0
        strength_score = avg_pct + avg_relative_to_spy + breadth_bonus
        leader_candidates = _rank_theme_leaders(score_rows, limit=THEME_LEADER_CANDIDATE_LIMIT, anchor_symbols=basket.get("anchor_symbols", ()))
        leaders = leader_candidates[:3]
        laggards = sorted(score_rows, key=lambda row: row["pct_change"])[:3]
        baskets.append(
            {
                "key": key,
                "name": str(basket.get("name") or key),
                "parent_key": parent_key,
                "parent_name": parent_name,
                "symbols": list(symbols),
                "covered_symbols": [row["symbol"] for row in constituents],
                "excluded_symbols": sorted(symbol for symbol in excluded if symbol in {row["symbol"] for row in constituents}),
                "constituents": sorted(constituents, key=lambda row: row["pct_change"], reverse=True),
                "score_symbols": [row["symbol"] for row in score_rows],
                "average_pct_change": round(avg_pct, 2),
                "median_pct_change": round(float(median_pct), 2) if median_pct is not None else None,
                "breadth_positive_pct": round(breadth_positive_pct, 1),
                "relative_to_spy_pct": round(avg_relative_to_spy, 2),
                "trading_value": round(sum(trading_values), 2) if trading_values else None,
                **volume_fields,
                "strength_score": round(strength_score, 3),
                "leader_candidates": leader_candidates,
                "leaders": leaders,
                "laggards": laggards,
            }
        )
    return sorted(baskets, key=lambda row: row["strength_score"], reverse=True)


def _line_for(prefix: str, rows: list[dict[str, Any]]) -> str:
    if not rows:
        return f"{prefix}: 데이터 부족"
    parts = [
        f"{row['name']} {row['symbol']} {_fmt_pct(row['pct_change'])} / SPY 대비 {_fmt_pct(row['relative_to_spy_pct'])}"
        for row in rows[:3]
    ]
    return f"{prefix}: " + " | ".join(parts)


def _theme_line_for(prefix: str, rows: list[dict[str, Any]]) -> str:
    if not rows:
        return f"{prefix}: 기준 해당 없음"
    parts = []
    for row in rows:
        leaders = ", ".join(f"{leader['symbol']} {_fmt_pct(leader['pct_change'])}" for leader in row.get("leaders", [])[:3])
        trading_value = row.get("trading_value")
        value_text = f" / 거래대금 {_fmt_trading_value(trading_value)}" if trading_value is not None else ""
        volume_text = _volume_inline_text(row)
        parts.append(
            f"{row['name']} 상승비율 {row['breadth_positive_pct']:.1f}%{value_text}{volume_text} / 주도 {leaders or 'n/a'}"
        )
    return f"{prefix}: " + " | ".join(parts)


def _positive_theme_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if (_to_float(row.get("average_pct_change")) or 0.0) > 0.0]


def _negative_theme_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if (_to_float(row.get("average_pct_change")) or 0.0) < 0.0]


def _positive_previous_day_theme_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if (_to_float(row.get("previous_day_average_pct_change")) or 0.0) > 0.0
        and (_to_float(row.get("previous_day_breadth_positive_pct")) or 0.0) >= 50.0
    ]


def _previous_day_leader_text(row: dict[str, Any]) -> str:
    symbol = str(row.get("symbol") or "").strip()
    if not symbol:
        return ""
    price = _fmt_price(row.get("previous_day_close"))
    price_text = f" / 전일종가 {price}" if price != "n/a" else ""
    return f"{symbol} {_fmt_pct(row.get('previous_day_pct_change'))}{price_text}{_previous_day_volume_inline_text(row)}"


def _previous_day_theme_line_for(prefix: str, rows: list[dict[str, Any]]) -> str:
    if not rows:
        return f"{prefix}: 기준 해당 없음"
    parts = []
    for row in rows:
        leaders = ", ".join(
            text
            for text in (_previous_day_leader_text(leader) for leader in row.get("leaders", [])[:3])
            if text
        )
        trading_value = row.get("previous_day_trading_value")
        value_text = f" / 전일 거래대금 {_fmt_trading_value(trading_value)}" if trading_value is not None else ""
        volume_text = _previous_day_volume_inline_text(row)
        parts.append(
            f"{row['name']} 전일 상승비율 {row['previous_day_breadth_positive_pct']:.1f}%{value_text}{volume_text} / 전일 주도 {leaders or 'n/a'}"
        )
    return f"{prefix}: " + " | ".join(parts)


def _sub_theme_line_for(prefix: str, rows: list[dict[str, Any]]) -> str:
    if not rows:
        return f"{prefix}: 데이터 부족"
    parts = []
    for row in rows[:3]:
        leaders = ", ".join(f"{leader['symbol']} {_fmt_pct(leader['pct_change'])}" for leader in row.get("leaders", [])[:3])
        trading_value = row.get("trading_value")
        value_text = f" / 거래대금 {_fmt_trading_value(trading_value)}" if trading_value is not None else ""
        volume_text = _volume_inline_text(row)
        parts.append(
            f"{row['parent_name']} > {row['name']} 평균 {_fmt_pct(row['average_pct_change'])} / 상승비율 {row['breadth_positive_pct']:.1f}%{value_text}{volume_text} / 주도 {leaders or 'n/a'}"
        )
    return f"{prefix}: " + " | ".join(parts)


def _build_rotation_alerts(strong_sub_themes: list[dict[str, Any]], weak_sub_themes: list[dict[str, Any]], limit: int = 2) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    used_pairs: set[tuple[str, str, str]] = set()
    for strong in strong_sub_themes:
        strong_parent = str(strong.get("parent_key") or "")
        if not strong_parent:
            continue
        strong_avg = _to_float(strong.get("average_pct_change"))
        if strong_avg is None or strong_avg <= 0:
            continue
        for weak in weak_sub_themes:
            weak_parent = str(weak.get("parent_key") or "")
            if weak_parent != strong_parent or weak.get("key") == strong.get("key"):
                continue
            weak_avg = _to_float(weak.get("average_pct_change"))
            if weak_avg is None or weak_avg >= 0:
                continue
            pair = (strong_parent, str(strong.get("key") or ""), str(weak.get("key") or ""))
            if pair in used_pairs:
                continue
            used_pairs.add(pair)
            into_leaders = [row for row in strong.get("leaders", []) if isinstance(row, dict)][:2]
            out_rows = [row for row in weak.get("leaders", []) if isinstance(row, dict)][:2]
            score_gap = (_to_float(strong.get("strength_score")) or 0.0) - (_to_float(weak.get("strength_score")) or 0.0)
            alerts.append(
                {
                    "parent_key": strong_parent,
                    "parent_name": strong.get("parent_name"),
                    "into_sub_theme_key": strong.get("key"),
                    "into_sub_theme": strong.get("name"),
                    "out_of_sub_theme_key": weak.get("key"),
                    "out_of_sub_theme": weak.get("name"),
                    "into_average_pct_change": round(float(strong_avg), 2),
                    "out_of_average_pct_change": round(float(weak_avg), 2),
                    "score_gap": round(score_gap, 3),
                    "into_leaders": into_leaders,
                    "out_of_examples": out_rows,
                    "interpretation": f"{strong.get('parent_name')} 내부 {strong.get('name')}로 자금 이동 / {weak.get('name')} 약세",
                }
            )
            break
    return sorted(alerts, key=lambda row: row["score_gap"], reverse=True)[:limit]


def _rotation_line(alerts: list[dict[str, Any]]) -> str:
    if not alerts:
        return "로테이션 해석: 뚜렷한 세부테마 내부 로테이션 없음"
    parts = []
    for alert in alerts[:2]:
        into = ", ".join(f"{row['symbol']} {_fmt_pct(row['pct_change'])}" for row in alert.get("into_leaders", [])[:2])
        out_of = ", ".join(f"{row['symbol']} {_fmt_pct(row['pct_change'])}" for row in alert.get("out_of_examples", [])[:2])
        parts.append(
            f"{alert['parent_name']} 내부 {alert['into_sub_theme']}로 자금 이동 / {alert['out_of_sub_theme']} 약세"
            f"(강세 {into or 'n/a'} vs 약세 {out_of or 'n/a'})"
        )
    return "로테이션 해석: " + " | ".join(parts)


def _rank_watchlist_movers(theme_baskets: list[dict[str, Any]], sub_theme_baskets: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    movers: list[dict[str, Any]] = []
    symbol_sub_themes: dict[str, dict[str, Any]] = {}
    for sub in sub_theme_baskets or []:
        for row in sub.get("constituents", []) or []:
            if not isinstance(row, dict) or not row.get("score_eligible", True):
                continue
            symbol = str(row.get("symbol") or "")
            if not symbol:
                continue
            previous = symbol_sub_themes.get(symbol)
            if previous is None or float(sub.get("strength_score") or 0) > float(previous.get("strength_score") or 0):
                symbol_sub_themes[symbol] = {
                    "key": sub.get("key"),
                    "name": sub.get("name"),
                    "parent_key": sub.get("parent_key"),
                    "parent_name": sub.get("parent_name"),
                    "strength_score": sub.get("strength_score"),
                }
    for basket in theme_baskets:
        theme_name = str(basket.get("name") or basket.get("key") or "테마")
        theme_key = str(basket.get("key") or theme_name)
        for row in basket.get("constituents", []) or []:
            if not isinstance(row, dict) or not row.get("score_eligible", True):
                continue
            pct = _to_float(row.get("pct_change"))
            if pct is None:
                continue
            relative_to_spy = _to_float(row.get("relative_to_spy_pct")) or 0.0
            mover_score = abs(pct) + max(relative_to_spy, 0.0)
            direction = "강세" if pct >= 0 else "약세"
            symbol = str(row.get("symbol") or "")
            sub_theme = symbol_sub_themes.get(symbol, {})
            sub_theme_name = str(sub_theme.get("name") or "")
            reason = f"{theme_name}>{sub_theme_name} 내부 {direction}" if sub_theme_name else f"{theme_name} 내부 {direction}"
            mover = {
                "symbol": symbol,
                "theme": theme_name,
                "theme_key": theme_key,
                "sub_theme": sub_theme_name or None,
                "sub_theme_key": sub_theme.get("key"),
                "pct_change": round(pct, 2),
                "relative_to_spy_pct": round(relative_to_spy, 2),
                "mover_score": round(mover_score, 3),
                "direction": direction,
                "reason": reason,
                "price": row.get("price"),
                "volume": row.get("volume"),
                "day_volume": row.get("day_volume"),
                "previous_volume": row.get("previous_volume"),
                "volume_vs_previous_pct": row.get("volume_vs_previous_pct"),
                "source": row.get("source"),
                "timestamp": row.get("timestamp"),
            }
            mover.update(_display_meta_fields(row))
            mover.update(_technical_fields(row))
            movers.append(mover)
    return sorted(movers, key=lambda row: row["mover_score"], reverse=True)


def _movers_line(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "오늘 먼저 볼 종목: 데이터 부족"
    parts = []
    for row in rows[:5]:
        scope = row.get("sub_theme") or row.get("theme")
        meta = _row_price_session_text(row)
        scope_text = f"{scope}; {meta}" if meta else str(scope)
        parts.append(f"{row['symbol']} {_fmt_pct(row['pct_change'])}({scope_text}){_technical_suffix(row)}")
    return "오늘 먼저 볼 종목: " + " | ".join(parts)


def _theme_leader_status_label(avg_pct: float | None, breadth_positive_pct: float | None) -> str:
    if avg_pct is None or breadth_positive_pct is None:
        return "데이터없음"
    if avg_pct >= 0.5 and breadth_positive_pct >= 60.0:
        return "주도"
    if avg_pct <= -0.5 and breadth_positive_pct <= 40.0:
        return "약함"
    return "혼조"


def _theme_leader_rows_from_quotes(quotes: dict[str, dict[str, Any]], basket: dict[str, Any]) -> list[dict[str, Any]]:
    symbols = tuple(str(symbol).upper() for symbol in basket.get("symbols", ()))
    excluded = {str(symbol).upper() for symbol in basket.get("excluded_from_score", ())}
    rows: list[dict[str, Any]] = []
    for symbol in symbols:
        if symbol in excluded:
            continue
        quote = quotes.get(symbol)
        if not quote:
            continue
        pct = _pct_change(quote)
        if pct is None:
            continue
        row = {
            "symbol": symbol,
            "pct_change": round(pct, 2),
            "price": quote.get("price"),
            **_quote_volume_fields(quote),
            "source": quote.get("source"),
            "timestamp": quote.get("timestamp") or quote.get("collected_at"),
        }
        row.update(_display_meta_fields(quote))
        row.update(_technical_fields(quote))
        rows.append(row)
    return sorted(rows, key=lambda row: row["pct_change"], reverse=True)


def _theme_leader_status_line(quotes: dict[str, dict[str, Any]]) -> str:
    parts: list[str] = []
    for _key, basket in USER_THEME_BASKETS.items():
        theme_name = str(basket.get("name") or _key)
        rows = _theme_leader_rows_from_quotes(quotes, basket)
        if not rows:
            parts.append(f"{theme_name}: n/a n/a 가격 n/a, 데이터없음")
            continue
        pct_values = [float(row["pct_change"]) for row in rows]
        avg_pct = sum(pct_values) / len(pct_values) if pct_values else None
        breadth = (sum(1 for value in pct_values if value > 0) / len(pct_values)) * 100 if pct_values else None
        leader = rows[0]
        meta = _row_price_session_text(leader) or "가격 n/a"
        status = _theme_leader_status_label(avg_pct, breadth)
        technical = _technical_suffix(leader)
        parts.append(f"{theme_name}: {leader['symbol']} {_fmt_pct(leader['pct_change'])} {meta}, {status}{technical}")
    return "테마별 대장주: " + " | ".join(parts)


def _theme_symbol_universe() -> set[str]:
    symbols: set[str] = set()
    for basket in USER_THEME_BASKETS.values():
        excluded = {str(symbol).upper() for symbol in basket.get("excluded_from_score", ())}
        for symbol in basket.get("symbols", ()):
            upper = str(symbol).upper()
            if upper not in excluded:
                symbols.add(upper)
    return symbols


def _current_strength_against_previous_close_line(quotes: dict[str, dict[str, Any]], limit: int = 5) -> str:
    theme_symbols = _theme_symbol_universe()
    rows: list[dict[str, Any]] = []
    for symbol in sorted(theme_symbols):
        quote = quotes.get(symbol)
        if not quote:
            continue
        price = _to_float(quote.get("price") or quote.get("last") or quote.get("last_price") or quote.get("regularMarketPrice"))
        previous = _to_float(quote.get("previous_close") or quote.get("previousClose") or quote.get("regularMarketPreviousClose"))
        pct = _pct_change(quote)
        if price is None or previous in (None, 0) or pct is None or pct <= 0:
            continue
        row = {
            "symbol": symbol,
            "price": price,
            "pct_change": pct,
            "source": quote.get("price_source") or quote.get("source"),
        }
        row.update(_quote_volume_fields(quote))
        rows.append(row)
    rows.sort(key=lambda row: row["pct_change"], reverse=True)
    if not rows:
        return "전일종가 대비 현재 강세: 데이터 부족 / 기준 전일 정규장 종가 대비 현재가 / 출처 Yahoo chart 1m includePrePost"
    parts = [f"{row['symbol']} {_fmt_pct(row['pct_change'])} 가격 {_fmt_price(row['price'])}{_volume_inline_text(row)}" for row in rows[:limit]]
    source = "Yahoo chart 1m includePrePost"
    return f"전일종가 대비 현재 강세: {' | '.join(parts)} / 기준 전일 정규장 종가 대비 현재가 / 출처 {source}"


def _etf_context_line(strong: list[dict[str, Any]], weak: list[dict[str, Any]]) -> str:
    strong_part = "데이터 부족"
    weak_part = "데이터 부족"
    if strong:
        row = strong[0]
        strong_part = f"강세 {row['name']} {row['symbol']} {_fmt_pct(row['pct_change'])}"
    if weak:
        row = weak[0]
        weak_part = f"약세 {row['name']} {row['symbol']} {_fmt_pct(row['pct_change'])}"
    return f"ETF 시장 참고: {strong_part} / {weak_part}"


_DISPLAY_BENCHMARKS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("NQ=F", "^IXIC"), "NASDAQ"),
    (("SPY",), "SPY"),
    (("SOXX",), "SOXX"),
    (("BTC-USD",), "BTCUSDT"),
    (("CL=F",), "WTI"),
    (("^VIX",), "VIX"),
)


def _benchmark_quote(normalized: dict[str, dict[str, Any]], symbols: tuple[str, ...]) -> dict[str, Any]:
    for symbol in symbols:
        quote = normalized.get(symbol)
        if isinstance(quote, dict) and _pct_change(quote) is not None:
            return quote
    return {}


def _benchmark_pct(normalized: dict[str, dict[str, Any]], symbols: tuple[str, ...]) -> float | None:
    return _pct_change(_benchmark_quote(normalized, symbols))


def _benchmark_intraday_pct(normalized: dict[str, dict[str, Any]], symbols: tuple[str, ...], minutes: int) -> float | None:
    for symbol in symbols:
        quote = normalized.get(symbol)
        if not isinstance(quote, dict):
            continue
        pct = _intraday_pct_change(quote, minutes)
        if pct is not None:
            return pct
    return None


def _benchmark_snapshot(normalized: dict[str, dict[str, Any]]) -> dict[str, float]:
    snapshot: dict[str, float] = {}
    for symbols, display in _DISPLAY_BENCHMARKS:
        pct = _benchmark_pct(normalized, symbols)
        if pct is not None:
            snapshot[display] = round(float(pct), 2)
    return snapshot


def _benchmark_context_line(normalized: dict[str, dict[str, Any]], collected_at: str) -> str:
    parts = []
    for symbols, display in _DISPLAY_BENCHMARKS:
        pct = _benchmark_pct(normalized, symbols)
        # Keep the benchmark label set stable in Telegram alerts even when a
        # quote provider temporarily misses one symbol, especially ^IXIC on
        # Windows/Yahoo. The value is explicit n/a rather than silently
        # dropping NASDAQ and making the whole benchmark line disappear.
        parts.append(f"{display} {_fmt_pct(pct) if pct is not None else 'n/a'}")
    context = " / ".join(parts) if parts else "데이터 부족"
    session = _quote_session_label(normalized.get("SPY", {}))
    stale = normalized.get("SPY", {}).get("stale_note") if normalized.get("SPY", {}).get("is_stale_regular_close") else None
    suffix = f" / 세션 {session}" if not stale else f" / 세션 {session} / {stale}"
    return f"장 분위기: {context}{suffix} / 기준시각 {collected_at}"


def _intraday_pct_change(quote: dict[str, Any], minutes: int) -> float | None:
    return _to_float(
        quote.get(f"pct_change_{minutes}m")
        or quote.get(f"change_{minutes}m_pct")
        or quote.get(f"pct_{minutes}m")
    )


def _infer_point_change_from_pct(price: float | None, pct: float | None) -> float | None:
    if price is None or pct is None:
        return None
    denominator = 1 + (pct / 100.0)
    if denominator <= 0:
        return None
    previous = price / denominator
    return round(price - previous, 2)


def _format_vix_intraday_change(label: str, price: float | None, pct: float | None) -> str | None:
    if pct is None:
        return None
    point_change = _infer_point_change_from_pct(price, pct)
    if point_change is None:
        return f"VIX {label} {_fmt_pct(pct)}"
    return f"VIX {label} {point_change:+.2f}pt({_fmt_pct(pct)})"


def _build_risk_spike_context(normalized: dict[str, dict[str, Any]]) -> dict[str, Any]:
    vix = normalized.get("^VIX", {})
    wti = normalized.get("CL=F", {})
    vix_price = _to_float(vix.get("price"))
    vix_5m = _intraday_pct_change(vix, 5)
    vix_15m = _intraday_pct_change(vix, 15)
    wti_5m = _intraday_pct_change(wti, 5)
    wti_15m = _intraday_pct_change(wti, 15)

    parts: list[str] = []
    triggers: list[str] = []
    score = 0

    vix_5m_pt = _infer_point_change_from_pct(vix_price, vix_5m)
    vix_15m_pt = _infer_point_change_from_pct(vix_price, vix_15m)
    if vix_5m is not None and (vix_5m >= 4.0 or (vix_5m_pt is not None and vix_5m_pt >= 0.6)):
        formatted = _format_vix_intraday_change("5m", vix_price, vix_5m)
        if formatted:
            parts.append(formatted)
        triggers.append("vix_5m_spike")
        score += 2
    elif vix_15m is not None and (vix_15m >= 7.0 or (vix_15m_pt is not None and vix_15m_pt >= 1.0)):
        formatted = _format_vix_intraday_change("15m", vix_price, vix_15m)
        if formatted:
            parts.append(formatted)
        triggers.append("vix_15m_spike")
        score += 2

    if wti_15m is not None and wti_15m >= 1.0:
        parts.append(f"WTI 15m {_fmt_pct(wti_15m)}")
        triggers.append("wti_15m_spike")
        score += 2
    elif wti_5m is not None and wti_5m >= 0.5:
        parts.append(f"WTI 5m {_fmt_pct(wti_5m)}")
        triggers.append("wti_5m_spike")
        score += 1

    market_parts: list[str] = []
    for symbols, display in ((("NQ=F", "^IXIC"), "NASDAQ"), (("SPY",), "SPY"), (("SOXX",), "SOXX")):
        pct = _benchmark_intraday_pct(normalized, symbols, 5)
        if pct is not None and pct <= -0.3:
            market_parts.append(f"{display} 5m {_fmt_pct(pct)}")
    if market_parts and triggers:
        parts.append(", ".join(market_parts[:3]))
        score += 1

    if not triggers:
        return {"active": False, "score": 0, "level": "stable", "triggers": [], "summary": ""}
    level = "risk_off" if score >= 4 else "watch"
    summary = " / ".join(parts)
    return {
        "active": True,
        "score": score,
        "level": level,
        "triggers": triggers,
        "summary": summary,
        "vix_5m_change_pct": vix_5m,
        "vix_5m_change_pt": vix_5m_pt,
        "vix_15m_change_pct": vix_15m,
        "vix_15m_change_pt": vix_15m_pt,
        "wti_5m_change_pct": wti_5m,
        "wti_15m_change_pct": wti_15m,
    }


def _build_flow_proxy_context(theme_baskets: list[dict[str, Any]], spy_pct: float) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for theme in theme_baskets:
        constituents = [row for row in theme.get("constituents", []) if row.get("score_eligible", True)]
        if not constituents:
            continue
        trading_value = _to_float(theme.get("trading_value"))
        breadth = _to_float(theme.get("breadth_positive_pct"))
        relative = _to_float(theme.get("relative_to_spy_pct"))
        avg_pct = _to_float(theme.get("average_pct_change"))
        vwap_above = [row for row in constituents if (_to_float(row.get("vwap_position_pct")) is not None and _to_float(row.get("vwap_position_pct")) >= 0)]
        intraday = sorted(
            [row for row in constituents if _to_float(row.get("pct_change_5m")) is not None],
            key=lambda row: _to_float(row.get("pct_change_5m")) or -999,
            reverse=True,
        )
        if not any(value is not None for value in (trading_value, breadth, relative, avg_pct)):
            continue
        score = 0
        signals: list[str] = []
        if trading_value is not None and trading_value >= 500_000_000:
            score += 2
            signals.append("거래대금")
        elif trading_value is not None and trading_value >= 100_000_000:
            score += 1
            signals.append("거래대금")
        if breadth is not None and breadth >= 70:
            score += 2
            signals.append("breadth")
        elif breadth is not None and breadth >= 60:
            score += 1
            signals.append("breadth")
        if relative is not None and relative >= 1.0:
            score += 2
            signals.append("상대강도")
        elif relative is not None and relative >= 0.5:
            score += 1
            signals.append("상대강도")
        if avg_pct is not None and avg_pct >= 1.0:
            score += 1
        if vwap_above:
            score += 1
            signals.append("VWAP")
        if intraday and (_to_float(intraday[0].get("pct_change_5m")) or 0) >= 0.5:
            score += 1
            signals.append("5m")
        if score < 5:
            continue
        intraday_text = ", ".join(
            f"{row['symbol']} {_fmt_pct(row.get('pct_change_5m'))}"
            for row in intraday[:2]
            if _to_float(row.get("pct_change_5m")) is not None
        )
        parts = [
            f"{theme.get('name') or theme.get('key')} 기관성 유입 의심",
            f"거래대금 {_fmt_trading_value(trading_value)}" if trading_value is not None else "거래대금 n/a",
            f"상승비율 {breadth:.1f}%" if breadth is not None else "상승비율 n/a",
            f"SPY 대비 {_fmt_pct(relative)}" if relative is not None else "SPY 대비 n/a",
        ]
        if intraday_text:
            parts.append(f"5m {intraday_text}")
        if vwap_above:
            parts.append(f"VWAP 위 {len(vwap_above)}종목")
        candidates.append(
            {
                "theme_key": theme.get("key"),
                "theme_name": theme.get("name"),
                "score": score,
                "signals": sorted(set(signals)),
                "summary": " / ".join(parts),
                "trading_value": trading_value,
                "breadth_positive_pct": breadth,
                "relative_to_spy_pct": relative,
                "vwap_above_count": len(vwap_above),
                "intraday_leaders": intraday[:3],
            }
        )
    candidates.sort(key=lambda row: (row.get("score") or 0, row.get("trading_value") or 0), reverse=True)
    if not candidates:
        return {"active": False, "candidates": [], "summary": ""}
    return {
        "active": True,
        "candidates": candidates[:3],
        "summary": candidates[0]["summary"],
        "note": "거래대금/VWAP/상대강도 기반 수급 proxy이며 실제 기관 순매수 단정 아님",
    }


def build_sector_strength_report(quotes: dict[str, Any], collected_at: str | None = None, top_n: int = 3) -> dict[str, Any]:
    normalized = {str(symbol).upper(): _normalize_quote(str(symbol), raw) for symbol, raw in (quotes or {}).items()}
    collected_at = collected_at or next((str(q.get("timestamp") or q.get("collected_at")) for q in normalized.values() if q.get("timestamp") or q.get("collected_at")), None) or datetime.now(timezone.utc).isoformat()

    spy_pct = _pct_change(normalized.get("SPY", {}))
    if spy_pct is None:
        return {
            "available": False,
            "summary": "섹터 강약: SPY 기준 데이터가 부족합니다",
            "collected_at": collected_at,
            "focus_lines": [
                "섹터 강약: SPY 기준 데이터가 부족합니다",
                _theme_leader_status_line(normalized),
            ],
            "next_actions": ["SPY와 주요 섹터/테마 quote가 들어오는지 먼저 확인"],
            "strong": [],
            "weak": [],
            "regime": {"label": "unavailable", "korean_label": "데이터 부족", "signals": []},
            "quotes": normalized,
        }

    ranked = _rank_sector_quotes(normalized, spy_pct)
    theme_baskets = _rank_theme_baskets(normalized, spy_pct)
    previous_day_theme_baskets = _rank_previous_day_theme_baskets(normalized, _quote_previous_day_pct(normalized.get("SPY", {})))
    sub_theme_baskets = _rank_sub_theme_baskets(normalized, spy_pct)
    watchlist_movers = _rank_watchlist_movers(theme_baskets, sub_theme_baskets)
    strong = ranked[:top_n]
    weak = sorted(ranked, key=lambda row: row["strength_score"])[:top_n]
    strong_themes = _positive_theme_rows(theme_baskets)
    weak_themes = _negative_theme_rows(sorted(theme_baskets, key=lambda row: row["strength_score"]))
    previous_day_strong_themes = _positive_previous_day_theme_rows(previous_day_theme_baskets)
    strong_sub_themes = sub_theme_baskets[:top_n]
    weak_sub_themes = sorted(sub_theme_baskets, key=lambda row: row["strength_score"])[:top_n]
    rotation_alerts = _build_rotation_alerts(strong_sub_themes, weak_sub_themes)
    regime = _classify_regime(normalized)
    risk_spikes = _build_risk_spike_context(normalized)
    flow_proxies = _build_flow_proxy_context(theme_baskets, spy_pct)
    regime_text = regime["korean_label"]
    if theme_baskets:
        leader = strong_themes[0]["name"] if strong_themes else "강한 테마 기준 해당 없음"
        laggard = weak_themes[0]["name"] if weak_themes else "약한 테마 기준 해당 없음"
        leader_summary = f"{leader} 주도" if strong_themes else leader
        laggard_summary = f"{laggard} 약세" if weak_themes else laggard
    else:
        leader = strong[0]["symbol"] if strong else "n/a"
        laggard = weak[0]["symbol"] if weak else "n/a"
        leader_summary = f"{leader} 주도"
        laggard_summary = f"{laggard} 약세"
    if strong_themes and weak_themes and strong_themes[0].get("key") == weak_themes[0].get("key") and strong_sub_themes and weak_sub_themes:
        leader = f"{strong_sub_themes[0]['parent_name']} > {strong_sub_themes[0]['name']}"
        laggard = f"{weak_sub_themes[0]['parent_name']} > {weak_sub_themes[0]['name']}"
    summary_prefix = "장중 테마 강약" if theme_baskets else "장중 섹터 강약"
    focus_lines = [
        f"장 분위기: {regime_text} / {'; '.join(regime['signals'][:3])}",
    ]
    if risk_spikes.get("active") and risk_spikes.get("summary"):
        focus_lines.append(f"분봉 리스크: {risk_spikes['summary']}")
    focus_lines.extend([
        _theme_line_for("강한 테마", strong_themes),
        _theme_line_for("약한 테마", weak_themes),
        _previous_day_theme_line_for("전날 강했던 테마", previous_day_strong_themes),
        _sub_theme_line_for("강한 세부테마", strong_sub_themes),
        _sub_theme_line_for("약한 세부테마", weak_sub_themes),
    ])
    if flow_proxies.get("active") and flow_proxies.get("summary"):
        focus_lines.append(f"수급 proxy: {flow_proxies['summary']}")
    focus_lines.extend([
        _rotation_line(rotation_alerts),
        _theme_leader_status_line(normalized),
        _current_strength_against_previous_close_line(normalized),
        _movers_line(watchlist_movers),
        _etf_context_line(strong, weak),
        _session_context_line(normalized),
        _benchmark_context_line(normalized, collected_at),
    ])
    next_actions = [
        "강한 테마가 SPY 대비 계속 우위인지 5분 뒤 재확인",
        "약한 테마 반등 매수는 VIX 안정과 SPY 회복 확인 후 판단",
    ]
    if flow_proxies.get("active"):
        next_actions.insert(0, "기관성 유입 의심은 실제 기관 순매수로 단정 금지")
    if risk_spikes.get("active"):
        next_actions.insert(0, "VIX/WTI 분봉 리스크 급등: 강한 테마도 추격보다 VWAP 눌림 대기")
    if rotation_alerts:
        top_rotation = rotation_alerts[0]
        next_actions.insert(
            0,
            f"{top_rotation['into_sub_theme']} 추격은 {top_rotation['out_of_sub_theme']} 회복 전까지 눌림/분할로 제한",
        )
    if regime["label"] == "risk_off":
        next_actions.insert(0, "리스크오프: 고베타/성장주 추격매수 비중 낮추고 손절선 짧게")
    elif regime["label"] == "risk_on":
        next_actions.insert(0, "리스크온: 주도 섹터 눌림에서만 후보 압축")

    return {
        "available": True,
        "summary": f"{summary_prefix}: {leader_summary} / {laggard_summary} / 장 분위기 {regime_text}",
        "collected_at": collected_at,
        "benchmarks": _benchmark_snapshot(normalized),
        "strong": strong,
        "weak": weak,
        "theme_baskets": theme_baskets,
        "strong_themes": strong_themes,
        "weak_themes": weak_themes,
        "previous_day_theme_baskets": previous_day_theme_baskets,
        "previous_day_strong_themes": previous_day_strong_themes,
        "sub_theme_baskets": sub_theme_baskets,
        "strong_sub_themes": strong_sub_themes,
        "weak_sub_themes": weak_sub_themes,
        "rotation_alerts": rotation_alerts,
        "watchlist_movers": watchlist_movers[:10],
        "regime": regime,
        "risk_spikes": risk_spikes,
        "flow_proxies": flow_proxies,
        "focus_lines": focus_lines,
        "next_actions": next_actions,
        "quotes": normalized,
    }


def _simple_quote_row(quotes: dict[str, dict[str, Any]], symbol: str) -> dict[str, Any]:
    quote = quotes.get(symbol, {})
    return {
        "symbol": symbol,
        "price": _to_float(quote.get("price")),
        "pct_change": _pct_change(quote),
        "pct_change_1m": _to_float(quote.get("pct_change_1m") or quote.get("change_1m_pct")),
        "pct_change_5m": _to_float(quote.get("pct_change_5m") or quote.get("change_5m_pct")),
        "pct_change_15m": _to_float(quote.get("pct_change_15m") or quote.get("change_15m_pct")),
        "source": quote.get("source"),
        "timestamp": quote.get("timestamp") or quote.get("collected_at"),
    }


def build_oil_vix_report(quotes: dict[str, Any], collected_at: str | None = None) -> dict[str, Any]:
    normalized = {str(symbol).upper(): _normalize_quote(str(symbol), raw) for symbol, raw in (quotes or {}).items()}
    collected_at = collected_at or next((str(q.get("timestamp") or q.get("collected_at")) for q in normalized.values() if q.get("timestamp") or q.get("collected_at")), None) or datetime.now(timezone.utc).isoformat()

    vix = _simple_quote_row(normalized, "^VIX")
    vix9d = _simple_quote_row(normalized, "^VIX9D")
    vix3m = _simple_quote_row(normalized, "^VIX3M")
    vix_level = vix.get("price")
    vix3m_level = vix3m.get("price")
    vix9d_level = vix9d.get("price")
    vix_curve = round(vix_level - vix3m_level, 2) if vix_level is not None and vix3m_level is not None else None
    vix_9d_spread = round(vix9d_level - vix_level, 2) if vix9d_level is not None and vix_level is not None else None
    if vix_curve is not None and vix_curve >= 1:
        structure = "backwardation"
        structure_kr = "백워데이션"
        vix_read = "공포/헤지 수요 우위"
    elif vix_curve is not None and vix_curve <= -4:
        structure = "contango"
        structure_kr = "콘탱고"
        vix_read = "정상/안정 구조"
    else:
        structure = "flat_or_unknown"
        structure_kr = "평탄/불명확"
        vix_read = "방향 확인 필요"
    if vix_level is not None and vix_level >= 25:
        vix_read = "고위험권, 헤지 수요 강함"
    elif vix_level is not None and vix_level <= 16 and structure == "contango":
        vix_read = "안정권, 변동성 매도 우위"

    wti = _simple_quote_row(normalized, "CL=F")
    brent = _simple_quote_row(normalized, "BZ=F")
    xle = _simple_quote_row(normalized, "XLE")
    oih = _simple_quote_row(normalized, "OIH")
    xop = _simple_quote_row(normalized, "XOP")
    crude_pcts = [pct for pct in (wti.get("pct_change"), brent.get("pct_change")) if pct is not None]
    energy_pcts = [pct for pct in (xle.get("pct_change"), oih.get("pct_change"), xop.get("pct_change")) if pct is not None]
    avg_crude_pct = round(sum(crude_pcts) / len(crude_pcts), 2) if crude_pcts else None
    avg_energy_pct = round(sum(energy_pcts) / len(energy_pcts), 2) if energy_pcts else None
    brent_wti_spread = round(brent["price"] - wti["price"], 2) if brent.get("price") is not None and wti.get("price") is not None else None
    if avg_crude_pct is not None and avg_crude_pct >= 3:
        oil_state = "oil_shock"
        oil_read = "유가 급등/인플레 압력"
    elif avg_crude_pct is not None and avg_crude_pct <= -3:
        oil_state = "demand_scare"
        oil_read = "유가 급락/수요 둔화 우려"
    elif avg_crude_pct is not None and avg_crude_pct > 1 and avg_energy_pct is not None and avg_energy_pct > 1:
        oil_state = "energy_reflation"
        oil_read = "에너지주 동반 강세/리플레이션"
    elif avg_crude_pct is not None and avg_crude_pct > 1 and avg_energy_pct is not None and avg_energy_pct < 0:
        oil_state = "oil_equity_divergence"
        oil_read = "유가는 오르는데 에너지주 약세, 수요불안/마진 부담"
    else:
        oil_state = "neutral"
        oil_read = "유가 충격 제한"

    focus_lines = [
        f"VIX: {_fmt_price(vix.get('price'))} / {_fmt_pct(vix.get('pct_change'))} / 9D {_fmt_price(vix9d.get('price'))} / 3M {_fmt_price(vix3m.get('price'))}",
        f"VIX 구조: {structure_kr} / VIX-3M {vix_curve:+.2f}p" if vix_curve is not None else "VIX 구조: 3M 데이터 부족",
        f"유가: WTI {_fmt_price(wti.get('price'))} {_fmt_pct(wti.get('pct_change'))} / Brent {_fmt_price(brent.get('price'))} {_fmt_pct(brent.get('pct_change'))} / Brent-WTI {brent_wti_spread:+.2f}" if brent_wti_spread is not None else f"유가: WTI {_fmt_price(wti.get('price'))} {_fmt_pct(wti.get('pct_change'))} / Brent {_fmt_price(brent.get('price'))} {_fmt_pct(brent.get('pct_change'))}",
        f"에너지 주식: XLE {_fmt_pct(xle.get('pct_change'))} / OIH {_fmt_pct(oih.get('pct_change'))} / XOP {_fmt_pct(xop.get('pct_change'))}",
        f"해석: {vix_read} / {oil_read} / 기준시각 {collected_at}",
    ]
    intraday_spikes: list[str] = []
    if _to_float(vix.get("pct_change_5m")) is not None and float(vix["pct_change_5m"]) >= 5:
        intraday_spikes.append(f"VIX 5m {_fmt_pct(vix.get('pct_change_5m'))}")
    elif _to_float(vix.get("pct_change_15m")) is not None and float(vix["pct_change_15m"]) >= 8:
        intraday_spikes.append(f"VIX 15m {_fmt_pct(vix.get('pct_change_15m'))}")
    if _to_float(wti.get("pct_change_5m")) is not None and float(wti["pct_change_5m"]) >= 1:
        intraday_spikes.append(f"WTI 5m {_fmt_pct(wti.get('pct_change_5m'))}")
    elif _to_float(wti.get("pct_change_15m")) is not None and float(wti["pct_change_15m"]) >= 2:
        intraday_spikes.append(f"WTI 15m {_fmt_pct(wti.get('pct_change_15m'))}")
    if _to_float(brent.get("pct_change_5m")) is not None and float(brent["pct_change_5m"]) >= 1:
        intraday_spikes.append(f"Brent 5m {_fmt_pct(brent.get('pct_change_5m'))}")
    elif _to_float(brent.get("pct_change_15m")) is not None and float(brent["pct_change_15m"]) >= 2:
        intraday_spikes.append(f"Brent 15m {_fmt_pct(brent.get('pct_change_15m'))}")
    if intraday_spikes:
        focus_lines.insert(0, f"분봉 급등: {' / '.join(intraday_spikes)}")
    alerts: list[str] = []
    if vix_level is not None and vix_level >= 25:
        alerts.append("vix_high")
    if _to_float(vix.get("pct_change_5m")) is not None and float(vix["pct_change_5m"]) >= 5:
        alerts.append("vix_5m_spike")
    elif _to_float(vix.get("pct_change_15m")) is not None and float(vix["pct_change_15m"]) >= 8:
        alerts.append("vix_15m_spike")
    if structure == "backwardation":
        alerts.append("vix_backwardation")
    if vix_9d_spread is not None and vix_9d_spread >= 1:
        alerts.append("vix9d_event_stress")
    if oil_state == "oil_shock":
        alerts.append("oil_shock")
    if _to_float(wti.get("pct_change_5m")) is not None and float(wti["pct_change_5m"]) >= 1:
        alerts.append("wti_5m_spike")
    elif _to_float(wti.get("pct_change_15m")) is not None and float(wti["pct_change_15m"]) >= 2:
        alerts.append("wti_15m_spike")
    if _to_float(brent.get("pct_change_5m")) is not None and float(brent["pct_change_5m"]) >= 1:
        alerts.append("brent_5m_spike")
    elif _to_float(brent.get("pct_change_15m")) is not None and float(brent["pct_change_15m"]) >= 2:
        alerts.append("brent_15m_spike")
    if oil_state == "demand_scare":
        alerts.append("oil_demand_scare")
    if oil_state == "oil_equity_divergence":
        alerts.append("oil_equity_divergence")
    if alerts:
        focus_lines.insert(0, f"트리거: {', '.join(alerts)}")
    next_actions = [
        "VIX 백워데이션이면 고베타 추격보다 헤지/현금비중 먼저 확인" if structure == "backwardation" else "VIX 콘탱고 유지면 주도 테마 눌림 위주로 후보 압축",
        "유가 급등이 XLE/OIH/XOP 동반 강세인지 확인, 동반 약하면 원유 추격 금지",
    ]
    return {
        "available": bool(vix.get("price") is not None or crude_pcts or energy_pcts),
        "summary": f"Oil/VIX: {structure_kr} / {oil_read}",
        "collected_at": collected_at,
        "vix": {
            "spot": vix,
            "vix9d": vix9d,
            "vix3m": vix3m,
            "structure": structure,
            "structure_kr": structure_kr,
            "vix_minus_3m": vix_curve,
            "vix9d_minus_vix": vix_9d_spread,
            "read": vix_read,
        },
        "oil": {
            "wti": wti,
            "brent": brent,
            "xle": xle,
            "oih": oih,
            "xop": xop,
            "avg_crude_pct": avg_crude_pct,
            "avg_energy_pct": avg_energy_pct,
            "brent_wti_spread": brent_wti_spread,
            "state": oil_state,
            "read": oil_read,
        },
        "focus_lines": focus_lines,
        "next_actions": next_actions,
        "alerts": alerts,
    }


def build_market_regime_report(quotes: dict[str, Any], collected_at: str | None = None) -> dict[str, Any]:
    report = build_sector_strength_report(quotes, collected_at=collected_at, top_n=3)
    oil_vix = build_oil_vix_report(quotes, collected_at=collected_at or report.get("collected_at"))
    regime = report.get("regime") or {"label": "unavailable", "korean_label": "데이터 부족", "signals": []}
    label = str(regime.get("korean_label") or regime.get("label") or "데이터 부족")
    signals = [str(signal) for signal in regime.get("signals", [])]
    benchmark_line = "장 분위기: 데이터 부족"
    if report.get("available"):
        benchmark_line = _benchmark_context_line(report.get("quotes") or {}, str(report.get("collected_at") or collected_at or ""))
    if regime.get("label") == "risk_off":
        action = "리스크오프: 고베타/성장주 추격매수 낮추고 손절선 짧게"
    elif regime.get("label") == "risk_on":
        action = "리스크온: 주도 테마 눌림 우선, 약한 종목 추격 제외"
    else:
        action = "중립장: 테마별 강약 확인 후 주도주만 선별"
    vol_stress_score = 0
    if oil_vix.get("vix", {}).get("spot", {}).get("price") is not None and float(oil_vix["vix"]["spot"]["price"]) >= 25:
        vol_stress_score += 2
    if oil_vix.get("vix", {}).get("structure") == "backwardation":
        vol_stress_score += 2
    if oil_vix.get("vix", {}).get("vix9d_minus_vix") is not None and float(oil_vix["vix"]["vix9d_minus_vix"]) >= 1:
        vol_stress_score += 1
    oil_pressure_score = 0
    if oil_vix.get("oil", {}).get("state") == "oil_shock":
        oil_pressure_score += 2
    elif oil_vix.get("oil", {}).get("state") in {"demand_scare", "oil_equity_divergence"}:
        oil_pressure_score += 1
    risk_off_score = int(regime.get("risk_off_score") or 0)
    risk_on_score = int(regime.get("risk_on_score") or 0)
    total_stress = risk_off_score + vol_stress_score + oil_pressure_score
    if total_stress >= 6 or (vol_stress_score >= 4 and oil_pressure_score >= 2):
        difficulty = {"label": "어려움", "reason": "변동성/유가 충격 동시 발생"}
    elif total_stress >= 3:
        difficulty = {"label": "보통", "reason": "리스크 신호 일부 존재"}
    elif regime.get("label") == "risk_on" and vol_stress_score == 0:
        difficulty = {"label": "쉬움", "reason": "리스크온에 변동성 압력 낮음"}
    else:
        difficulty = {"label": "보통", "reason": "방향성 확인 필요"}
    scores = {
        "risk_off_score": risk_off_score,
        "risk_on_score": risk_on_score,
        "vol_stress_score": vol_stress_score,
        "oil_pressure_score": oil_pressure_score,
        "total_stress_score": total_stress,
    }
    return {
        "available": bool(report.get("available")),
        "summary": f"장 분위기: {label}",
        "collected_at": report.get("collected_at"),
        "regime": regime,
        "focus_lines": [
            f"오늘 매매 난이도: {difficulty['label']} / {difficulty['reason']} / stress {total_stress}",
            f"장 분위기: {label} / {'; '.join(signals[:4]) if signals else '신호 부족'}",
            benchmark_line,
            *oil_vix["focus_lines"][:3],
            f"해석: {action}",
        ],
        "next_actions": [
            action,
            "장 분위기가 명확하지 않으면 SPY와 주도 테마 상승비율을 5분 뒤 재확인",
        ],
        "source_report": report,
        "oil_vix": oil_vix,
        "scores": scores,
        "trading_difficulty": difficulty,
    }


def _apply_previous_day_fields_from_daily_rows(quote: dict[str, Any], daily_rows: Any) -> None:
    if not isinstance(daily_rows, list):
        return
    rows: list[dict[str, Any]] = []
    for raw in daily_rows:
        if not isinstance(raw, dict):
            continue
        close = _to_float(raw.get("close"))
        date_text = str(raw.get("session_date") or "").strip()
        if close is None or not date_text:
            continue
        rows.append(
            {
                "date": date_text,
                "close": close,
                "volume": _to_float(raw.get("volume")),
            }
        )
    rows.sort(key=lambda row: row["date"])
    if len(rows) < 2:
        return

    current_date = _et_session_date_key(quote.get("timestamp") or quote.get("regular_market_time"))
    previous_idx = len(rows) - 1
    if current_date and rows[-1]["date"] >= current_date and len(rows) >= 2:
        previous_idx = len(rows) - 2
    if previous_idx <= 0:
        return

    previous_row = rows[previous_idx]
    base_row = rows[previous_idx - 1]
    base_close = _to_float(base_row.get("close"))
    previous_close = _to_float(previous_row.get("close"))
    if base_close in (None, 0) or previous_close is None:
        return

    pct = ((previous_close - float(base_close)) / float(base_close)) * 100
    quote["previous_day_date"] = previous_row["date"]
    quote["previous_day_close"] = round(previous_close, 2)
    quote["previous_day_previous_close"] = round(float(base_close), 2)
    quote["previous_day_pct_change"] = round(pct, 2)
    volume = _to_float(previous_row.get("volume"))
    if volume is not None:
        quote["previous_day_volume"] = int(volume)
        quote["previous_day_trading_value"] = round(previous_close * volume, 2)


def _apply_daily_technical_fields(symbol: str, quote: dict[str, Any], fetch_chart_pack: Any) -> None:
    _clear_technical_fields(quote)
    try:
        daily_pack = fetch_chart_pack(symbol, range_="6mo", interval="1d")
    except Exception as exc:
        quote["technical_warning"] = str(exc)
        return

    if not (isinstance(daily_pack, dict) and daily_pack.get("available") and isinstance(daily_pack.get("quote"), dict)):
        if isinstance(daily_pack, dict) and daily_pack.get("warning"):
            quote["technical_warning"] = daily_pack.get("warning")
        return

    daily_quote = daily_pack["quote"]
    _apply_previous_day_fields_from_daily_rows(quote, daily_quote.get("daily_ohlcv"))
    daily_technicals = _technical_fields(daily_quote)
    if not daily_technicals:
        return
    quote.update(daily_technicals)
    quote["technical_source"] = daily_pack.get("source") or daily_quote.get("source")
    quote["technical_timestamp"] = daily_quote.get("timestamp") or daily_pack.get("collected_at")
    quote["technical_range"] = "6mo"
    quote["technical_interval"] = "1d"


def fetch_sector_strength_quotes(symbols: tuple[str, ...] | list[str] | None = None) -> dict[str, dict[str, Any]]:
    try:
        from ..market_data.yfinance import fetch_toss_wts_quote_packs, fetch_yahoo_chart_quote_pack, fetch_yfinance_quote_pack
    except ImportError:  # direct script execution via src/main.py
        from us.market_data.yfinance import fetch_toss_wts_quote_packs, fetch_yahoo_chart_quote_pack, fetch_yfinance_quote_pack

    selected = tuple(symbols or DEFAULT_SECTOR_STRENGTH_SYMBOLS)
    toss_packs = fetch_toss_wts_quote_packs(selected) if os.getenv("SECTOR_STRENGTH_ENABLE_TOSS_WTS", "1") != "0" else {}

    def fetch_one(symbol: str) -> tuple[str, dict[str, Any]]:
        pack = fetch_yahoo_chart_quote_pack(symbol)
        if not (isinstance(pack, dict) and pack.get("available")):
            fallback_pack = fetch_yfinance_quote_pack(symbol)
            if isinstance(fallback_pack, dict):
                if isinstance(pack, dict) and pack.get("warning"):
                    fallback_pack = dict(fallback_pack)
                    fallback_pack["chart_warning"] = pack.get("warning")
                pack = fallback_pack
        quote = dict(pack.get("quote") or {}) if isinstance(pack, dict) else {}
        quote["symbol"] = symbol
        quote["source"] = pack.get("source") if isinstance(pack, dict) else "unknown"
        quote["timestamp"] = pack.get("collected_at") if isinstance(pack, dict) else None
        quote["available"] = bool(pack.get("available")) if isinstance(pack, dict) else False
        if pack.get("warning") if isinstance(pack, dict) else False:
            quote["warning"] = pack.get("warning")
        if pack.get("warnings") if isinstance(pack, dict) else False:
            quote["warnings"] = pack.get("warnings")

        _apply_daily_technical_fields(symbol, quote, fetch_yahoo_chart_quote_pack)

        toss_pack = toss_packs.get(symbol) if isinstance(toss_packs, dict) else None
        if isinstance(toss_pack, dict) and toss_pack.get("available") and isinstance(toss_pack.get("quote"), dict):
            yahoo_technical_fields = _technical_fields(quote)
            yahoo_timestamp = quote.get("timestamp")
            yahoo_source = quote.get("source")
            quote.update(toss_pack["quote"])
            quote.update(yahoo_technical_fields)
            quote["symbol"] = symbol
            quote["source"] = "toss_wts_stock_prices"
            quote["timestamp"] = toss_pack.get("collected_at")
            quote["technical_source"] = yahoo_source
            quote["technical_timestamp"] = yahoo_timestamp
            quote["available"] = True
        else:
            session_label = _quote_session_label(quote)
            if _session_needs_live_price(session_label) and quote.get("is_stale_regular_close"):
                quote["session_label"] = session_label
                quote["stale_note"] = quote.get("stale_note") or "정규장 종가 기준(확장/주간거래 실시간가 미확인)"
                quote["pct_change_basis"] = "정규장 종가 기준"
        return symbol, quote

    max_workers = max(1, int(os.getenv("SECTOR_STRENGTH_QUOTE_WORKERS", "16")))
    max_workers = min(max_workers, max(1, len(selected)))
    quotes: dict[str, dict[str, Any]] = {}
    if max_workers == 1:
        for symbol in selected:
            key, quote = fetch_one(symbol)
            quotes[key] = quote
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(fetch_one, symbol) for symbol in selected]
            for future in as_completed(futures):
                key, quote = future.result()
                quotes[key] = quote
    return {symbol: quotes[symbol] for symbol in selected if symbol in quotes}
