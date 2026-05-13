from __future__ import annotations

from typing import Any, Iterable

try:
    from ..kiwoom.client import KiwoomRestClient, build_kiwoom_data_client
    from ..kiwoom.collectors import call_market_tr
    from .common import _extract_rows, _first_value, _fmt_float, _fmt_int, _now_iso, _to_float, _to_int, normalize_krx_code
    from .snapshot import _tr_data
except ImportError:  # direct script execution
    from kr.kiwoom.client import KiwoomRestClient, build_kiwoom_data_client
    from kr.kiwoom.collectors import call_market_tr
    from kr.flow.common import _extract_rows, _first_value, _fmt_float, _fmt_int, _now_iso, _to_float, _to_int, normalize_krx_code
    from kr.flow.snapshot import _tr_data


RANK_SCAN_SPECS = {
    "trade_value": {
        "label": "거래대금 상위",
        "tr": "ka10032",
        "endpoint": "/api/dostk/rkinfo",
        "body": {"mrkt_tp": "000", "mang_stk_incls": "0", "stex_tp": "1"},
        "row_keys": ["trde_prica_upper", "trade_value_top", "rows"],
    },
    "investor_intraday": {
        "label": "장중 투자자별 매매 상위",
        "tr": "ka10065",
        "endpoint": "/api/dostk/rkinfo",
        "body": {"mrkt_tp": "000", "amt_qty_tp": "1", "trde_tp": "1", "orgn_tp": "9000", "stex_tp": "1"},
        "row_keys": ["opmr_invsr_trde_upper", "investor_intraday_top", "rows"],
    },
    "foreign_institution": {
        "label": "외국인/기관 매매 상위",
        "tr": "ka90009",
        "endpoint": "/api/dostk/rkinfo",
        "body": {"mrkt_tp": "000", "qry_dt_tp": "0", "date": "", "trde_tp": "1", "sort_tp": "1", "amt_qty_tp": "1", "stex_tp": "1"},
        "row_keys": ["frgnr_orgn_trde_upper", "foreign_institution_top", "rows"],
    },
    "program_net_buy": {
        "label": "프로그램 순매수 상위",
        "tr": "ka90003",
        "endpoint": "/api/dostk/stkinfo",
        "body": {"trde_upper_tp": "1", "amt_qty_tp": "1", "mrkt_tp": "000", "stex_tp": "1"},
        "row_keys": ["prm_netprps_upper_50", "program_net_buy_top", "rows"],
    },
}

