"""Per-symbol KRX supply/demand snapshot backed by Kiwoom official REST TRs.

This module deliberately treats ranking TRs as candidate discovery only. For a
specific symbol, it validates dated institution/foreign/program flows through
symbol-level TRs such as ka10009, ka10045 and ka90008.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

try:
    from ..kiwoom.collectors import TRCallResult, call_market_tr
except ImportError:  # direct script execution via src/main.py
    from kr.kiwoom.collectors import TRCallResult, call_market_tr

KST = timezone(timedelta(hours=9))
MATERIAL_QTY = 10_000
MATERIAL_AMOUNT = 100_000


def today_kst() -> str:
    return datetime.now(KST).strftime("%Y%m%d")


def _days_before(yyyymmdd: str, days: int) -> str:
    dt = datetime.strptime(yyyymmdd, "%Y%m%d") - timedelta(days=days)
    return dt.strftime("%Y%m%d")


def _clean_code(value: Any) -> str:
    code = str(value or "").strip().upper()
    if code.startswith("A") and len(code) == 7:
        code = code[1:]
    if code.endswith(".KS") or code.endswith(".KQ"):
        code = code[:6]
    return code.zfill(6) if code.isdigit() and len(code) <= 6 else code


def _to_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    text = str(value).strip().replace(",", "")
    sign = -1 if text.startswith("-") else 1
    text = text.replace("+", "").replace("-", "")
    try:
        return sign * int(float(text))
    except (TypeError, ValueError):
        return None


def _first_row(result: TRCallResult) -> Mapping[str, Any]:
    return result.rows[0] if result.rows and isinstance(result.rows[0], Mapping) else {}


def _latest_dated_row(rows: list[Any], requested_date: str) -> tuple[Mapping[str, Any], str, bool]:
    dict_rows = [row for row in rows if isinstance(row, Mapping)]
    for row in dict_rows:
        dt = str(row.get("dt") or row.get("date") or "")
        if dt == requested_date:
            return row, dt, True
    if dict_rows:
        row = dict_rows[0]
        dt = str(row.get("dt") or row.get("date") or "")
        return row, dt, False
    return {}, "", False


def _market_kind(result: TRCallResult) -> dict[str, Any]:
    return {
        "api_id": result.api_id,
        "status": result.status,
        "return_code": result.return_code,
        "return_msg": result.return_msg,
        "row_count": result.row_count,
        "collected_at": result.collected_at,
    }


def _material(value: int | None, amount: int | None = None) -> bool:
    qty_ok = value is not None and abs(value) >= MATERIAL_QTY
    amt_ok = amount is not None and abs(amount) >= MATERIAL_AMOUNT
    return qty_ok or amt_ok


def _classify(snapshot: dict[str, Any]) -> str:
    if not snapshot.get("is_today_confirmed"):
        return "기준일미확인"
    inst = snapshot.get("institution_net_buy_qty")
    foreign = snapshot.get("foreign_net_buy_qty")
    program = snapshot.get("program_net_buy_qty")
    if inst is not None and inst < 0 and _material(inst):
        return "기관매도"
    if program is not None and program < 0 and _material(program):
        return "프로그램매도"
    if inst is not None and inst > 0 and foreign is not None and foreign > 0 and (program is None or program >= 0):
        return "동반순매수"
    if inst is not None and inst > 0 and _material(inst):
        return "기관순매수"
    return "관찰"


def build_krx_symbol_flow_snapshot_v2(client: Any, symbol: str, *, as_of_date: str | None = None, lookback_days: int = 21) -> dict[str, Any]:
    requested_date = as_of_date or today_kst()
    code = _clean_code(symbol)
    warnings: list[str] = []
    calls: dict[str, dict[str, Any]] = {}
    data_dates: dict[str, str] = {}

    institution_scalar = call_market_tr(client, "ka10009", {"stk_cd": code})
    calls["institution_scalar"] = _market_kind(institution_scalar)
    scalar_date = str(institution_scalar.data.get("date") or "")
    if scalar_date:
        data_dates["ka10009"] = scalar_date

    institution_trend = call_market_tr(
        client,
        "ka10045",
        {
            "stk_cd": code,
            "strt_dt": _days_before(requested_date, lookback_days),
            "end_dt": requested_date,
            "orgn_prsm_unp_tp": "1",
            "for_prsm_unp_tp": "1",
        },
    )
    calls["institution_trend"] = _market_kind(institution_trend)
    trend_row, trend_date, trend_is_requested = _latest_dated_row(institution_trend.rows, requested_date)
    if trend_date:
        data_dates["ka10045"] = trend_date

    program_trend = call_market_tr(client, "ka90008", {"amt_qty_tp": "1", "stk_cd": code, "date": requested_date})
    calls["program_trend"] = _market_kind(program_trend)
    program_row = _first_row(program_trend)
    program_time_value = program_row.get("base_pric_tm") or program_row.get("tm")
    if program_time_value:
        data_dates["ka90008_time"] = str(program_time_value)

    foreign_trend = call_market_tr(client, "ka10008", {"stk_cd": code})
    calls["foreign_trend"] = _market_kind(foreign_trend)
    foreign_row, foreign_date, _foreign_is_requested = _latest_dated_row(foreign_trend.rows, requested_date)
    if foreign_date:
        data_dates["ka10008"] = foreign_date

    institution_qty = _to_int(trend_row.get("orgn_daly_nettrde_qty"))
    foreign_qty = _to_int(trend_row.get("for_daly_nettrde_qty"))
    if institution_qty is None:
        institution_qty = _to_int(institution_scalar.data.get("orgn_daly_nettrde"))
    if foreign_qty is None:
        foreign_qty = _to_int(institution_scalar.data.get("frgnr_daly_nettrde"))

    scalar_today = scalar_date == requested_date if scalar_date else False
    is_today_confirmed = trend_is_requested or scalar_today
    if not is_today_confirmed:
        seen = ", ".join(f"{k}={v}" for k, v in data_dates.items()) or "none"
        warnings.append(f"requested_date={requested_date} 당일 기관/외인 데이터 미확인; data_dates: {seen}")
    if institution_qty is not None and abs(institution_qty) < MATERIAL_QTY:
        warnings.append(f"기관 순매수 {institution_qty}주는 materiality threshold {MATERIAL_QTY}주 미만이라 수급 양호 근거로 사용하지 않음")

    snapshot: dict[str, Any] = {
        "source": getattr(institution_scalar, "source", "kiwoom"),
        "env": getattr(institution_scalar, "env", "unknown"),
        "base_url": getattr(institution_scalar, "base_url", ""),
        "collected_at": getattr(institution_scalar, "collected_at", ""),
        "symbol": code,
        "requested_date": requested_date,
        "data_dates": data_dates,
        "is_today_confirmed": is_today_confirmed,
        "institution_net_buy_qty": institution_qty,
        "foreign_net_buy_qty": foreign_qty,
        "program_net_buy_qty": _to_int(program_row.get("prm_netprps_qty")),
        "program_net_buy_amt": _to_int(program_row.get("prm_netprps_amt")),
        "program_time": str(program_row.get("tm") or ""),
        "foreign_position_change_qty": _to_int(foreign_row.get("chg_qty")),
        "warnings": warnings,
        "calls": calls,
        "raw_evidence": {
            "ka10009": institution_scalar.data,
            "ka10045_row": dict(trend_row),
            "ka90008_row": dict(program_row),
            "ka10008_row": dict(foreign_row),
        },
    }
    snapshot["supply_signal"] = _classify(snapshot)
    return snapshot


def format_krx_symbol_flow_snapshot_v2(snapshot: Mapping[str, Any]) -> list[str]:
    lines = [
        f"Kiwoom symbol flow v2: {snapshot.get('symbol')} / source={snapshot.get('source')} / env={snapshot.get('env')} / base={snapshot.get('base_url')}",
        f"requested_date={snapshot.get('requested_date')} / collected_at={snapshot.get('collected_at')} / signal={snapshot.get('supply_signal')}",
    ]
    if snapshot.get("env") == "mock":
        lines.append("env=mock은 Kiwoom 모의투자 도메인 실호출 결과임. 오늘/prod 수급처럼 단정 금지.")
    lines.append(f"기관 순매수: {snapshot.get('institution_net_buy_qty')}주")
    lines.append(f"외국인 순매수: {snapshot.get('foreign_net_buy_qty')}주")
    lines.append(f"프로그램 순매수: {snapshot.get('program_net_buy_qty')}주 / {snapshot.get('program_net_buy_amt')} 금액단위 / time={snapshot.get('program_time')}")
    lines.append(f"data_dates: {snapshot.get('data_dates')}")
    if snapshot.get("warnings"):
        lines.append("warnings:")
        lines.extend(f"- {warning}" for warning in snapshot.get("warnings", []))
    return lines


__all__ = ["build_krx_symbol_flow_snapshot_v2", "format_krx_symbol_flow_snapshot_v2", "today_kst"]
