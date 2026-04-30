from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .repository import fetch_latest_earnings, fetch_latest_news, fetch_latest_snapshot, get_connection
except ImportError:  # direct script execution
    from repository import fetch_latest_earnings, fetch_latest_news, fetch_latest_snapshot, get_connection


TOPIC_FAMILIES = [
    "market:quote:{symbol}",
    "market:history:{symbol}:5d:15m",
    "news:symbol:{symbol}",
    "filing:sec:{symbol}",
    "earnings:calendar:{symbol}",
    "options:chain:{symbol}",
    "social:threads:{symbol}",
    "portfolio:position:{symbol}",
]


def list_stock_topics(symbols: list[str]) -> list[str]:
    topics: list[str] = []
    for symbol in symbols:
        sym = symbol.upper().strip()
        if not sym:
            continue
        topics.extend(template.format(symbol=sym) for template in TOPIC_FAMILIES)
    topics.extend(["agent:brief:<run_id>", "agent:alert:<run_id>"])
    return topics


def _row_to_dict(row: Any) -> dict[str, Any] | None:
    if not row:
        return None
    return {key: row[key] for key in row.keys()}


def _age_ms(collected_at: str | None) -> int:
    if not collected_at:
        return -1
    try:
        dt = datetime.fromisoformat(collected_at.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0, int((datetime.now(timezone.utc) - dt).total_seconds() * 1000))
    except Exception:
        return -1


def peek_topic(topic: str, db_path: str | Path) -> dict[str, Any]:
    parts = topic.split(":")
    result = {"topic": topic, "value": None, "age_ms": -1, "source": "stock_agent_db"}
    if len(parts) < 3:
        return result
    family, sub, symbol = parts[0], parts[1], parts[2].upper()
    conn = get_connection(db_path)
    try:
        if family == "market" and sub == "quote":
            row = fetch_latest_snapshot(conn, symbol)
            value = _row_to_dict(row)
            result["value"] = value
            result["age_ms"] = _age_ms(value.get("collected_at") if value else None)
        elif family == "news" and sub == "symbol":
            rows = fetch_latest_news(conn, symbol, limit=1)
            value = _row_to_dict(rows[0]) if rows else None
            result["value"] = value
            result["age_ms"] = _age_ms(value.get("collected_at") if value else None)
        elif family == "earnings" and sub == "calendar":
            row = fetch_latest_earnings(conn, symbol)
            value = _row_to_dict(row)
            result["value"] = value
            result["age_ms"] = _age_ms(value.get("collected_at") if value else None)
        else:
            result["source"] = "topic_defined_no_cached_value"
    finally:
        conn.close()
    return result


def build_topic_hub_focus_lines(symbols: list[str], db_path: str | Path, max_topics_per_symbol: int = 8) -> list[str]:
    focus: list[str] = []
    for symbol in symbols[:3]:
        symbol_topics = [topic for topic in list_stock_topics([symbol]) if ":<run_id>" not in topic]
        focus.append(f"DataHub-lite {symbol}: topics {', '.join(symbol_topics[:max_topics_per_symbol])}")
        for topic in [f"market:quote:{symbol}", f"news:symbol:{symbol}", f"earnings:calendar:{symbol}"]:
            peeked = peek_topic(topic, db_path)
            value = peeked.get("value") or {}
            if topic.startswith("market:quote") and value:
                focus.append(f"peek {topic}: price={value.get('price')} pct={value.get('pct_change')} age_ms={peeked['age_ms']}")
            elif topic.startswith("news:symbol") and value:
                focus.append(f"peek {topic}: headline={value.get('headline')} age_ms={peeked['age_ms']}")
            elif topic.startswith("earnings:calendar") and value:
                focus.append(f"peek {topic}: date={value.get('earnings_date')} session={value.get('session')} age_ms={peeked['age_ms']}")
            else:
                focus.append(f"peek {topic}: no cached value age_ms=-1")
    return focus