def _parse_rank_rows(data: dict[str, Any], row_keys: Iterable[str], limit: int) -> list[dict[str, Any]]:
    parsed: list[dict[str, Any]] = []
    for idx, row in enumerate(_extract_rows(data, row_keys)[:limit], start=1):
        code = normalize_krx_code(
            _first_value(
                row,
                [
                    "stk_cd",
                    "isu_cd",
                    "code",
                    "symbol",
                    "for_netprps_stk_cd",
                    "orgn_netprps_stk_cd",
                    "for_netslmt_stk_cd",
                    "orgn_netslmt_stk_cd",
                ],
            )
        )
        name = _first_value(
            row,
            [
                "stk_nm",
                "isu_nm",
                "name",
                "symbol_name",
                "for_netprps_stk_nm",
                "orgn_netprps_stk_nm",
                "for_netslmt_stk_nm",
                "orgn_netslmt_stk_nm",
            ],
        )
        rank = _to_int(_first_value(row, ["rank", "rank_no", "data_rank"]), absolute=True) or idx
        parsed.append(
            {
                "rank": rank,
                "code": code,
                "name": name or code,
                "current_price": _to_int(_first_value(row, ["cur_prc", "now_prc", "price", "current_price"]), absolute=True),
                "change_pct": _to_float(_first_value(row, ["flu_rt", "chg_rt", "change_pct"])),
                "volume": _to_int(_first_value(row, ["trde_qty", "acc_trde_qty", "volume", "mac"]), absolute=True),
                "trading_value": _to_int(_first_value(row, ["acc_trde_prica", "trde_prica", "trde_amt", "trading_value"]), absolute=True),
                "investor_type": _first_value(row, ["invst_tp", "investor_type", "trde_tp_nm"]),
                "sell_quantity": _to_int(_first_value(row, ["sel_qty", "sell_qty"])),
                "buy_quantity": _to_int(_first_value(row, ["buy_qty", "buy_quantity"])),
                "net_buy_amount": _to_int(_first_value(row, ["netprps_amt", "net_buy_amount", "pure_buy_amt"])),
                "net_buy_quantity": _to_int(_first_value(row, ["netprps_qty", "net_buy_quantity", "pure_buy_qty", "netslmt"])),
                "foreign_net_sell_code": normalize_krx_code(row.get("for_netslmt_stk_cd")),
                "foreign_net_sell_name": row.get("for_netslmt_stk_nm"),
                "foreign_net_sell_amount": _to_int(row.get("for_netslmt_amt")),
                "foreign_net_sell_quantity": _to_int(row.get("for_netslmt_qty")),
                "foreign_net_buy_code": normalize_krx_code(row.get("for_netprps_stk_cd")),
                "foreign_net_buy_name": row.get("for_netprps_stk_nm"),
                "foreign_net_buy_amount": _to_int(_first_value(row, ["frgnr_netprps_amt", "for_netprps_amt", "foreign_net_buy_amount"])),
                "foreign_net_buy_quantity": _to_int(_first_value(row, ["frgnr_netprps_qty", "for_netprps_qty", "foreign_net_buy_quantity"])),
                "institution_net_sell_code": normalize_krx_code(row.get("orgn_netslmt_stk_cd")),
                "institution_net_sell_name": row.get("orgn_netslmt_stk_nm"),
                "institution_net_sell_amount": _to_int(row.get("orgn_netslmt_amt")),
                "institution_net_sell_quantity": _to_int(row.get("orgn_netslmt_qty")),
                "institution_net_buy_code": normalize_krx_code(row.get("orgn_netprps_stk_cd")),
                "institution_net_buy_name": row.get("orgn_netprps_stk_nm"),
                "institution_net_buy_amount": _to_int(_first_value(row, ["orgn_netprps_amt", "inst_netprps_amt", "institution_net_buy_amount"])),
                "institution_net_buy_quantity": _to_int(_first_value(row, ["orgn_netprps_qty", "inst_netprps_qty", "institution_net_buy_quantity"])),
                "program_net_buy_amount": _to_int(_first_value(row, ["prm_netprps_amt", "program_net_buy_amount"])),
                "program_net_buy_quantity": _to_int(_first_value(row, ["prm_netprps_qty", "program_net_buy_quantity"])),
            }
        )
    return parsed


def build_krx_flow_rank_scan(client: Any | None = None, collected_at: str | None = None, limit: int = 10) -> dict[str, Any]:
    client = client or build_kiwoom_data_client()
    source_environment = getattr(getattr(client, "config", None), "env", None)
    collected_at = collected_at or _now_iso()
    sections: dict[str, Any] = {}
    for key, spec in RANK_SCAN_SPECS.items():
        section = {"label": spec["label"], "tr": spec["tr"], "status": "ok", "rows": [], "source": "kiwoom", "source_environment": source_environment}
        try:
            data = _tr_data(client, spec["tr"], spec["endpoint"], dict(spec["body"]))
            section["rows"] = _parse_rank_rows(data, spec["row_keys"], limit)
            if not section["rows"]:
                section["status"] = "empty"
        except Exception as exc:  # keep scan useful even when one TR is unavailable
            section["status"] = "unavailable"
            section["error"] = type(exc).__name__
            section["error_message"] = str(exc)
        sections[key] = section
    return {
        "mode": "krx_flow_rank_scan",
        "source": "kiwoom",
        "source_environment": source_environment,
        "collected_at": collected_at,
        "sections": sections,
        "notes": [
            f"Kiwoom REST 랭킹 TR 기반(env={source_environment or 'unknown'}). 거래대금/투자자/프로그램 섹션은 각 TR 응답 기준이며 실시간성은 TR 기준시각에 따름.",
            "env=mock은 Kiwoom 모의투자 도메인 실호출 결과임. KRX API 기능 검증/모의투자 기준 수급으로 보되, prod 실계좌 도메인과는 구분해야 함.",
            "섹션별 status가 unavailable/empty면 해당 TR 응답 또는 모의투자 지원 범위를 확인해야 함.",
        ],
    }


