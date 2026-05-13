from __future__ import annotations

from typing import Any

try:
    from ..kiwoom.client import KiwoomRestClient, build_kiwoom_data_client
    from .common import _fmt_float, _fmt_int, _now_iso, _to_float, _to_int, normalize_krx_code
except ImportError:  # direct script execution
    from kr.kiwoom.client import KiwoomRestClient, build_kiwoom_data_client
    from kr.flow.common import _fmt_float, _fmt_int, _now_iso, _to_float, _to_int, normalize_krx_code


def _parse_basic(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "tr": "ka10001",
        "code": normalize_krx_code(data.get("stk_cd")),
        "name": data.get("stk_nm") or data.get("name") or "",
        "current_price": _to_int(data.get("cur_prc"), absolute=True),
        "change_value": _to_int(data.get("pred_pre")),
        "change_pct": _to_float(data.get("flu_rt")),
        "volume": _to_int(data.get("mac") or data.get("trde_qty"), absolute=True),
    }


def _parse_orderbook(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "tr": "ka10004",
        "base_time": data.get("bid_req_base_tm") or data.get("base_time"),
        "best_ask": _to_int(data.get("sel_1th_pre_req_pre") or data.get("ask_price_1"), absolute=True),
        "best_bid": _to_int(data.get("buy_1th_pre_req_pre") or data.get("bid_price_1"), absolute=True),
        "ask_volume": _to_int(data.get("sel_1th_pre_req") or data.get("ask_volume_1"), absolute=True),
        "bid_volume": _to_int(data.get("buy_1th_pre_req") or data.get("bid_volume_1"), absolute=True),
    }


def _parse_execution_strength(data: dict[str, Any]) -> dict[str, Any]:
    rows = data.get("cntr_str_tm") or data.get("items") or []
    if isinstance(rows, dict):
        rows = [rows]
    parsed_rows = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        parsed_rows.append(
            {
                "time": row.get("cntr_tm") or row.get("time"),
                "current_price": _to_int(row.get("cur_prc"), absolute=True),
                "trade_quantity": _to_int(row.get("trde_qty"), absolute=True),
                "accumulated_trading_value": _to_int(row.get("acc_trde_prica"), absolute=True),
                "execution_strength": _to_float(row.get("cntr_str"), absolute=True),
                "execution_strength_5m": _to_float(row.get("cntr_str_5min"), absolute=True),
            }
        )
    return {"tr": "ka10046", "rows": parsed_rows, "latest": parsed_rows[0] if parsed_rows else {}}


def _parse_investor_flow(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "tr": "ka10063",
        "net_buy_amount": _to_int(data.get("netprps_amt")),
        "net_buy_quantity": _to_int(data.get("netprps_qty")),
        "buy_amount": _to_int(data.get("buy_amt"), absolute=True),
        "sell_amount": _to_int(data.get("sell_amt"), absolute=True),
        "base_time": data.get("tm") or data.get("base_time"),
        "note": "Kiwoom 장중투자자별매매 TR 기준. 투자자 구분별 상세/지연 여부는 TR 응답 기준으로 별도 확인 필요.",
    }


def _parse_program_intraday(data: dict[str, Any]) -> dict[str, Any]:
    rows = data.get("stk_prm_tm_trde_trnsn") or data.get("items") or []
    if isinstance(rows, dict):
        rows = [rows]
    parsed_rows = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        parsed_rows.append(
            {
                "time": row.get("tm") or row.get("time"),
                "program_sell_amount": _to_int(row.get("prm_sell_amt")),
                "program_buy_amount": _to_int(row.get("prm_buy_amt")),
                "program_net_buy_amount": _to_int(row.get("prm_netprps_amt")),
                "program_net_buy_quantity": _to_int(row.get("prm_netprps_qty")),
            }
        )
    return {"tr": "ka90008", "rows": parsed_rows, "latest": parsed_rows[0] if parsed_rows else {}}


