"""Session-aware KRX flow-change watch helpers.

Pure formatter/scoring layer: no network calls and no order/trading APIs.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import re

SESSION_LABELS = {
    "regular": "정규장",
    "closing": "장후반",
    "after_hours": "시간외",
    "nxt": "NXT",
    "preopen": "장전",
    "unknown": "세션미상",
}

NXT_CAVEAT = "NXT 구간은 가격/거래량 변화 감시 중심, 투자자/프로그램 수급은 최신 제공 row 기준 또는 unavailable로 표시"


@dataclass(frozen=True)
class SessionFlowPoint:
    code: str
    name: str
    session: str
    collected_at: str | None = None
    env: str | None = None
    source: str | None = None
    price: float | None = None
    change_pct: float | None = None
    foreign_net_buy: float | None = None
    institution_net_buy: float | None = None
    program_net_buy: float | None = None
    trade_value: float | None = None
    volume: float | None = None
    execution_strength: float | None = None


def _as_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text in {"-", "--"}:
        return None
    sign = -1 if text.startswith("--") or text.startswith("-") else 1
    text = re.sub(r"[^0-9.]", "", text)
    if not text:
        return None
    try:
        return sign * float(text)
    except ValueError:
        return None


def _pick(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        cur: Any = row
        ok = True
        for part in key.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                ok = False
                break
        if ok and cur not in (None, ""):
            return cur
    return None


def normalize_session_label(value: Any) -> str:
    text = str(value or "unknown").strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "정규장": "regular", "regular_session": "regular", "regular": "regular",
        "장후반": "closing", "closing": "closing", "late": "closing", "late_flow": "closing",
        "시간외": "after_hours", "afterhour": "after_hours", "after_hours": "after_hours", "after_market": "after_hours",
        "nxt": "nxt", "nxt장": "nxt", "nxt_market": "nxt",
        "장전": "preopen", "preopen": "preopen", "pre_open": "preopen",
    }
    return aliases.get(text, text if text in SESSION_LABELS else "unknown")


def normalize_code(value: Any) -> str:
    text = str(value or "").strip().upper()
    if text.endswith((".KS", ".KQ")):
        text = text[:-3]
    if text.startswith("A") and len(text) == 7 and text[1:].isdigit():
        text = text[1:]
    digits = re.sub(r"\D", "", text)
    if len(digits) >= 6:
        return digits[-6:]
    return text


def _iter_rows(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("stocks", "items", "candidates", "rows"):
        rows = snapshot.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    if any(k in snapshot for k in ("code", "symbol", "price", "program_net_buy")):
        return [snapshot]
    return []


def normalize_session_snapshot(snapshot: dict[str, Any]) -> list[SessionFlowPoint]:
    session = normalize_session_label(snapshot.get("session") or snapshot.get("market_session"))
    collected_at = snapshot.get("collected_at") or snapshot.get("timestamp")
    env = snapshot.get("env") or snapshot.get("flow_env")
    source = snapshot.get("source") or snapshot.get("base_url")
    points: list[SessionFlowPoint] = []
    for row in _iter_rows(snapshot):
        code = normalize_code(_pick(row, "code", "symbol", "ticker", "stk_cd"))
        if not code:
            continue
        points.append(SessionFlowPoint(
            code=code,
            name=str(_pick(row, "name", "stock_name", "stk_nm") or code),
            session=normalize_session_label(row.get("session") or session),
            collected_at=str(row.get("collected_at") or collected_at or ""),
            env=str(row.get("env") or env or ""),
            source=str(row.get("source") or source or ""),
            price=_as_number(_pick(row, "price", "current_price", "close_price", "basic.current_price", "naver.closePrice")),
            change_pct=_as_number(_pick(row, "change_pct", "pct", "pct_change", "price_change_pct", "naver.compareToPreviousClosePrice.rate")),
            foreign_net_buy=_as_number(_pick(row, "foreign_net_buy", "foreign_net_buy_qty", "foreign_quantity", "for_daly_nettrde_qty", "naver.foreignerPureBuyQuant")),
            institution_net_buy=_as_number(_pick(row, "institution_net_buy", "institution_net_buy_qty", "institution_quantity", "orgn_daly_nettrde_qty", "naver.organPureBuyQuant")),
            program_net_buy=_as_number(_pick(row, "program_net_buy", "program_net_buy_qty", "program_intraday.latest.program_net_buy_amount", "program_intraday.latest.program_net_buy_quantity", "prm_netprps_qty")),
            trade_value=_as_number(_pick(row, "trade_value", "trading_value", "execution_strength.latest.accumulated_trading_value")),
            volume=_as_number(_pick(row, "volume", "trading_volume", "trde_qty", "accumulatedTradingVolume")),
            execution_strength=_as_number(_pick(row, "execution_strength", "execution_strength.latest.execution_strength")),
        ))
    return points


def _delta(cur: float | None, prev: float | None) -> float | None:
    if cur is None or prev is None:
        return None
    return cur - prev


def _total_flow(point: SessionFlowPoint) -> float | None:
    vals = [v for v in [point.foreign_net_buy, point.institution_net_buy, point.program_net_buy] if v is not None]
    if not vals:
        return None
    return sum(vals)


def _alert_if_accelerating(alerts: list[str], prefix: str, cur: float | None, prev: float | None) -> None:
    d = _delta(cur, prev)
    if d is None or d == 0:
        return
    if d > 0:
        alerts.append(f"{prefix}_buy_acceleration")
    else:
        alerts.append(f"{prefix}_sell_acceleration")


def _judge(alerts: list[str]) -> str:
    if "price_up_flow_divergence" in alerts or "session_reversal" in alerts:
        return "수급이탈주의"
    if "session_continuation" in alerts and any(a.endswith("buy_acceleration") for a in alerts):
        return "수급연속"
    if any(a.endswith("buy_acceleration") for a in alerts):
        return "수급개선"
    if any(a.endswith("sell_acceleration") for a in alerts):
        return "수급약화"
    return "관찰"


def build_krx_session_flow_watch_report(snapshots: list[dict[str, Any]] | dict[str, Any]) -> dict[str, Any]:
    if isinstance(snapshots, dict):
        snapshots = snapshots.get("snapshots") or snapshots.get("session_snapshots") or []
    normalized: list[list[SessionFlowPoint]] = [normalize_session_snapshot(s) for s in snapshots if isinstance(s, dict)]
    flat = [p for group in normalized for p in group]
    session_path = []
    for group in normalized:
        if group:
            session_path.append(group[0].session)
    by_code: dict[str, list[SessionFlowPoint]] = {}
    for point in flat:
        by_code.setdefault(point.code, []).append(point)

    items: list[dict[str, Any]] = []
    for code, points in by_code.items():
        if len(points) < 2:
            continue
        prev, cur = points[-2], points[-1]
        alerts: list[str] = []
        _alert_if_accelerating(alerts, "foreign", cur.foreign_net_buy, prev.foreign_net_buy)
        _alert_if_accelerating(alerts, "institution", cur.institution_net_buy, prev.institution_net_buy)
        _alert_if_accelerating(alerts, "program", cur.program_net_buy, prev.program_net_buy)
        price_delta = _delta(cur.price, prev.price)
        volume_delta = _delta(cur.volume, prev.volume)
        total_prev = _total_flow(prev)
        total_cur = _total_flow(cur)
        total_delta = _delta(total_cur, total_prev)
        if price_delta is not None and price_delta > 0 and volume_delta is not None and volume_delta > 0:
            alerts.append("price_volume_confirmation")
        if price_delta is not None and price_delta > 0 and total_delta is not None and total_delta > 0:
            alerts.append("session_continuation")
        if price_delta is not None and price_delta > 0 and total_delta is not None and total_delta < 0:
            alerts.append("price_up_flow_divergence")
            alerts.append("session_reversal")
        if cur.session != prev.session and cur.session in {"nxt", "after_hours"} and total_cur is not None and total_prev is not None:
            if total_cur > 0 and total_delta is not None and total_delta >= 0 and "session_continuation" not in alerts:
                alerts.append("session_continuation")
            if total_cur < 0 and total_delta is not None and total_delta < 0 and "session_reversal" not in alerts:
                alerts.append("session_reversal")
        items.append({
            "code": code,
            "name": cur.name or prev.name,
            "previous_session": prev.session,
            "current_session": cur.session,
            "previous_collected_at": prev.collected_at,
            "current_collected_at": cur.collected_at,
            "env": cur.env or prev.env,
            "source": cur.source or prev.source,
            "price": cur.price,
            "price_delta": price_delta,
            "change_pct": cur.change_pct,
            "foreign_net_buy": cur.foreign_net_buy,
            "institution_net_buy": cur.institution_net_buy,
            "program_net_buy": cur.program_net_buy,
            "total_flow_delta": total_delta,
            "volume": cur.volume,
            "volume_delta": volume_delta,
            "alerts": list(dict.fromkeys(alerts)),
            "judgment": _judge(alerts),
        })
    items.sort(key=lambda item: (item["judgment"] != "수급연속", -len(item["alerts"]), item["code"]))
    has_nxt = any(p.session == "nxt" for p in flat) or any("nxt" in (p.source or "").lower() for p in flat)
    return {
        "mode": "krx_session_flow_watch",
        "session_path": session_path,
        "items": items,
        "nxt_caveat": NXT_CAVEAT if has_nxt else "",
        "source": ",".join(sorted({p.source for p in flat if p.source})) or "runtime_context",
        "env": ",".join(sorted({p.env for p in flat if p.env})) or "unknown",
        "collected_at": items[-1]["current_collected_at"] if items else "",
    }


def _fmt_num(value: float | None, suffix: str = "") -> str:
    if value is None:
        return "n/a"
    if float(value).is_integer():
        return f"{int(value):+,}{suffix}"
    return f"{value:+.2f}{suffix}"


def format_krx_session_flow_watch_report(report: dict[str, Any]) -> list[str]:
    session_path = "→".join(SESSION_LABELS.get(s, s) for s in report.get("session_path", [])) or "세션미상"
    lines = [
        f"[세션 수급 변화] {session_path} / env={report.get('env','unknown')} / source={report.get('source','runtime_context')}",
    ]
    for item in report.get("items", []):
        cur_session = SESSION_LABELS.get(item.get("current_session"), item.get("current_session", "unknown"))
        prev_session = SESSION_LABELS.get(item.get("previous_session"), item.get("previous_session", "unknown"))
        alerts = ",".join(item.get("alerts") or ["no_alert"])
        lines.append(
            f"{item.get('name')}({item.get('code')}) {prev_session}->{cur_session} 판정={item.get('judgment')} "
            f"가격변화={_fmt_num(item.get('price_delta'),'원')} 외인={_fmt_num(item.get('foreign_net_buy'),'주')} "
            f"기관={_fmt_num(item.get('institution_net_buy'),'주')} 프로그램={_fmt_num(item.get('program_net_buy'),'주')} alerts={alerts}"
        )
    if report.get("nxt_caveat"):
        lines.append(f"[NXT 주의] {report['nxt_caveat']}")
    if not report.get("items"):
        lines.append("비교 가능한 이전/현재 세션 스냅샷이 부족함")
    return lines


def build_krx_session_flow_watch_response(report: dict[str, Any]) -> dict[str, Any]:
    focus = format_krx_session_flow_watch_report(report)
    item_count = len(report.get("items", []))
    return {
        "agent": "stock-research-agent",
        "mode": "krx_session_flow_watch",
        "summary": f"KRX NXT/세션 수급 변화 감시: {item_count}개 종목 비교",
        "symbols": [item.get("code") for item in report.get("items", [])],
        "focus": focus,
        "next_actions": [
            "정규장→시간외/NXT 가격·거래량 변화와 최신 수급 row의 방향 전환만 감시",
            "NXT 투자자별/프로그램 수급은 API 제공 여부가 제한적이면 unavailable 또는 최신 row carry-forward로 표시",
            "주문/자동매매 없이 read-only 감시·알림 후보로만 사용",
        ],
        "features": ["krx_session_flow_watch", "nxt_session_caveat", "read_only_monitoring"],
        "krx_session_flow_watch_report": report,
    }
