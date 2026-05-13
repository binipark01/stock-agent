from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

try:
    from ...watchlists import SYMBOL_ALIASES, normalize_symbol
except ImportError:  # direct script execution
    from watchlists import SYMBOL_ALIASES, normalize_symbol


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def normalize_krx_code(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    normalized_symbol = normalize_symbol(text)
    if normalized_symbol:
        text = normalized_symbol
    upper = text.strip().upper()
    if upper.startswith("A") and len(upper) == 7 and upper[1:].isdigit():
        return upper[1:]
    if upper.endswith((".KS", ".KQ")) and len(upper) >= 9:
        return upper.split(".", 1)[0]
    if upper.isdigit() and len(upper) <= 6:
        return upper.zfill(6)
    compact = text.lower().replace(" ", "")
    for symbol, aliases in SYMBOL_ALIASES.items():
        candidates = {alias.lower().replace(" ", "") for alias in aliases}
        if compact in candidates and symbol.endswith((".KS", ".KQ")):
            return symbol.split(".", 1)[0]
    return upper


def _to_int(value: Any, *, absolute: bool = False) -> int | None:
    if value in (None, ""):
        return None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    sign = -1 if text.startswith("-") else 1
    text = text.lstrip("+-")
    try:
        number = int(float(text))
    except ValueError:
        return None
    number *= sign
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


def _fmt_int(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value)


def _fmt_float(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.2f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return str(value)


def _first_value(row: dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _extract_rows(data: dict[str, Any], row_keys: Iterable[str]) -> list[dict[str, Any]]:
    for key in row_keys:
        rows = data.get(key)
        if isinstance(rows, dict):
            return [rows]
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    nested_rows: list[dict[str, Any]] = []
    for value in data.values():
        if isinstance(value, list) and value and all(isinstance(row, dict) for row in value):
            nested_rows.extend(value)
    return nested_rows
