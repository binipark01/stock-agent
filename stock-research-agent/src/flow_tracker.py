"""Stateful US sector/theme flow-proxy tracker."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .flow_store import load_recent_theme_snapshots, save_flow_events, save_theme_snapshots, should_emit_event
except ImportError:  # pragma: no cover
    from flow_store import load_recent_theme_snapshots, save_flow_events, save_theme_snapshots, should_emit_event


def _to_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        out = float(value)
    except Exception:
        return None
    if out != out or out in (float("inf"), float("-inf")):
        return None
    return out


def _fmt_pct(value: Any) -> str:
    number = _to_float(value)
    return "n/a" if number is None else f"{number:+.2f}%"


def _fmt_money(value: Any) -> str:
    number = _to_float(value)
    if number is None:
        return "n/a"
    abs_number = abs(number)
    prefix = chr(36)
    if abs_number >= 1_000_000_000:
        return f"{prefix}{number / 1_000_000_000:.1f}B"
    if abs_number >= 1_000_000:
        return f"{prefix}{number / 1_000_000:.1f}M"
    return f"{prefix}{number:,.0f}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _score_from_theme(theme: dict[str, Any]) -> int:
    trading_value = _to_float(theme.get("trading_value"))
    relative = _to_float(theme.get("relative_to_spy_pct"))
    breadth = _to_float(theme.get("breadth_positive_pct"))
    avg_pct = _to_float(theme.get("average_pct_change"))
    constituents = [row for row in theme.get("constituents", []) if row.get("score_eligible", True)]
    vwap_above_count = sum(1 for row in constituents if (_to_float(row.get("vwap_position_pct")) is not None and (_to_float(row.get("vwap_position_pct")) or 0) >= 0))
    pct5_values = [_to_float(row.get("pct_change_5m")) for row in constituents]
    pct5_values = [value for value in pct5_values if value is not None]
    best_pct5 = max(pct5_values) if pct5_values else None
    score = 0
    if trading_value is not None:
        if trading_value >= 1_000_000_000:
            score += 25
        elif trading_value >= 500_000_000:
            score += 20
        elif trading_value >= 100_000_000:
            score += 12
    if relative is not None:
        if relative >= 3.0:
            score += 20
        elif relative >= 1.5:
            score += 15
        elif relative >= 0.7:
            score += 8
    if breadth is not None:
        if breadth >= 75:
            score += 20
        elif breadth >= 60:
            score += 14
        elif breadth >= 45:
            score += 7
    if constituents:
        vwap_ratio = vwap_above_count / max(len(constituents), 1)
        if vwap_ratio >= 0.75:
            score += 15
        elif vwap_ratio >= 0.5:
            score += 10
        elif vwap_ratio > 0:
            score += 5
    if best_pct5 is not None:
        if best_pct5 >= 1.0:
            score += 15
        elif best_pct5 >= 0.5:
            score += 10
        elif best_pct5 > 0:
            score += 4
    if avg_pct is not None and avg_pct >= 1.0:
        score += 5
    return max(0, min(100, int(round(score))))


def build_theme_flow_snapshots(report: dict[str, Any], *, timestamp: str | None = None) -> list[dict[str, Any]]:
    timestamp = timestamp or str(report.get("collected_at") or _utc_now())
    active_keys = {str(item.get("theme_key")) for item in ((report.get("flow_proxies") or {}).get("candidates") or []) if item.get("theme_key")}
    snapshots: list[dict[str, Any]] = []
    for theme in report.get("theme_baskets", []) or []:
        key = str(theme.get("key") or "")
        constituents = [row for row in theme.get("constituents", []) if row.get("score_eligible", True)]
        vwap_above = [row for row in constituents if (_to_float(row.get("vwap_position_pct")) is not None and (_to_float(row.get("vwap_position_pct")) or 0) >= 0)]
        intraday = sorted([row for row in constituents if _to_float(row.get("pct_change_5m")) is not None], key=lambda row: _to_float(row.get("pct_change_5m")) or -999, reverse=True)
        snapshots.append({
            "timestamp": timestamp,
            "theme_key": key,
            "theme_name": theme.get("name") or key,
            "flow_score": _score_from_theme(theme),
            "average_pct_change": _to_float(theme.get("average_pct_change")),
            "breadth_positive_pct": _to_float(theme.get("breadth_positive_pct")),
            "relative_to_spy_pct": _to_float(theme.get("relative_to_spy_pct")),
            "trading_value": _to_float(theme.get("trading_value")),
            "vwap_above_count": len(vwap_above),
            "constituent_count": len(constituents),
            "top_5m_symbols": [str(row.get("symbol")) for row in intraday[:3] if row.get("symbol")],
            "top_5m": [{"symbol": str(row.get("symbol")), "pct_change_5m": _to_float(row.get("pct_change_5m"))} for row in intraday[:3] if row.get("symbol")],
            "leader_symbols": [str(row.get("symbol")) for row in (theme.get("leaders") or [])[:3] if row.get("symbol")],
            "flow_proxy_active": key in active_keys,
        })
    return snapshots


def _latest_by_theme(history: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in history:
        key = str(row.get("theme_key") or "")
        if key:
            out[key] = row
    return out


def _event_summary(current: dict[str, Any], previous: dict[str, Any] | None = None) -> str:
    score = int(current.get("flow_score") or 0)
    prev_score = int(previous.get("flow_score") or 0) if previous else None
    score_text = f"score {prev_score}→{score}" if prev_score is not None else f"score {score}"
    top5 = ", ".join(f"{row.get('symbol')} {_fmt_pct(row.get('pct_change_5m'))}" for row in current.get("top_5m", [])[:2] if row.get("symbol"))
    parts = [score_text, f"거래대금 {_fmt_money(current.get('trading_value'))}", f"SPY대비 {_fmt_pct(current.get('relative_to_spy_pct'))}", f"VWAP 위 {int(current.get('vwap_above_count') or 0)}종목"]
    if top5:
        parts.append(f"5m {top5}")
    return " / ".join(parts)


def detect_flow_events(current: list[dict[str, Any]], history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    previous_by_theme = _latest_by_theme(history)
    events: list[dict[str, Any]] = []
    for row in current:
        key = str(row.get("theme_key") or "")
        if not key:
            continue
        prev = previous_by_theme.get(key)
        score = int(row.get("flow_score") or 0)
        prev_score = int(prev.get("flow_score") or 0) if prev else 0
        breadth = _to_float(row.get("breadth_positive_pct"))
        prev_breadth = _to_float(prev.get("breadth_positive_pct")) if prev else None
        vwap_count = int(row.get("vwap_above_count") or 0)
        prev_vwap_count = int(prev.get("vwap_above_count") or 0) if prev else 0
        event_type = None
        title = None
        if prev and score >= 70 and prev_score < 45:
            event_type, title = "flow_started", "수급 신규"
        elif prev and score >= 75 and score - prev_score >= 15:
            event_type, title = "flow_accelerated", "수급 가속"
        elif prev and prev_score >= 70 and score < 50:
            event_type, title = "flow_faded", "수급 약화"
        elif prev and breadth is not None and prev_breadth is not None and breadth >= 70 and breadth - prev_breadth >= 20:
            event_type, title = "breadth_expanded", "수급 확산"
        elif score < 50 and (row.get("average_pct_change") or 0) >= 1.5 and (breadth or 0) < 40 and vwap_count <= 2:
            event_type, title = "fake_strength", "fake strength"
        if not event_type:
            continue
        events.append({
            "timestamp": row.get("timestamp") or _utc_now(),
            "event_type": event_type,
            "title": title,
            "theme_key": key,
            "theme_name": row.get("theme_name") or key,
            "score": score,
            "previous_score": prev_score if prev else None,
            "summary": _event_summary(row, prev),
            "vwap_above_delta": vwap_count - prev_vwap_count if prev else None,
        })
    priority = {"flow_started": 0, "flow_accelerated": 1, "breadth_expanded": 2, "flow_faded": 3, "fake_strength": 4}
    return sorted(events, key=lambda event: (priority.get(str(event.get("event_type")), 99), -(event.get("score") or 0)))


def build_flow_event_alert(events: list[dict[str, Any]], *, max_events: int = 2) -> str:
    if not events:
        return ""
    lines: list[str] = []
    for event in events[:max_events]:
        title = str(event.get("title") or event.get("event_type") or "수급 이벤트")
        theme = str(event.get("theme_name") or event.get("theme_key") or "테마")
        summary = str(event.get("summary") or "")
        action = "추격보다 VWAP 눌림/재돌파 확인"
        if event.get("event_type") == "flow_faded":
            action = "추격 금지, VWAP 회복 전 관망"
        elif event.get("event_type") == "fake_strength":
            action = "좁은 상승, 대장주 단독인지 확인"
        lines.append(f"[{title}] {theme} / {summary} / {action}")
    return "\n".join(lines)[:700]


def run_flow_tracker_cycle(report: dict[str, Any], *, db_path: str | Path, now: str | None = None, cooldown_minutes: int = 20) -> dict[str, Any]:
    timestamp = now or str(report.get("collected_at") or _utc_now())
    history = load_recent_theme_snapshots(db_path, lookback_minutes=90, now=timestamp)
    current = build_theme_flow_snapshots(report, timestamp=timestamp)
    events = detect_flow_events(current, history)
    emit_events = [event for event in events if should_emit_event(db_path, event, cooldown_minutes=cooldown_minutes, now=timestamp)]
    save_theme_snapshots(db_path, current)
    if emit_events:
        save_flow_events(db_path, emit_events)
    return {"status": "ok", "snapshots": current, "events": emit_events, "alert_text": build_flow_event_alert(emit_events), "db_path": str(db_path)}
