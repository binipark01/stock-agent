"""Kiwoom domestic-stock API catalog and safety gates.

This module intentionally contains metadata only. It does not call Kiwoom,
issue tokens, or place orders. Order/credit-order TRs are cataloged so they can
be explicitly blocked by default.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


MARKET_READONLY = "market_readonly"
ACCOUNT_READONLY = "account_readonly"
ORDER_MUTATION = "order_mutation"


class KiwoomApiCatalogError(KeyError):
    """Raised when a category or TR is not present in the local Kiwoom catalog."""


class KiwoomApiPermissionError(PermissionError):
    """Raised when a Kiwoom TR is not allowed by the current safety gate."""


@dataclass(frozen=True)
class KiwoomCategory:
    key: str
    job_tp_code: str
    label: str
    endpoint: str
    risk_tier: str
    api_count: int | None = None


@dataclass(frozen=True)
class KiwoomTR:
    api_id: str
    name: str
    category: str
    endpoint: str
    risk_tier: str
    default_body: Mapping[str, str] = field(default_factory=dict)
    row_keys: tuple[str, ...] = ()
    priority: str = "p2"
    notes: str = ""


def _category(key: str, job_tp_code: str, label: str, endpoint: str, risk_tier: str, api_count: int) -> KiwoomCategory:
    return KiwoomCategory(key, job_tp_code, label, endpoint, risk_tier, api_count)


KIWOOM_CATEGORIES: dict[str, KiwoomCategory] = {
    "acnt": _category("acnt", "08", "계좌", "/api/dostk/acnt", ACCOUNT_READONLY, 33),
    "shsa": _category("shsa", "17", "공매도", "/api/dostk/shsa", MARKET_READONLY, 1),
    "frgnistt": _category("frgnistt", "03", "기관/외국인", "/api/dostk/frgnistt", MARKET_READONLY, 4),
    "slb": _category("slb", "12", "대차거래", "/api/dostk/slb", MARKET_READONLY, 4),
    "rkinfo": _category("rkinfo", "05", "순위정보", "/api/dostk/rkinfo", MARKET_READONLY, 23),
    "mrkcond": _category("mrkcond", "02", "시세", "/api/dostk/mrkcond", MARKET_READONLY, 25),
    "crdordr": _category("crdordr", "16", "신용주문", "/api/dostk/crdordr", ORDER_MUTATION, 4),
    "websocket": _category("websocket", "14", "실시간시세", "/api/dostk/websocket", MARKET_READONLY, 19),
    "sect": _category("sect", "04", "업종", "/api/dostk/sect", MARKET_READONLY, 6),
    "condition": _category("condition", "15", "조건검색", "/api/dostk/websocket", MARKET_READONLY, 4),
    "stkinfo": _category("stkinfo", "01", "종목정보", "/api/dostk/stkinfo", MARKET_READONLY, 31),
    "ordr": _category("ordr", "13", "주문", "/api/dostk/ordr", ORDER_MUTATION, 8),
    "chart": _category("chart", "07", "차트", "/api/dostk/chart", MARKET_READONLY, 21),
    "thme": _category("thme", "11", "테마", "/api/dostk/thme", MARKET_READONLY, 2),
    "elw": _category("elw", "06", "ELW", "/api/dostk/elw", MARKET_READONLY, 11),
    "etf": _category("etf", "10", "ETF", "/api/dostk/etf", MARKET_READONLY, 9),
}


def _tr(
    api_id: str,
    name: str,
    category: str,
    *,
    default_body: Mapping[str, str] | None = None,
    row_keys: tuple[str, ...] = (),
    priority: str = "p2",
    risk_tier: str | None = None,
    notes: str = "",
) -> KiwoomTR:
    try:
        cat = KIWOOM_CATEGORIES[category]
    except KeyError as exc:
        raise KiwoomApiCatalogError(f"Unknown Kiwoom category: {category}") from exc
    return KiwoomTR(
        api_id=api_id,
        name=name,
        category=category,
        endpoint=cat.endpoint,
        risk_tier=risk_tier or cat.risk_tier,
        default_body=dict(default_body or {}),
        row_keys=tuple(row_keys),
        priority=priority,
        notes=notes,
    )


KIWOOM_TRS: dict[str, KiwoomTR] = {
    # Ranking P0
    "ka10032": _tr(
        "ka10032",
        "거래대금상위요청",
        "rkinfo",
        default_body={"mrkt_tp": "000", "mang_stk_incls": "0", "stex_tp": "1"},
        row_keys=("trde_prica_upper",),
        priority="p0",
    ),
    "ka10023": _tr(
        "ka10023",
        "거래량급증요청",
        "rkinfo",
        default_body={"mrkt_tp": "000", "sort_tp": "1", "tm_tp": "1", "trde_qty_tp": "0", "stk_cnd": "0", "pric_tp": "0", "stex_tp": "1"},
        row_keys=("trde_qty_sdnin", "trde_qty_upper"),
        priority="p0",
    ),
    "ka10021": _tr(
        "ka10021",
        "호가잔량급증요청",
        "rkinfo",
        default_body={"mrkt_tp": "000", "sort_tp": "1", "tm_tp": "1", "trde_qty_tp": "0", "stk_cnd": "0", "trde_tp": "1", "stex_tp": "1"},
        row_keys=("bid_req_upper", "ask_req_upper", "req_upper"),
        priority="p1",
    ),
    "ka10033": _tr(
        "ka10033",
        "신용비율상위요청",
        "rkinfo",
        default_body={"mrkt_tp": "000", "trde_qty_tp": "0", "stk_cnd": "0", "updown_incls": "1", "crd_cnd": "0", "stex_tp": "1"},
        row_keys=("crd_rt_upper",),
        priority="p1",
    ),
    "ka10035": _tr(
        "ka10035",
        "외인연속순매매상위요청",
        "rkinfo",
        default_body={"mrkt_tp": "000", "trde_tp": "1", "base_dt_tp": "1", "stex_tp": "1"},
        row_keys=("frgn_cont_nettrde_upper", "frgnr_cont_nettrde_upper"),
        priority="p1",
    ),
    "ka10065": _tr(
        "ka10065",
        "장중투자자별매매상위요청",
        "rkinfo",
        default_body={"mrkt_tp": "000", "amt_qty_tp": "1", "trde_tp": "1", "orgn_tp": "9000", "stex_tp": "1"},
        row_keys=("opmr_invsr_trde_upper",),
        priority="p0",
    ),
    "ka90009": _tr(
        "ka90009",
        "외국인기관매매상위요청",
        "rkinfo",
        default_body={"mrkt_tp": "000", "qry_dt_tp": "0", "date": "", "trde_tp": "1", "sort_tp": "1", "amt_qty_tp": "1", "stex_tp": "1"},
        row_keys=("frgnr_orgn_trde_upper",),
        priority="p0",
        notes="Foreign/institution buy/sell buckets must remain separate.",
    ),
    "ka90003": _tr(
        "ka90003",
        "프로그램순매수상위50요청",
        "stkinfo",
        default_body={"trde_upper_tp": "1", "amt_qty_tp": "1", "mrkt_tp": "000", "stex_tp": "1"},
        row_keys=("prm_netprps_upper_50",),
        priority="p0",
    ),
    # Symbol snapshot P0
    "ka10001": _tr("ka10001", "주식기본정보요청", "stkinfo", default_body={"stk_cd": ""}, priority="p0"),
    "ka10004": _tr("ka10004", "주식호가요청", "mrkcond", default_body={"stk_cd": ""}, priority="p0"),
    "ka10046": _tr("ka10046", "체결강도추이시간별요청", "mrkcond", default_body={"stk_cd": ""}, priority="p0"),
    "ka10063": _tr(
        "ka10063",
        "장중투자자별매매요청",
        "mrkcond",
        default_body={"mrkt_tp": "000", "amt_qty_tp": "1", "invsr": "6", "frgn_all": "0", "smtm_netprps_tp": "0", "stex_tp": "3"},
        row_keys=("opmr_invsr_trde",),
        priority="p0",
        notes="Official docs example uses investor code, not stk_cd; broad intraday market flow only.",
    ),
    "ka10008": _tr("ka10008", "주식외국인종목별매매동향", "frgnistt", default_body={"stk_cd": ""}, row_keys=("stk_frgnr",), priority="p0"),
    "ka10009": _tr("ka10009", "주식기관요청", "frgnistt", default_body={"stk_cd": ""}, priority="p0", notes="Scalar response: date/orgn_daly_nettrde/frgnr_daly_nettrde."),
    "ka10045": _tr(
        "ka10045",
        "종목별기관매매추이요청",
        "mrkcond",
        default_body={"stk_cd": "", "strt_dt": "", "end_dt": "", "orgn_prsm_unp_tp": "1", "for_prsm_unp_tp": "1"},
        row_keys=("stk_orgn_trde_trnsn",),
        priority="p0",
        notes="Official docs row fields include dt/orgn_daly_nettrde_qty/for_daly_nettrde_qty; use this for per-symbol dated flow confirmation.",
    ),
    "ka90008": _tr(
        "ka90008",
        "종목시간별프로그램매매추이요청",
        "mrkcond",
        default_body={"amt_qty_tp": "1", "stk_cd": "", "date": ""},
        row_keys=("stk_tm_prm_trde_trnsn",),
        priority="p0",
    ),
    "ka90004": _tr(
        "ka90004",
        "종목별프로그램매매현황",
        "stkinfo",
        default_body={"dt": "", "mrkt_tp": "P00101", "stex_tp": "1"},
        row_keys=("stk_prm_trde_prst",),
        priority="p0",
    ),
    "ka10014": _tr(
        "ka10014",
        "공매도추이요청",
        "shsa",
        default_body={"stk_cd": "", "tm_tp": "1", "strt_dt": "", "end_dt": ""},
        row_keys=("shrts_trnsn",),
        priority="p0",
    ),
    "ka10013": _tr(
        "ka10013",
        "신용매매동향요청",
        "stkinfo",
        default_body={"stk_cd": "", "dt": "", "qry_tp": "1"},
        row_keys=("crd_trde_trend",),
        priority="p0",
    ),
    # Stock-loan P0
    "ka10068": _tr("ka10068", "대차거래추이요청", "slb", priority="p0"),
    "ka10069": _tr("ka10069", "대차거래상위10종목요청", "slb", priority="p0"),
    "ka20068": _tr("ka20068", "대차거래추이요청(종목별)", "slb", default_body={"stk_cd": ""}, priority="p0"),
    "ka90012": _tr("ka90012", "대차거래내역요청", "slb", priority="p0"),
    # Theme/sector/ETF P0
    "ka90001": _tr("ka90001", "테마그룹별요청", "thme", priority="p0"),
    "ka90002": _tr("ka90002", "테마구성종목요청", "thme", default_body={"theme_grp_cd": ""}, priority="p0"),
    "ka10051": _tr("ka10051", "업종별투자자순매수요청", "sect", priority="p0"),
    "ka10010": _tr("ka10010", "업종프로그램요청", "sect", priority="p0"),
    "ka20003": _tr("ka20003", "전업종지수요청", "sect", priority="p0"),
    "ka40004": _tr("ka40004", "ETF전체시세요청", "etf", priority="p0"),
    "ka40002": _tr("ka40002", "ETF종목정보요청", "etf", default_body={"stk_cd": ""}, priority="p0"),
    # Sensitive/account examples for gates
    "kt00001": _tr("kt00001", "예수금상세현황요청", "acnt", priority="p2"),
    "ka00001": _tr("ka00001", "계좌번호조회", "acnt", priority="p2"),
    # Mutating order examples for gates
    "kt10000": _tr("kt10000", "주식 매수주문", "ordr", priority="p2"),
    "kt10001": _tr("kt10001", "주식 매도주문", "ordr", priority="p2"),
    "kt10006": _tr("kt10006", "신용 매수주문", "crdordr", priority="p2"),
}


def get_category(key: str) -> KiwoomCategory:
    try:
        return KIWOOM_CATEGORIES[key]
    except KeyError as exc:
        raise KiwoomApiCatalogError(f"Unknown Kiwoom category: {key}") from exc


def get_tr(api_id: str) -> KiwoomTR:
    try:
        return KIWOOM_TRS[api_id]
    except KeyError as exc:
        raise KiwoomApiCatalogError(f"Unknown Kiwoom TR: {api_id}") from exc


def assert_tr_allowed(api_id: str, *, allow_account: bool = False, allow_order: bool = False) -> KiwoomTR:
    tr = get_tr(api_id)
    if tr.risk_tier == ACCOUNT_READONLY and not allow_account:
        raise KiwoomApiPermissionError(f"Kiwoom account TR {api_id} is blocked unless allow_account=True")
    if tr.risk_tier == ORDER_MUTATION and not allow_order:
        raise KiwoomApiPermissionError(f"Kiwoom order TR {api_id} is blocked unless allow_order=True")
    return tr


def p0_market_trs() -> list[KiwoomTR]:
    return sorted(
        (tr for tr in KIWOOM_TRS.values() if tr.priority == "p0" and tr.risk_tier == MARKET_READONLY),
        key=lambda tr: (tr.category, tr.api_id),
    )


__all__ = [
    "ACCOUNT_READONLY",
    "KIWOOM_CATEGORIES",
    "KIWOOM_TRS",
    "MARKET_READONLY",
    "ORDER_MUTATION",
    "KiwoomApiCatalogError",
    "KiwoomApiPermissionError",
    "KiwoomCategory",
    "KiwoomTR",
    "assert_tr_allowed",
    "get_category",
    "get_tr",
    "p0_market_trs",
]
