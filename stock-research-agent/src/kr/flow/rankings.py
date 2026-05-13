"""Kiwoom-backed KRX ranking scanner v2.

This module is the first consumer of the catalog + collector layers. It keeps
ranking sections independent, normalizes only common fields, and produces a
triage score from multiple confirmed signals. It is read-only.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from ..kiwoom.collectors import TRCallResult, call_market_tr


RANKING_SECTION_SPECS: tuple[tuple[str, str, str, int], ...] = (
    ("trade_value", "ka10032", "거래대금 상위", 8),
    ("volume_surge", "ka10023", "거래량 급증", 5),
    ("investor_intraday", "ka10065", "장중 투자자별 순매수", 7),
    ("foreign_institution", "ka90009", "외국인/기관 매매 상위", 0),
    ("program_net_buy", "ka90003", "프로그램 순매수", 6),
    ("orderbook_surge", "ka10021", "호가잔량 급증", 3),
    ("foreign_streak", "ka10035", "외인 연속 순매매", 3),
    ("credit_ratio", "ka10033", "신용비율 상위", -5),
)


def _first(row: Mapping[str, Any], keys: Iterable[str], default: Any = "") -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return default


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
    except ValueError:
        return None


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    text = str(value).strip().replace(",", "").replace("+", "").replace("%", "")
    try:
        return float(text)
    except ValueError:
        return None


def _base_stock_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "code": _clean_code(_first(row, ("stk_cd", "code", "isu_cd"))),
        "name": str(_first(row, ("stk_nm", "name", "isu_nm"))),
        "price": _to_int(_first(row, ("cur_prc", "price", "now_prc"))),
        "change_pct": _to_float(_first(row, ("flu_rt", "change_pct", "chg_rt"))),
    }


def _normalize_trade_value(row: Mapping[str, Any]) -> dict[str, Any]:
    out = _base_stock_row(row)
    out["trade_value"] = _to_int(_first(row, ("acc_trde_prica", "trde_prica", "trade_value")))
    return out


def _normalize_volume_surge(row: Mapping[str, Any]) -> dict[str, Any]:
    out = _base_stock_row(row)
    out["previous_volume"] = _to_int(_first(row, ("prev_trde_qty", "pred_pre", "prev_volume")))
    out["current_volume"] = _to_int(_first(row, ("now_trde_qty", "trde_qty", "acc_trde_qty", "current_volume")))
    return out


def _normalize_investor_intraday(row: Mapping[str, Any]) -> dict[str, Any]:
    out = _base_stock_row(row)
    out["net_buy_quantity"] = _to_int(_first(row, ("netslmt", "net_buy_quantity", "netprps_qty")))
    return out


def _normalize_foreign_institution(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    buckets = (
        ("foreign_net_buy", "for_netprps_stk_cd", "for_netprps_stk_nm", "for_netprps_amt", "for_netprps_qty"),
        ("institution_net_buy", "orgn_netprps_stk_cd", "orgn_netprps_stk_nm", "orgn_netprps_amt", "orgn_netprps_qty"),
        ("foreign_net_sell", "for_netslmt_stk_cd", "for_netslmt_stk_nm", "for_netslmt_amt", "for_netslmt_qty"),
        ("institution_net_sell", "orgn_netslmt_stk_cd", "orgn_netslmt_stk_nm", "orgn_netslmt_amt", "orgn_netslmt_qty"),
    )
    for bucket, code_key, name_key, amount_key, quantity_key in buckets:
        code = _clean_code(row.get(code_key))
        if not code:
            continue
        items.append({
            "code": code,
            "name": str(row.get(name_key) or ""),
            "bucket": bucket,
            "amount": _to_int(row.get(amount_key)),
            "quantity": _to_int(row.get(quantity_key)),
        })
    return items


def _normalize_program(row: Mapping[str, Any]) -> dict[str, Any]:
    out = _base_stock_row(row)
    out["program_net_buy_amount"] = _to_int(_first(row, ("netprps_amt", "prm_netprps_amt", "program_net_buy_amount")))
    out["program_net_buy_quantity"] = _to_int(_first(row, ("netprps_qty", "prm_netprps_qty", "program_net_buy_quantity")))
    return out


def _normalize_orderbook(row: Mapping[str, Any]) -> dict[str, Any]:
    out = _base_stock_row(row)
    out["bid_quantity"] = _to_int(_first(row, ("bid_req", "tot_bid_req", "bid_quantity")))
    out["ask_quantity"] = _to_int(_first(row, ("ask_req", "tot_ask_req", "ask_quantity")))
    return out


def _normalize_foreign_streak(row: Mapping[str, Any]) -> dict[str, Any]:
    out = _base_stock_row(row)
    out["streak_days"] = _to_int(_first(row, ("cont_netprps_dys", "streak_days", "cont_dys")))
    out["net_buy_quantity"] = _to_int(_first(row, ("netprps_qty", "net_buy_quantity")))
    return out


def _normalize_credit(row: Mapping[str, Any]) -> dict[str, Any]:
    out = _base_stock_row(row)
    out["credit_ratio"] = _to_float(_first(row, ("crd_rt", "credit_ratio")))
    return out


def _normalize_section_rows(section_key: str, rows: list[Any], limit: int) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows[:limit]:
        if not isinstance(row, Mapping):
            continue
        if section_key == "trade_value":
            normalized.append(_normalize_trade_value(row))
        elif section_key == "volume_surge":
            normalized.append(_normalize_volume_surge(row))
        elif section_key == "investor_intraday":
            normalized.append(_normalize_investor_intraday(row))
        elif section_key == "foreign_institution":
            normalized.extend(_normalize_foreign_institution(row))
        elif section_key == "program_net_buy":
            normalized.append(_normalize_program(row))
        elif section_key == "orderbook_surge":
            normalized.append(_normalize_orderbook(row))
        elif section_key == "foreign_streak":
            normalized.append(_normalize_foreign_streak(row))
        elif section_key == "credit_ratio":
            normalized.append(_normalize_credit(row))
        else:
            normalized.append(dict(row))
    return [row for row in normalized if row.get("code")]


def _section_from_result(section_key: str, label: str, result: TRCallResult, limit: int) -> dict[str, Any]:
    rows = _normalize_section_rows(section_key, result.rows, limit)
    status = result.status
    if result.status == "ok" and not rows:
        status = "empty"
    return {
        "label": label,
        "api_id": result.api_id,
        "endpoint": result.endpoint,
        "status": status,
        "return_code": result.return_code,
        "return_msg": result.return_msg,
        "row_count": len(rows),
        "rows": rows,
        "collected_at": result.collected_at,
        "source": result.source,
        "env": result.env,
    }


def _candidate_bucket(score: int, risks: list[str]) -> str:
    if score >= 25:
        return "주도수급"
    if score >= 18:
        return "눌림대기"
    if risks and score < 12:
        return "위험제외"
    if score >= 12:
        return "수급확인"
    if score >= 6:
        return "관찰"
    return "데이터부족"


def _get_candidate(candidates: dict[str, dict[str, Any]], row: Mapping[str, Any]) -> dict[str, Any]:
    code = str(row.get("code") or "")
    candidate = candidates.setdefault(code, {
        "code": code,
        "name": row.get("name") or "",
        "score": 0,
        "signals": [],
        "risks": [],
        "evidence": {},
    })
    if not candidate.get("name") and row.get("name"):
        candidate["name"] = row["name"]
    return candidate


def _add_signal(candidate: dict[str, Any], signal: str, weight: int, evidence_key: str, row: Mapping[str, Any]) -> None:
    if signal not in candidate["signals"]:
        candidate["signals"].append(signal)
        candidate["score"] += weight
    candidate["evidence"][evidence_key] = dict(row)


def _add_risk(candidate: dict[str, Any], risk: str, weight: int, evidence_key: str, row: Mapping[str, Any]) -> None:
    if risk not in candidate["risks"]:
        candidate["risks"].append(risk)
        candidate["score"] += weight
    candidate["evidence"][evidence_key] = dict(row)


def _is_material_flow(row: Mapping[str, Any]) -> bool:
    """Reject tiny foreign/institution buckets that appear in Kiwoom rankings.

    Kiwoom ka90009 can include a large-cap in a net-buy bucket with only a few
    hundred shares. That is not a meaningful 수급 signal for user-facing triage.
    Amount appears to be reported in thousand-KRW units in observed responses,
    so 100_000 ~= 100M KRW. Either amount or quantity must be material.
    """
    amount = abs(row.get("amount") or 0)
    quantity = abs(row.get("quantity") or 0)
    return amount >= 100_000 or quantity >= 10_000


def build_krx_candidates_v2(sections: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}
    signal_map = {
        "trade_value": ("trade_value_top", 8),
        "volume_surge": ("volume_surge", 5),
        "investor_intraday": ("investor_intraday_net_buy", 7),
        "program_net_buy": ("program_net_buy_top", 6),
        "orderbook_surge": ("orderbook_bid_support", 3),
        "foreign_streak": ("foreign_buy_streak", 3),
    }
    for section_key, (signal, weight) in signal_map.items():
        for row in sections.get(section_key, {}).get("rows", []):
            candidate = _get_candidate(candidates, row)
            _add_signal(candidate, signal, weight, section_key, row)

    for row in sections.get("foreign_institution", {}).get("rows", []):
        candidate = _get_candidate(candidates, row)
        bucket = row.get("bucket")
        if bucket == "foreign_net_buy":
            evidence_key = "foreign_net_buy_rank_bucket" if _is_material_flow(row) else "foreign_net_buy_ignored_tiny"
            candidate["evidence"][evidence_key] = dict(row)
        elif bucket == "institution_net_buy":
            evidence_key = "institution_net_buy_rank_bucket" if _is_material_flow(row) else "institution_net_buy_ignored_tiny"
            candidate["evidence"][evidence_key] = dict(row)
        elif bucket == "foreign_net_sell":
            if _is_material_flow(row):
                _add_risk(candidate, "foreign_net_sell_top", -4, "foreign_net_sell", row)
            else:
                candidate["evidence"]["foreign_net_sell_ignored_tiny"] = dict(row)
        elif bucket == "institution_net_sell":
            if _is_material_flow(row):
                _add_risk(candidate, "institution_net_sell_top", -4, "institution_net_sell", row)
            else:
                candidate["evidence"]["institution_net_sell_ignored_tiny"] = dict(row)

    for row in sections.get("credit_ratio", {}).get("rows", []):
        candidate = _get_candidate(candidates, row)
        ratio = row.get("credit_ratio")
        if isinstance(ratio, (int, float)) and ratio >= 7.0:
            _add_risk(candidate, "credit_ratio_high_risk", -5, "credit_ratio", row)

    output = []
    for candidate in candidates.values():
        candidate["bucket"] = _candidate_bucket(candidate["score"], candidate["risks"])
        output.append(candidate)
    return sorted(output, key=lambda item: (item["score"], len(item["signals"])), reverse=True)


def build_krx_ranking_scan_v2(client: Any, *, limit: int = 10) -> dict[str, Any]:
    sections: dict[str, dict[str, Any]] = {}
    source = "kiwoom"
    env = getattr(getattr(client, "config", None), "normalized_env", "unknown")
    base_url = getattr(getattr(client, "config", None), "rest_base_url", "")
    collected_at = ""

    for section_key, api_id, label, _weight in RANKING_SECTION_SPECS:
        result = call_market_tr(client, api_id)
        source = result.source
        env = result.env
        base_url = result.base_url
        collected_at = collected_at or result.collected_at
        sections[section_key] = _section_from_result(section_key, label, result, limit)

    return {
        "source": source,
        "env": env,
        "base_url": base_url,
        "collected_at": collected_at,
        "sections": sections,
        "candidates": build_krx_candidates_v2(sections),
    }


def format_krx_ranking_scan_v2_focus(scan: Mapping[str, Any], *, limit: int = 5) -> list[str]:
    env = scan.get("env", "unknown")
    base_url = scan.get("base_url", "")
    lines = [
        f"Kiwoom KRX ranking v2: source={scan.get('source','kiwoom')} / env={env} / base={base_url}",
        f"수집시각: {scan.get('collected_at','')}",
    ]
    if env == "mock":
        lines.append("env=mock은 Kiwoom 모의투자 도메인 실호출 결과임. prod 전환은 KIWOOM_ENV=prod + 실전 appkey/secret + prod token cache로 수행.")
    else:
        lines.append("env=prod는 Kiwoom 운영 도메인 호출 결과임. 주문 API 비활성 상태 유지.")
    lines.append("주문 API 비활성: catalog gate가 주문/신용주문 TR을 기본 차단함.")

    for section_key, section in scan.get("sections", {}).items():
        lines.append(f"[{section_key}] {section.get('label')} / {section.get('api_id')} / status={section.get('status')} / rows={section.get('row_count')}")

    lines.append("후보:")
    for candidate in scan.get("candidates", [])[:limit]:
        lines.append(
            f"- {candidate.get('name')} {candidate.get('code')} score={candidate.get('score')} bucket={candidate.get('bucket')} "
            f"signals={','.join(candidate.get('signals', []))} risks={','.join(candidate.get('risks', [])) or '-'}"
        )
    return lines


__all__ = [
    "RANKING_SECTION_SPECS",
    "build_krx_candidates_v2",
    "build_krx_ranking_scan_v2",
    "format_krx_ranking_scan_v2_focus",
]
