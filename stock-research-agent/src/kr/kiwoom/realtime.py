from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

try:
    from ..flow.common import normalize_krx_code
except ImportError:  # direct script execution
    from kr.flow.common import normalize_krx_code


MOCK_WEBSOCKET_URL = "wss://mockapi.kiwoom.com:10000/api/dostk/websocket"
PROD_WEBSOCKET_URL = "wss://api.kiwoom.com:10000/api/dostk/websocket"


def get_websocket_url(env: str = "mock") -> str:
    normalized = str(env or "mock").strip().lower()
    if normalized in {"prod", "production", "real", "live"}:
        return PROD_WEBSOCKET_URL
    return MOCK_WEBSOCKET_URL


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _codes(symbols: Iterable[Any]) -> list[str]:
    return [code for code in dict.fromkeys(normalize_krx_code(symbol) for symbol in symbols or []) if code]


def build_register_message(
    symbols: Iterable[Any],
    types: Iterable[str] = ("0B", "0D", "0w"),
    group_no: str = "1",
    refresh: str = "1",
) -> dict[str, Any]:
    return {
        "trnm": "REG",
        "grp_no": str(group_no),
        "refresh": str(refresh),
        "data": [{"item": _codes(symbols), "type": [str(t) for t in types]}],
    }


def build_remove_message(
    symbols: Iterable[Any],
    types: Iterable[str] = ("0B", "0D", "0w"),
    group_no: str = "1",
) -> dict[str, Any]:
    return {
        "trnm": "REMOVE",
        "grp_no": str(group_no),
        "data": [{"item": _codes(symbols), "type": [str(t) for t in types]}],
    }


def _to_int(value: Any, *, absolute: bool = False) -> int | None:
    if value in (None, ""):
        return None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    sign = -1 if text.startswith("-") else 1
    text = text.lstrip("+-")
    try:
        number = int(float(text)) * sign
    except ValueError:
        return None
    return abs(number) if absolute else number


def _to_float(value: Any, *, absolute: bool = False) -> float | None:
    if value in (None, ""):
        return None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    sign = -1 if text.startswith("-") else 1
    text = text.lstrip("+-")
    try:
        number = float(text) * sign
    except ValueError:
        return None
    return abs(number) if absolute else number


def _event_base(item: dict[str, Any], source_type: str, collected_at: str) -> dict[str, Any]:
    return {
        "code": normalize_krx_code(item.get("item") or item.get("code") or item.get("stk_cd")),
        "source": "kiwoom_websocket",
        "source_type": source_type,
        "collected_at": collected_at,
    }


def _normalize_tick(item: dict[str, Any], values: dict[str, Any], collected_at: str) -> dict[str, Any]:
    event = _event_base(item, "0B", collected_at)
    event.update(
        {
            "event": "stock_tick",
            "time": values.get("20"),
            "current_price": _to_int(values.get("10"), absolute=True),
            "change_value": _to_int(values.get("11")),
            "change_pct": _to_float(values.get("12")),
            "accumulated_volume": _to_int(values.get("13"), absolute=True),
            "accumulated_trading_value": _to_int(values.get("14"), absolute=True),
            "execution_strength": _to_float(values.get("228"), absolute=True),
            "instant_trading_value": _to_int(values.get("1313"), absolute=True),
            "net_buy_execution_quantity": _to_int(values.get("1314")),
        }
    )
    return event


def _normalize_orderbook(item: dict[str, Any], values: dict[str, Any], collected_at: str) -> dict[str, Any]:
    event = _event_base(item, "0D", collected_at)
    event.update(
        {
            "event": "orderbook",
            "time": values.get("21"),
            "best_ask": _to_int(values.get("41"), absolute=True),
            "best_bid": _to_int(values.get("51"), absolute=True),
            "best_ask_volume": _to_int(values.get("61"), absolute=True),
            "best_bid_volume": _to_int(values.get("71"), absolute=True),
            "total_ask_volume": _to_int(values.get("121"), absolute=True),
            "total_bid_volume": _to_int(values.get("125"), absolute=True),
            "net_bid_volume": _to_int(values.get("128")),
            "bid_volume_ratio": _to_float(values.get("129"), absolute=True),
        }
    )
    return event


def _normalize_program(item: dict[str, Any], values: dict[str, Any], collected_at: str) -> dict[str, Any]:
    event = _event_base(item, "0w", collected_at)
    event.update(
        {
            "event": "program_trading",
            "time": values.get("20"),
            "current_price": _to_int(values.get("10"), absolute=True),
            "change_pct": _to_float(values.get("12")),
            "program_sell_quantity": _to_int(values.get("202"), absolute=True),
            "program_sell_amount": _to_int(values.get("204"), absolute=True),
            "program_buy_quantity": _to_int(values.get("206"), absolute=True),
            "program_buy_amount": _to_int(values.get("208"), absolute=True),
            "program_net_buy_quantity": _to_int(values.get("210")),
            "program_net_buy_amount": _to_int(values.get("212")),
        }
    )
    return event


def normalize_realtime_message(message: dict[str, Any], collected_at: str | None = None) -> list[dict[str, Any]]:
    collected_at = collected_at or _now_iso()
    raw_items = message.get("data") if isinstance(message, dict) else []
    if isinstance(raw_items, dict):
        raw_items = [raw_items]
    events: list[dict[str, Any]] = []
    for item in raw_items or []:
        if not isinstance(item, dict):
            continue
        source_type = str(item.get("type") or item.get("tr_cd") or item.get("source_type") or "")
        values = item.get("values") or item.get("value") or item.get("data") or {}
        if not isinstance(values, dict):
            continue
        if source_type == "0B":
            events.append(_normalize_tick(item, values, collected_at))
        elif source_type == "0D":
            events.append(_normalize_orderbook(item, values, collected_at))
        elif source_type == "0w":
            events.append(_normalize_program(item, values, collected_at))
        else:
            unknown = _event_base(item, source_type, collected_at)
            unknown.update({"event": "unknown", "values": values})
            events.append(unknown)
    return events
