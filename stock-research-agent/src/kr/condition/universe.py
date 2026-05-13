"""Build condition-search universes from Kiwoom KRX ranking scans.

The condition engine is intentionally pure and accepts stock snapshots.  This
module bridges real Kiwoom ranking scan output into that stock snapshot shape
without making trading/order calls.
"""

from __future__ import annotations

from typing import Any

try:  # package import
    from ..flow.common import _to_float, _to_int, normalize_krx_code
except ImportError:  # direct script execution
    from kr.flow.common import _to_float, _to_int, normalize_krx_code


def _first_value(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _ensure_stock(stocks: dict[str, dict[str, Any]], code: Any, name: Any = None) -> dict[str, Any] | None:
    norm = normalize_krx_code(str(code)) if code not in (None, "") else ""
    if not norm:
        return None
    stock = stocks.setdefault(norm, {"code": norm, "name": str(name or norm)})
    if name and (not stock.get("name") or stock.get("name") == norm):
        stock["name"] = str(name)
    stock.setdefault("rank_signals", [])
    stock.setdefault("rank_sources", [])
    return stock


def _append_unique(target: list[Any], value: Any) -> None:
    if value not in (None, "") and value not in target:
        target.append(value)


def _merge_number(stock: dict[str, Any], key: str, value: Any, *, prefer_existing: bool = False) -> None:
    parsed = _to_float(value) if key.endswith("pct") or key.endswith("ratio") else _to_int(value)
    if parsed is None:
        return
    if prefer_existing and stock.get(key) not in (None, ""):
        return
    stock[key] = parsed


def _merge_trade_value_rows(stocks: dict[str, dict[str, Any]], rows: list[dict[str, Any]]) -> None:
    for idx, row in enumerate(rows, 1):
        stock = _ensure_stock(stocks, row.get("code") or row.get("stk_cd"), row.get("name") or row.get("stk_nm"))
        if not stock:
            continue
        rank = _to_int(_first_value(row, "rank", "rnkg", "ranking")) or idx
        stock["trade_value_rank"] = rank
        _merge_number(stock, "trade_value", _first_value(row, "trade_value", "trading_value", "accumulated_trading_value", "trde_prica", "trde_amt"))
        _merge_number(stock, "change_pct", _first_value(row, "change_pct", "pct", "flu_rt", "change_rate"))
        _merge_number(stock, "price", _first_value(row, "price", "current_price", "cur_prc", "close"), prefer_existing=True)
        _append_unique(stock["rank_signals"], "trade_value_top")
        _append_unique(stock["rank_sources"], "trade_value")


def _merge_investor_rows(stocks: dict[str, dict[str, Any]], rows: list[dict[str, Any]]) -> None:
    for idx, row in enumerate(rows, 1):
        stock = _ensure_stock(stocks, row.get("code") or row.get("stk_cd"), row.get("name") or row.get("stk_nm"))
        if not stock:
            continue
        stock["investor_intraday_rank"] = _to_int(_first_value(row, "rank", "rnkg")) or idx
        _merge_number(stock, "investor_intraday_net_buy", _first_value(row, "net_buy_amount", "net_buy", "netslmt", "net_buy_quantity"))
        _merge_number(stock, "investor_intraday_net_buy_qty", _first_value(row, "net_buy_quantity", "netslmt", "buy_quantity"))
        _append_unique(stock["rank_signals"], "investor_intraday_net_buy")
        _append_unique(stock["rank_sources"], "investor_intraday")


def _merge_foreign_institution_rows(stocks: dict[str, dict[str, Any]], rows: list[dict[str, Any]]) -> None:
    for idx, row in enumerate(rows, 1):
        foreign = _ensure_stock(
            stocks,
            _first_value(row, "foreign_net_buy_code", "for_netprps_code", "foreign_code"),
            _first_value(row, "foreign_net_buy_name", "for_netprps_name", "foreign_name"),
        )
        if foreign:
            foreign["foreign_rank"] = _to_int(_first_value(row, "foreign_rank", "rank", "rnkg")) or idx
            _merge_number(foreign, "foreign_net_buy", _first_value(row, "foreign_net_buy_quantity", "foreign_net_buy_amount", "for_netprps_qty", "for_netprps_amt"))
            _merge_number(foreign, "foreign_net_buy_amount", _first_value(row, "foreign_net_buy_amount", "for_netprps_amt"))
            _append_unique(foreign["rank_signals"], "foreign_net_buy_top")
            _append_unique(foreign["rank_sources"], "foreign_institution")

        institution = _ensure_stock(
            stocks,
            _first_value(row, "institution_net_buy_code", "orgn_netprps_code", "institution_code"),
            _first_value(row, "institution_net_buy_name", "orgn_netprps_name", "institution_name"),
        )
        if institution:
            institution["institution_rank"] = _to_int(_first_value(row, "institution_rank", "rank", "rnkg")) or idx
            _merge_number(institution, "institution_net_buy", _first_value(row, "institution_net_buy_quantity", "institution_net_buy_amount", "orgn_netprps_qty", "orgn_netprps_amt"))
            _merge_number(institution, "institution_net_buy_amount", _first_value(row, "institution_net_buy_amount", "orgn_netprps_amt"))
            _append_unique(institution["rank_signals"], "institution_net_buy_top")
            _append_unique(institution["rank_sources"], "foreign_institution")


def _merge_program_rows(stocks: dict[str, dict[str, Any]], rows: list[dict[str, Any]]) -> None:
    for idx, row in enumerate(rows, 1):
        stock = _ensure_stock(stocks, row.get("code") or row.get("stk_cd"), row.get("name") or row.get("stk_nm"))
        if not stock:
            continue
        stock["program_rank"] = _to_int(_first_value(row, "rank", "rnkg")) or idx
        _merge_number(stock, "program_net_buy", _first_value(row, "program_net_buy_quantity", "program_net_buy_amount", "prm_netprps_qty", "prm_netprps_amt"))
        _merge_number(stock, "program_net_buy_amount", _first_value(row, "program_net_buy_amount", "prm_netprps_amt"))
        _append_unique(stock["rank_signals"], "program_net_buy_top")
        _append_unique(stock["rank_sources"], "program_net_buy")


def _merge_candidates(stocks: dict[str, dict[str, Any]], candidates: list[dict[str, Any]]) -> None:
    for candidate in candidates or []:
        stock = _ensure_stock(stocks, candidate.get("code"), candidate.get("name"))
        if not stock:
            continue
        stock["rank_candidate_score"] = candidate.get("score")
        stock["rank_judgment"] = candidate.get("judgment")
        for signal in candidate.get("signals") or []:
            _append_unique(stock["rank_signals"], signal)
        metrics = candidate.get("metrics") or {}
        for key, value in metrics.items():
            if key in {"trade_value_rank", "trade_value", "foreign_net_buy_amount", "foreign_net_buy_quantity", "institution_net_buy_amount", "institution_net_buy_quantity", "program_net_buy_amount", "program_net_buy_quantity"}:
                target = {
                    "foreign_net_buy_quantity": "foreign_net_buy",
                    "institution_net_buy_quantity": "institution_net_buy",
                    "program_net_buy_quantity": "program_net_buy",
                }.get(key, key)
                _merge_number(stock, target, value, prefer_existing=True)


def build_condition_universe_from_rank_scan(
    scan: dict[str, Any],
    *,
    candidates: list[dict[str, Any]] | None = None,
    limit: int = 30,
) -> dict[str, Any]:
    """Convert  output into  stock snapshots."""
    sections = scan.get("sections") or {}
    stocks: dict[str, dict[str, Any]] = {}

    _merge_trade_value_rows(stocks, (sections.get("trade_value") or {}).get("rows") or [])
    _merge_investor_rows(stocks, (sections.get("investor_intraday") or {}).get("rows") or [])
    _merge_foreign_institution_rows(stocks, (sections.get("foreign_institution") or {}).get("rows") or [])
    _merge_program_rows(stocks, (sections.get("program_net_buy") or {}).get("rows") or [])
    _merge_candidates(stocks, candidates or [])

    ordered = sorted(
        stocks.values(),
        key=lambda row: (
            int(row.get("trade_value_rank") or 9999),
            -(int(row.get("rank_candidate_score") or 0)),
            row.get("code") or "",
        ),
    )[:limit]

    caveats = [
        "rank_scan 기반 universe라 개별종목 오늘 수급 확정 전 단계",
        "ka90009/ka10065 랭킹 bucket은 후보 발견용이며 기관/외국인 확정값은 symbol_flow로 재확인 필요",
    ]
    if (sections.get("program_net_buy") or {}).get("status") in {"empty", "error"}:
        caveats.append("프로그램 순매수 랭킹이 비었거나 실패해 program_net_buy 점수는 제한적")

    return {
        "mode": "krx_condition_universe",
        "source": scan.get("source") or "kiwoom_rank_scan",
        "source_environment": scan.get("source_environment") or scan.get("env"),
        "base_url": scan.get("base_url"),
        "collected_at": scan.get("collected_at"),
        "stock_count": len(ordered),
        "stocks": ordered,
        "caveats": caveats,
    }