def _fmt_rank_row(row: dict[str, Any]) -> str:
    bits = [f"#{_fmt_int(row.get('rank'))}", f"{row.get('name') or row.get('code')}({row.get('code')})"]
    if row.get("current_price") is not None:
        bits.append(f"현재가 {_fmt_int(row.get('current_price'))}")
    if row.get("change_pct") is not None:
        bits.append(f"등락률 {_fmt_float(row.get('change_pct'))}%")
    if row.get("trading_value") is not None:
        bits.append(f"거래대금 {_fmt_int(row.get('trading_value'))}")
    if row.get("investor_type"):
        bits.append(f"투자자 {row.get('investor_type')}")
    if row.get("net_buy_amount") is not None:
        bits.append(f"순매수금액 {_fmt_int(row.get('net_buy_amount'))}")
    if row.get("foreign_net_buy_amount") is not None:
        bits.append(f"외국인 {_fmt_int(row.get('foreign_net_buy_amount'))}")
    if row.get("institution_net_buy_amount") is not None:
        bits.append(f"기관 {_fmt_int(row.get('institution_net_buy_amount'))}")
    if row.get("program_net_buy_amount") is not None:
        bits.append(f"프로그램 {_fmt_int(row.get('program_net_buy_amount'))}")
    return " / ".join(bits)


def format_krx_flow_rank_focus(scan: dict[str, Any], per_section: int = 3) -> list[str]:
    env = scan.get("source_environment") or "unknown"
    lines = [f"수집시각: {scan.get('collected_at')} / source=Kiwoom REST / env={env}"]
    for key in ["trade_value", "investor_intraday", "foreign_institution", "program_net_buy"]:
        section = (scan.get("sections") or {}).get(key) or {}
        label = section.get("label") or key
        rows = section.get("rows") or []
        lines.append(f"[{label}] status={section.get('status')} / TR {section.get('tr')}")
        if rows:
            for row in rows[:per_section]:
                lines.append(f"- {_fmt_rank_row(row)}")
        else:
            lines.append("- 데이터 없음/미지원: TR 응답 또는 모의투자 지원 범위 확인")
    return lines


def _candidate_bucket(candidates: dict[str, dict[str, Any]], code: Any, name: Any) -> dict[str, Any] | None:
    normalized = normalize_krx_code(code)
    if not normalized:
        return None
    candidate = candidates.setdefault(
        normalized,
        {
            "code": normalized,
            "name": name or normalized,
            "score": 0,
            "signals": [],
            "metrics": {},
            "judgment": "관찰",
        },
    )
    if name and candidate.get("name") in (None, "", normalized):
        candidate["name"] = name
    return candidate


def _add_candidate_signal(
    candidates: dict[str, dict[str, Any]],
    code: Any,
    name: Any,
    signal: str,
    weight: int,
    metrics: dict[str, Any] | None = None,
) -> None:
    candidate = _candidate_bucket(candidates, code, name)
    if not candidate:
        return
    if signal not in candidate["signals"]:
        candidate["signals"].append(signal)
        candidate["score"] += weight
    if metrics:
        candidate["metrics"].update({key: value for key, value in metrics.items() if value not in (None, "")})


def _judge_candidate(score: int, signals: list[str]) -> str:
    if score >= 7:
        return "눌림 대기"
    if score >= 5:
        return "수급 확인"
    if score >= 3:
        return "관찰"
    return "제외"


