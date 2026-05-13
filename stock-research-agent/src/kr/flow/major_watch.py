from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

try:
    from .symbol_flow import build_krx_symbol_flow_snapshot_v2, today_kst
except ImportError:
    from kr.flow.symbol_flow import build_krx_symbol_flow_snapshot_v2, today_kst

KST = timezone(timedelta(hours=9))
MATERIAL_QTY = 100_000
PROGRAM_MATERIAL_QTY = 100_000

DEFAULT_MAJOR_SYMBOLS: list[dict[str, str]] = [
    {"code": "005930", "name": "삼성전자", "theme": "반도체/지수"},
    {"code": "000660", "name": "SK하이닉스", "theme": "반도체/HBM"},
    {"code": "005380", "name": "현대차", "theme": "자동차"},
    {"code": "000270", "name": "기아", "theme": "자동차"},
    {"code": "005490", "name": "POSCO홀딩스", "theme": "철강/2차전지"},
    {"code": "012450", "name": "한화에어로스페이스", "theme": "방산"},
    {"code": "267260", "name": "HD현대일렉트릭", "theme": "전력기기"},
    {"code": "001440", "name": "대한전선", "theme": "전선/전력인프라"},
    {"code": "277810", "name": "레인보우로보틱스", "theme": "로봇"},
    {"code": "454910", "name": "두산로보틱스", "theme": "로봇"},
    {"code": "035420", "name": "NAVER", "theme": "인터넷/AI"},
    {"code": "035720", "name": "카카오", "theme": "인터넷"},
    {"code": "373220", "name": "LG에너지솔루션", "theme": "2차전지"},
    {"code": "247540", "name": "에코프로비엠", "theme": "2차전지"},
    {"code": "196170", "name": "알테오젠", "theme": "바이오"},
    {"code": "028300", "name": "HLB", "theme": "바이오"},
]


def _now_kst() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


def _clean_code(value: Any) -> str:
    text = str(value or "").upper().strip()
    if text.endswith((".KS", ".KQ")):
        text = text[:-3]
    if text.startswith("A") and len(text) == 7 and text[1:].isdigit():
        text = text[1:]
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits[-6:] if len(digits) >= 6 else text


def _symbol_map(symbols: Sequence[Any] | None = None) -> list[dict[str, str]]:
    if not symbols:
        return [dict(item) for item in DEFAULT_MAJOR_SYMBOLS]
    defaults = {_clean_code(item["code"]): item for item in DEFAULT_MAJOR_SYMBOLS}
    mapped: list[dict[str, str]] = []
    for item in symbols:
        if isinstance(item, Mapping):
            code = _clean_code(item.get("code") or item.get("symbol"))
            base = defaults.get(code, {})
            mapped.append({"code": code, "name": str(item.get("name") or base.get("name") or code), "theme": str(item.get("theme") or base.get("theme") or "주요종목")})
        else:
            code = _clean_code(item)
            base = defaults.get(code, {})
            mapped.append({"code": code, "name": str(base.get("name") or code), "theme": str(base.get("theme") or "주요종목")})
    return mapped


def _snapshot_list(snapshots: Any) -> list[dict[str, Any]]:
    if not snapshots:
        return []
    values = snapshots.values() if isinstance(snapshots, Mapping) else snapshots
    return [dict(item) for item in values if isinstance(item, Mapping)]


def _material(value: Any, threshold: int = MATERIAL_QTY) -> bool:
    return isinstance(value, (int, float)) and abs(value) >= threshold


def _score_snapshot(snapshot: Mapping[str, Any]) -> tuple[int, list[str], list[str], str]:
    score = 0
    signals: list[str] = []
    risks: list[str] = []
    inst = snapshot.get("institution_net_buy_qty")
    foreign = snapshot.get("foreign_net_buy_qty")
    program = snapshot.get("program_net_buy_qty")
    today = bool(snapshot.get("is_today_confirmed"))
    if _material(inst):
        if inst > 0:
            score += 2
            signals.append("기관순매수")
        else:
            score -= 2
            risks.append("기관매도")
    if _material(foreign):
        if foreign > 0:
            score += 2
            signals.append("외국인순매수")
        else:
            score -= 2
            risks.append("외국인매도")
    if _material(program, PROGRAM_MATERIAL_QTY):
        if program > 0:
            score += 3
            signals.append("프로그램순매수")
        else:
            score -= 3
            risks.append("프로그램매도")
    if today:
        score += 1
        signals.append("당일확인")
    else:
        risks.append("기준일주의")
    if score >= 5:
        action = "추적"
    elif score >= 2:
        action = "눌림대기"
    elif score <= -3:
        action = "버림"
    else:
        action = "관망"
    return score, signals, risks, action