def _tr_data(client: Any, api_id: str, endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
    result = client.post_tr(api_id, endpoint, body)
    return result.data if hasattr(result, "data") else result


def build_krx_flow_snapshot(
    symbols: Iterable[Any],
    client: Any | None = None,
    collected_at: str | None = None,
    include_program_rank: bool = False,
) -> dict[str, Any]:
    client = client or build_kiwoom_data_client()
    source_environment = getattr(getattr(client, "config", None), "env", None)
    collected_at = collected_at or _now_iso()
    codes = [normalize_krx_code(symbol) for symbol in symbols or []]
    codes = [code for code in dict.fromkeys(codes) if code]
    stocks = []
    for code in codes:
        basic = _parse_basic(_tr_data(client, "ka10001", "/api/dostk/stkinfo", {"stk_cd": code}))
        orderbook = _parse_orderbook(_tr_data(client, "ka10004", "/api/dostk/mrkcond", {"stk_cd": code}))
        execution = _parse_execution_strength(_tr_data(client, "ka10046", "/api/dostk/mrkcond", {"stk_cd": code}))
        investor = _parse_investor_flow(_tr_data(client, "ka10063", "/api/dostk/mrkcond", {"stk_cd": code}))
        program = _parse_program_intraday(
            _tr_data(client, "ka90008", "/api/dostk/mrkcond", {"stk_cd": code, "amt_qty_tp": "1", "date": ""})
        )
        stock = {
            "code": code,
            "name": basic.get("name") or code,
            "basic": basic,
            "orderbook": orderbook,
            "execution_strength": execution,
            "intraday_investor_flow": investor,
            "program_intraday": program,
            "trs": ["ka10001", "ka10004", "ka10046", "ka10063", "ka90008"],
        }
        if include_program_rank:
            stock["program_rank"] = {"tr": "ka90003", **_tr_data(client, "ka90003", "/api/dostk/stkinfo", {"stk_cd": code})}
        stocks.append(stock)
    return {
        "mode": "krx_flow_snapshot",
        "source": "kiwoom",
        "collected_at": collected_at,
        "symbols": codes,
        "stocks": stocks,
        "notes": [
            "Kiwoom REST TR 기반 스냅샷. collected_at은 에이전트 수집시각이며 각 TR의 기준시각/기준일은 응답 필드 기준.",
            "실시간 틱/호가/종목프로그램은 WebSocket 0B/0D/0w로 별도 모니터링 가능.",
        ],
    }


def format_krx_flow_focus(snapshot: dict[str, Any]) -> list[str]:
    lines = [f"수집시각: {snapshot.get('collected_at')} / source=Kiwoom REST"]
    for stock in snapshot.get("stocks") or []:
        basic = stock.get("basic") or {}
        orderbook = stock.get("orderbook") or {}
        execution = (stock.get("execution_strength") or {}).get("latest") or {}
        investor = stock.get("intraday_investor_flow") or {}
        program = (stock.get("program_intraday") or {}).get("latest") or {}
        lines.append(
            f"{stock.get('name') or stock.get('code')}({stock.get('code')}): "
            f"현재가 {_fmt_int(basic.get('current_price'))} / 등락률 {_fmt_float(basic.get('change_pct'))}% / "
            f"최우선호가 매도 {_fmt_int(orderbook.get('best_ask'))}, 매수 {_fmt_int(orderbook.get('best_bid'))} "
            f"[TR {basic.get('tr')}, {orderbook.get('tr')}]"
        )
        lines.append(
            f"체결강도 {_fmt_float(execution.get('execution_strength'))} / "
            f"누적거래대금 {_fmt_int(execution.get('accumulated_trading_value'))} "
            f"[TR {(stock.get('execution_strength') or {}).get('tr')}]"
        )
        lines.append(
            f"장중 투자자 순매수: 수량 {_fmt_int(investor.get('net_buy_quantity'))}, 금액 {_fmt_int(investor.get('net_buy_amount'))} "
            f"[TR {investor.get('tr')}]"
        )
        lines.append(
            f"프로그램 순매수: 수량 {_fmt_int(program.get('program_net_buy_quantity'))}, 금액 {_fmt_int(program.get('program_net_buy_amount'))} "
            f"[TR {(stock.get('program_intraday') or {}).get('tr')}]"
        )
    return lines


def _stock_map(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(stock.get("code") or ""): stock for stock in snapshot.get("stocks") or [] if stock.get("code")}


def _stock_metrics(stock: dict[str, Any]) -> dict[str, Any]:
    execution = (stock.get("execution_strength") or {}).get("latest") or {}
    investor = stock.get("intraday_investor_flow") or {}
    program = (stock.get("program_intraday") or {}).get("latest") or {}
    return {
        "price": (stock.get("basic") or {}).get("current_price"),
        "execution_strength": execution.get("execution_strength"),
        "trading_value": execution.get("accumulated_trading_value"),
        "investor_net_buy_amount": investor.get("net_buy_amount"),
        "investor_net_buy_quantity": investor.get("net_buy_quantity"),
        "program_net_buy_amount": program.get("program_net_buy_amount"),
        "program_net_buy_quantity": program.get("program_net_buy_quantity"),
    }


def _delta(current: Any, previous: Any) -> Any:
    if current is None or previous is None:
        return None
    try:
        return current - previous
    except TypeError:
        return None


def build_krx_flow_watch_report(previous_snapshot: dict[str, Any], current_snapshot: dict[str, Any], collected_at: str | None = None) -> dict[str, Any]:
    collected_at = collected_at or current_snapshot.get("collected_at") or _now_iso()
    previous_by_code = _stock_map(previous_snapshot)
    diffs: list[dict[str, Any]] = []
    for current_stock in current_snapshot.get("stocks") or []:
        code = current_stock.get("code")
        if not code or code not in previous_by_code:
            continue
        prev_stock = previous_by_code[code]
        cur = _stock_metrics(current_stock)
        prev = _stock_metrics(prev_stock)
        diff = {
            "code": code,
            "name": current_stock.get("name") or prev_stock.get("name") or code,
            "price_delta": _delta(cur.get("price"), prev.get("price")),
            "execution_strength_delta": _delta(cur.get("execution_strength"), prev.get("execution_strength")),
            "trading_value_delta": _delta(cur.get("trading_value"), prev.get("trading_value")),
            "investor_net_buy_amount_delta": _delta(cur.get("investor_net_buy_amount"), prev.get("investor_net_buy_amount")),
            "investor_net_buy_quantity_delta": _delta(cur.get("investor_net_buy_quantity"), prev.get("investor_net_buy_quantity")),
            "program_net_buy_amount_delta": _delta(cur.get("program_net_buy_amount"), prev.get("program_net_buy_amount")),
            "program_net_buy_quantity_delta": _delta(cur.get("program_net_buy_quantity"), prev.get("program_net_buy_quantity")),
            "current": cur,
            "previous": prev,
            "alerts": [],
        }
        if (diff.get("program_net_buy_amount_delta") or 0) > 0 and (cur.get("program_net_buy_amount") or 0) > 0:
            diff["alerts"].append("program_net_buy_acceleration")
        if (diff.get("execution_strength_delta") or 0) >= 20 and (cur.get("execution_strength") or 0) >= 120:
            diff["alerts"].append("execution_strength_spike")
        if (diff.get("trading_value_delta") or 0) >= 1_000_000_000:
            diff["alerts"].append("trading_value_surge")
        if (diff.get("investor_net_buy_amount_delta") or diff.get("investor_net_buy_quantity_delta") or 0) > 0:
            diff["alerts"].append("investor_net_buy_acceleration")
        diffs.append(diff)
    return {
        "mode": "krx_flow_watch",
        "source": "kiwoom",
        "previous_collected_at": previous_snapshot.get("collected_at"),
        "current_collected_at": current_snapshot.get("collected_at"),
        "collected_at": collected_at,
        "diffs": diffs,
        "notes": [
            "이 report는 두 snapshot 비교 결과. 실시간 체결/호가/프로그램은 WebSocket 0B/0D/0w 누적값과 함께 쓰는 것이 적합.",
            "투자자별 순매수 변화는 REST TR 재조회 기준이며 실시간이라고 과장하지 않기.",
        ],
    }


def format_krx_flow_watch_focus(report: dict[str, Any]) -> list[str]:
    lines = [
        f"비교구간: {report.get('previous_collected_at')} -> {report.get('current_collected_at')} / source=Kiwoom REST",
    ]
    for diff in report.get("diffs") or []:
        lines.append(
            f"{diff.get('name')}({diff.get('code')}): 가격변화 {_fmt_int(diff.get('price_delta'))} / "
            f"체결강도변화 {_fmt_float(diff.get('execution_strength_delta'))} / "
            f"거래대금증가 {_fmt_int(diff.get('trading_value_delta'))}"
        )
        lines.append(
            f"수급변화: 투자자 순매수금액 {_fmt_int(diff.get('investor_net_buy_amount_delta'))}, "
            f"프로그램 순매수금액 {_fmt_int(diff.get('program_net_buy_amount_delta'))} / alerts={','.join(diff.get('alerts') or []) or '-'}"
        )
    if not report.get("diffs"):
        lines.append("비교 가능한 공통 종목 없음")
    return lines


def build_krx_flow_watch_response(report: dict[str, Any]) -> dict[str, Any]:
    symbols = [diff.get("code") for diff in report.get("diffs") or [] if diff.get("code")]
    return {
        "agent": "stock-research-agent",
        "mode": "krx_flow_watch",
        "summary": f"Kiwoom KRX 수급/매매 변화 감시: {', '.join(symbols) if symbols else '비교종목 없음'}",
        "symbols": symbols,
        "focus": format_krx_flow_watch_focus(report),
        "next_actions": [
            "알림은 program_net_buy_acceleration + execution_strength_spike 동시 발생 종목 우선",
            "거래대금 급증만 있고 프로그램/외인기관 수급이 없으면 추격보다 관망",
            "장중 investor TR은 기준시각을 붙이고 WebSocket 프로그램/체결 데이터로 보강",
        ],
        "features": ["kiwoom", "krx_flow_watch", "krx_flow_rank_scan"],
        "data": {"krx_flow_watch": report},
    }


def build_krx_flow_response(snapshot: dict[str, Any]) -> dict[str, Any]:
    focus = format_krx_flow_focus(snapshot)
    symbols = snapshot.get("symbols") or [stock.get("code") for stock in snapshot.get("stocks") or [] if stock.get("code")]
    return {
        "agent": "stock-research-agent",
        "mode": "krx_flow_snapshot",
        "summary": f"Kiwoom KRX 수급 스냅샷: {', '.join(symbols) if symbols else '종목 없음'}",
        "symbols": symbols,
        "focus": focus,
        "next_actions": [
            "몇 분 간격 반복 감시는 krx_flow_watch/WebSocket 0B·0D·0w로 체결강도·호가·프로그램 변화만 추적",
            "투자자별 순매수는 TR 기준시각/기준일을 같이 확인하고, 실시간이라고 과해석하지 않기",
            "급등 종목은 거래대금상위(ka10032)와 프로그램/외인기관 상위(ka90009, ka10065)로 교차검증",
        ],
        "features": ["kiwoom", "krx_flow_snapshot"],
        "data": {"krx_flow_snapshot": snapshot},
    }