def build_krx_flow_trade_candidates(scan: dict[str, Any], limit: int = 10) -> list[dict[str, Any]]:
    sections = scan.get("sections") or {}
    candidates: dict[str, dict[str, Any]] = {}

    for row in (sections.get("trade_value") or {}).get("rows") or []:
        _add_candidate_signal(
            candidates,
            row.get("code"),
            row.get("name"),
            "trade_value_top",
            2,
            {"trade_value_rank": row.get("rank"), "trading_value": row.get("trading_value")},
        )
    for row in (sections.get("investor_intraday") or {}).get("rows") or []:
        _add_candidate_signal(
            candidates,
            row.get("code"),
            row.get("name"),
            "investor_intraday_net_buy",
            2,
            {
                "investor_rank": row.get("rank"),
                "investor_buy_quantity": row.get("buy_quantity"),
                "investor_sell_quantity": row.get("sell_quantity"),
                "investor_net_buy_quantity": row.get("net_buy_quantity"),
                "investor_net_buy_amount": row.get("net_buy_amount"),
            },
        )
    for row in (sections.get("foreign_institution") or {}).get("rows") or []:
        _add_candidate_signal(
            candidates,
            row.get("foreign_net_buy_code") or row.get("code"),
            row.get("foreign_net_buy_name") or row.get("name"),
            "foreign_net_buy_top",
            2,
            {
                "foreign_rank": row.get("rank"),
                "foreign_net_buy_amount": row.get("foreign_net_buy_amount"),
                "foreign_net_buy_quantity": row.get("foreign_net_buy_quantity"),
            },
        )
        _add_candidate_signal(
            candidates,
            row.get("institution_net_buy_code"),
            row.get("institution_net_buy_name"),
            "institution_net_buy_top",
            2,
            {
                "institution_rank": row.get("rank"),
                "institution_net_buy_amount": row.get("institution_net_buy_amount"),
                "institution_net_buy_quantity": row.get("institution_net_buy_quantity"),
            },
        )
    for row in (sections.get("program_net_buy") or {}).get("rows") or []:
        _add_candidate_signal(
            candidates,
            row.get("code"),
            row.get("name"),
            "program_net_buy_top",
            3,
            {
                "program_rank": row.get("rank"),
                "program_net_buy_amount": row.get("program_net_buy_amount"),
                "program_net_buy_quantity": row.get("program_net_buy_quantity"),
            },
        )

    result = []
    for candidate in candidates.values():
        candidate["judgment"] = _judge_candidate(int(candidate.get("score") or 0), candidate.get("signals") or [])
        if candidate["judgment"] != "제외":
            result.append(candidate)
    return sorted(
        result,
        key=lambda item: (
            -(item.get("score") or 0),
            int((item.get("metrics") or {}).get("trade_value_rank") or 9999),
            item.get("code") or "",
        ),
    )[:limit]


def format_krx_flow_trade_candidate_focus(candidates: list[dict[str, Any]], limit: int = 5) -> list[str]:
    lines = ["매매 후보 triage: 추격 금지 원칙, 수급 중첩 종목은 눌림/돌파 재확인"]
    if not candidates:
        lines.append("- 후보 없음: 거래대금·외인/기관·프로그램 중첩 부족")
        return lines
    for candidate in candidates[:limit]:
        metrics = candidate.get("metrics") or {}
        metric_bits = []
        if metrics.get("trading_value") is not None:
            metric_bits.append(f"거래대금 {_fmt_int(metrics.get('trading_value'))}")
        if metrics.get("investor_net_buy_quantity") is not None:
            metric_bits.append(f"장중순매수 {_fmt_int(metrics.get('investor_net_buy_quantity'))}주")
        if metrics.get("foreign_net_buy_amount") is not None:
            metric_bits.append(f"외국인 {_fmt_int(metrics.get('foreign_net_buy_amount'))}")
        if metrics.get("institution_net_buy_amount") is not None:
            metric_bits.append(f"기관 {_fmt_int(metrics.get('institution_net_buy_amount'))}")
        if metrics.get("program_net_buy_amount") is not None:
            metric_bits.append(f"프로그램 {_fmt_int(metrics.get('program_net_buy_amount'))}")
        lines.append(
            f"- {candidate.get('name')}({candidate.get('code')}): score {candidate.get('score')} / "
            f"판단 {candidate.get('judgment')} / signals={','.join(candidate.get('signals') or [])}"
            + (f" / {' / '.join(metric_bits)}" if metric_bits else "")
        )
    return lines