def build_krx_major_flow_watch_report(client: Any | None = None, *, symbols: Sequence[Any] | None = None, snapshots: Any = None, collected_at: str | None = None, as_of_date: str | None = None, limit: int = 16) -> dict[str, Any]:
    watch_symbols = _symbol_map(symbols)[:limit]
    by_code = {_clean_code(item.get("symbol") or item.get("code")): item for item in _snapshot_list(snapshots)}
    results: list[dict[str, Any]] = []
    warnings: list[str] = []
    for meta in watch_symbols:
        code = meta["code"]
        snapshot = by_code.get(code)
        error = None
        if snapshot is None and client is not None:
            try:
                snapshot = build_krx_symbol_flow_snapshot_v2(client, code, as_of_date=as_of_date)
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                warnings.append(f"{meta['name']}({code}) 수급 조회 실패: {type(exc).__name__}")
                snapshot = {"symbol": code, "warnings": [error]}
        if snapshot is None:
            snapshot = {"symbol": code, "warnings": ["snapshot unavailable"]}
        score, signals, risks, action = _score_snapshot(snapshot)
        results.append({"code": code, "name": meta["name"], "theme": meta["theme"], "score": score, "action": action, "signals": signals, "risks": risks, "snapshot": snapshot, "error": error})
    candidates = sorted(results, key=lambda row: (row["score"], len(row["signals"])), reverse=True)
    env = next((r["snapshot"].get("env") for r in results if r["snapshot"].get("env")), "unknown")
    base_url = next((r["snapshot"].get("base_url") for r in results if r["snapshot"].get("base_url")), "")
    data_dates = {r["code"]: r["snapshot"].get("data_dates") for r in results if r["snapshot"].get("data_dates")}
    return {"mode": "krx_major_flow_watch", "source": "kiwoom_symbol_flow_v2", "env": env, "base_url": base_url, "collected_at": collected_at or _now_kst(), "requested_date": as_of_date or today_kst(), "watched_count": len(results), "results": results, "candidates": candidates, "top_candidates": [row for row in candidates if row["action"] in {"추적", "눌림대기"}][:3], "data_dates": data_dates, "warnings": warnings, "caveats": ["랭킹 TR이 비거나 지연돼도 주요 종목을 고정 감시하는 보조 스캔임", "개별종목 TR 기준일과 env를 확인해야 하며 mock 결과를 prod 수급처럼 말하지 않음"]}


def _fmt_qty(value: Any) -> str:
    return f"{value:+,}주" if isinstance(value, (int, float)) else "n/a"


def format_krx_major_flow_watch_report(report: Mapping[str, Any]) -> list[str]:
    top = list(report.get("top_candidates") or [])
    results = list(report.get("candidates") or [])
    lines = [
        "주요종목 고정 수급 감시: {}개 / env={} / collected_at={}".format(
            report.get("watched_count", 0),
            report.get("env"),
            report.get("collected_at"),
        )
    ]
    if not top:
        lines.append("결론: 관망. 고정 감시 종목 중 추적급 수급 조합 없음.")
    else:
        lines.append(
            "결론: "
            + ", ".join("{}({})".format(row.get("name"), row.get("action")) for row in top)
        )
    for row in (top or results[:3]):
        snap = row.get("snapshot") or {}
        bits = [*row.get("signals", [])]
        if row.get("risks"):
            bits.append("주의=" + "/".join(row.get("risks") or []))
        lines.append(
            "{}({}) {} score={} 기관={} 외인={} 프로그램={} / ".format(
                row.get("name"),
                row.get("code"),
                row.get("action"),
                row.get("score"),
                _fmt_qty(snap.get("institution_net_buy_qty")),
                _fmt_qty(snap.get("foreign_net_buy_qty")),
                _fmt_qty(snap.get("program_net_buy_qty")),
            )
            + (", ".join(bits) or "신호없음")
        )
    if report.get("warnings"):
        lines.append("주의: " + "; ".join(str(x) for x in report.get("warnings", [])[:3]))
    lines.append(
        "데이터: requested_date={} / base={}".format(
            report.get("requested_date"), report.get("base_url") or "unknown"
        )
    )
    return lines


def build_krx_major_flow_watch_response(report: Mapping[str, Any]) -> dict[str, Any]:
    lines = format_krx_major_flow_watch_report(report)
    return {"mode": "krx_major_flow_watch", "summary": lines[0], "focus": lines[1:], "next_actions": ["상위 1~3개만 개별 차트/뉴스로 재확인", "프로그램매도·기준일주의가 붙은 종목은 추격 금지"], "features": ["krx", "kiwoom", "major_flow_watch"], "raw": {"krx_major_flow_watch": dict(report)}}


__all__ = ["DEFAULT_MAJOR_SYMBOLS", "build_krx_major_flow_watch_report", "format_krx_major_flow_watch_report", "build_krx_major_flow_watch_response"]