def _candidate_map(scan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {candidate["code"]: candidate for candidate in build_krx_flow_trade_candidates(scan, limit=100) if candidate.get("code")}


def build_krx_flow_rank_watch_report(previous_scan: dict[str, Any], current_scan: dict[str, Any]) -> dict[str, Any]:
    previous = _candidate_map(previous_scan)
    current = _candidate_map(current_scan)
    changes: list[dict[str, Any]] = []
    for code, candidate in current.items():
        old = previous.get(code)
        old_signals = set((old or {}).get("signals") or [])
        new_signals = [signal for signal in candidate.get("signals") or [] if signal not in old_signals]
        old_score = int((old or {}).get("score") or 0)
        score_delta = int(candidate.get("score") or 0) - old_score
        alerts = []
        if old is None:
            alerts.append("new_candidate")
        if score_delta >= 3 or len(new_signals) >= 2:
            alerts.append("signal_strengthening")
        if candidate.get("judgment") == "눌림 대기" and (old or {}).get("judgment") != "눌림 대기":
            alerts.append("triage_upgrade")
        if not alerts and score_delta == 0:
            continue
        changes.append(
            {
                "code": code,
                "name": candidate.get("name"),
                "score": candidate.get("score"),
                "previous_score": old_score,
                "score_delta": score_delta,
                "judgment": candidate.get("judgment"),
                "previous_judgment": (old or {}).get("judgment"),
                "signals": candidate.get("signals") or [],
                "new_signals": new_signals,
                "alerts": alerts,
                "metrics": candidate.get("metrics") or {},
            }
        )
    return {
        "mode": "krx_flow_rank_watch",
        "source": current_scan.get("source") or "kiwoom",
        "previous_collected_at": previous_scan.get("collected_at"),
        "current_collected_at": current_scan.get("collected_at"),
        "changes": sorted(changes, key=lambda item: (-(item.get("score_delta") or 0), -(item.get("score") or 0), item.get("code") or "")),
        "notes": [
            "랭킹 watch는 거래대금·장중투자자·외인기관·프로그램 랭킹 중첩 변화만 감시한다.",
            "판단은 매수 추천이 아니라 수급 기반 triage이며, 추격보다 눌림/재돌파 확인을 기본값으로 둔다.",
        ],
    }


def build_krx_flow_rank_response(scan: dict[str, Any]) -> dict[str, Any]:
    candidates = build_krx_flow_trade_candidates(scan)
    return {
        "agent": "stock-research-agent",
        "mode": "krx_flow_rank_scan",
        "summary": "Kiwoom KRX 수급/매매 랭킹 스캔",
        "symbols": [candidate.get("code") for candidate in candidates if candidate.get("code")],
        "focus": [*format_krx_flow_rank_focus(scan), *format_krx_flow_trade_candidate_focus(candidates)],
        "next_actions": [
            "거래대금 상위와 프로그램 순매수 상위가 겹치는 종목을 우선 추적",
            "외국인/기관 상위와 개별 종목 krx_flow_snapshot을 교차확인",
            "score 7 이상은 추격보다 눌림 대기, score 3~6은 체결강도/호가로 확인",
            "5분 반복 감시는 이전 랭킹 대비 신규 후보·signal_strengthening만 알림으로 압축",
        ],
        "features": ["kiwoom", "krx_flow_rank_scan", "krx_flow_rank_watch", "krx_flow_watch"],
        "data": {"krx_flow_rank_scan": scan, "trade_candidates": candidates},
    }


def format_krx_flow_rank_watch_focus(report: dict[str, Any], limit: int = 5) -> list[str]:
    lines = [
        f"랭킹 변화 감시: {report.get('previous_collected_at')} -> {report.get('current_collected_at')} / source=Kiwoom REST",
        "원칙: 신규 후보·수급 중첩 강화만 알림, 단순 거래대금 급등은 추격 금지",
    ]
    changes = report.get("changes") or []
    if not changes:
        lines.append("- 유의미한 수급/매매 랭킹 변화 없음")
        return lines
    for change in changes[:limit]:
        lines.append(
            f"- {change.get('name')}({change.get('code')}): score {change.get('previous_score')}->{change.get('score')} "
            f"delta {change.get('score_delta')} / 판단 {change.get('judgment')} / "
            f"alerts={','.join(change.get('alerts') or [])} / new={','.join(change.get('new_signals') or []) or '-'}"
        )
    return lines


def build_krx_flow_rank_watch_response(report: dict[str, Any]) -> dict[str, Any]:
    symbols = [change.get("code") for change in report.get("changes") or [] if change.get("code")]
    return {
        "agent": "stock-research-agent",
        "mode": "krx_flow_rank_watch",
        "summary": f"Kiwoom KRX 수급/매매 랭킹 변화 감시: {', '.join(symbols[:5]) if symbols else '변화 없음'}",
        "symbols": symbols,
        "focus": format_krx_flow_rank_watch_focus(report),
        "next_actions": [
            "signal_strengthening은 개별 krx_flow_snapshot으로 체결강도·호가·프로그램을 확인",
            "new_candidate는 첫 알림만 보고 추격하지 말고 다음 5분 랭킹 유지 여부 확인",
            "눌림 대기 후보만 관심종목으로 승격하고 단순 거래대금 후보는 관찰",
        ],
        "features": ["kiwoom", "krx_flow_rank_watch", "krx_flow_rank_scan"],
        "data": {"krx_flow_rank_watch": report},
    }
