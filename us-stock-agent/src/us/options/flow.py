from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import re
from typing import Any
import urllib.parse
import urllib.request


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        numeric = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
    if math.isnan(numeric) or math.isinf(numeric):
        return None
    return numeric


def _to_int(value: Any) -> int:
    numeric = _to_float(value)
    return int(numeric) if numeric is not None else 0


def _fmt(value: Any, digits: int = 2) -> str:
    numeric = _to_float(value)
    if numeric is None:
        return "n/a"
    return f"{numeric:.{digits}f}"


def _fmt_ratio(value: Any) -> str:
    numeric = _to_float(value)
    return "n/a" if numeric is None else f"{numeric:.2f}"


def parse_occ_option_symbol(option_symbol: str, underlying: str | None = None) -> dict[str, Any]:
    text = str(option_symbol or "").strip().upper()
    pattern = re.compile(r"^([A-Z]{1,6})(\d{2})(\d{2})(\d{2})([CP])(\d{8})$")
    match = pattern.match(text)
    if not match:
        return {"option": text, "underlying": underlying, "expiration": None, "option_type": None, "strike": None}
    root, yy, mm, dd, cp, strike_raw = match.groups()
    year = 2000 + int(yy)
    strike = int(strike_raw) / 1000.0
    return {
        "option": text,
        "underlying": underlying or root,
        "expiration": f"{year:04d}-{int(mm):02d}-{int(dd):02d}",
        "option_type": "call" if cp == "C" else "put",
        "strike": strike,
    }


def _normalize_option_row(symbol: str, row: dict[str, Any]) -> dict[str, Any] | None:
    parsed = parse_occ_option_symbol(str(row.get("option") or row.get("symbol") or row.get("option_symbol") or ""), underlying=symbol)
    if not parsed.get("expiration") or not parsed.get("option_type") or parsed.get("strike") is None:
        return None
    bid = _to_float(row.get("bid"))
    ask = _to_float(row.get("ask"))
    mid = round((bid + ask) / 2, 2) if bid is not None and ask is not None else None
    volume = _to_int(row.get("volume") or row.get("vol"))
    open_interest = _to_int(row.get("open_interest") or row.get("openInterest") or row.get("oi"))
    vol_oi_ratio = round(volume / open_interest, 2) if open_interest else (float(volume) if volume else None)
    normalized = {
        **parsed,
        "bid": bid,
        "ask": ask,
        "mid": mid,
        "last": _to_float(row.get("last_trade_price") or row.get("lastPrice") or row.get("last")),
        "volume": volume,
        "open_interest": open_interest,
        "vol_oi_ratio": vol_oi_ratio,
        "iv": _to_float(row.get("iv") or row.get("impliedVolatility")),
        "delta": _to_float(row.get("delta")),
        "gamma": _to_float(row.get("gamma")),
        "theta": _to_float(row.get("theta")),
        "vega": _to_float(row.get("vega")),
        "last_trade_time": row.get("last_trade_time") or row.get("lastTradeDate"),
    }
    return normalized


def _sum(rows: list[dict[str, Any]], key: str) -> int:
    return sum(_to_int(row.get(key)) for row in rows)


def _top(rows: list[dict[str, Any]], key: str, limit: int = 5) -> list[dict[str, Any]]:
    selected = sorted(rows, key=lambda row: _to_int(row.get(key)), reverse=True)[:limit]
    return [
        {
            "option": row.get("option"),
            "expiration": row.get("expiration"),
            "type": row.get("option_type"),
            "strike": row.get("strike"),
            "volume": row.get("volume"),
            "open_interest": row.get("open_interest"),
            "vol_oi_ratio": row.get("vol_oi_ratio"),
            "iv": row.get("iv"),
            "delta": row.get("delta"),
        }
        for row in selected
    ]


def _wall(rows: list[dict[str, Any]], option_type: str, key: str = "open_interest") -> dict[str, Any] | None:
    typed = [row for row in rows if row.get("option_type") == option_type]
    if not typed:
        return None
    row = max(typed, key=lambda item: _to_int(item.get(key)))
    return {"strike": row.get("strike"), "expiration": row.get("expiration"), "volume": row.get("volume"), "open_interest": row.get("open_interest"), "option": row.get("option")}


def _max_pain(rows: list[dict[str, Any]], expiration: str | None) -> dict[str, Any] | None:
    expiry_rows = [row for row in rows if row.get("expiration") == expiration]
    strikes = sorted({row.get("strike") for row in expiry_rows if row.get("strike") is not None})
    if not strikes:
        return None
    payouts: list[tuple[float, float]] = []
    for settle in strikes:
        payout = 0.0
        for row in expiry_rows:
            strike = _to_float(row.get("strike"))
            oi = _to_float(row.get("open_interest")) or 0.0
            if strike is None:
                continue
            if row.get("option_type") == "call":
                payout += max(float(settle) - strike, 0.0) * oi
            else:
                payout += max(strike - float(settle), 0.0) * oi
        payouts.append((float(settle), payout))
    strike, payout = min(payouts, key=lambda item: item[1])
    return {"expiration": expiration, "strike": strike, "payout_proxy": round(payout, 2)}


def _gamma_exposure(rows: list[dict[str, Any]], current_price: float | None) -> dict[str, Any]:
    if current_price is None:
        return {"net_gamma_proxy": None, "read": "가격 데이터 부족"}
    net = 0.0
    for row in rows:
        gamma = _to_float(row.get("gamma")) or 0.0
        oi = _to_float(row.get("open_interest")) or 0.0
        sign = 1.0 if row.get("option_type") == "call" else -1.0
        net += sign * gamma * oi * 100 * float(current_price)
    if net > 500_000:
        read = "콜 감마 우위, 상승 시 딜러 헤지 추종 가능"
    elif net < -500_000:
        read = "풋 감마 우위, 하락 변동성 확대 주의"
    else:
        read = "감마 중립권"
    return {"net_gamma_proxy": round(net, 2), "read": read}


def _expiration_summaries(rows: list[dict[str, Any]], limit: int = 4) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for expiration in sorted({str(row.get("expiration")) for row in rows if row.get("expiration")}):
        expiry_rows = [row for row in rows if row.get("expiration") == expiration]
        calls = [row for row in expiry_rows if row.get("option_type") == "call"]
        puts = [row for row in expiry_rows if row.get("option_type") == "put"]
        call_volume = _sum(calls, "volume")
        put_volume = _sum(puts, "volume")
        call_oi = _sum(calls, "open_interest")
        put_oi = _sum(puts, "open_interest")
        summaries.append(
            {
                "expiration": expiration,
                "call_volume": call_volume,
                "put_volume": put_volume,
                "call_open_interest": call_oi,
                "put_open_interest": put_oi,
                "put_call_volume_ratio": round(put_volume / call_volume, 2) if call_volume else None,
                "put_call_open_interest_ratio": round(put_oi / call_oi, 2) if call_oi else None,
                "call_wall": _wall(expiry_rows, "call"),
                "put_wall": _wall(expiry_rows, "put"),
            }
        )
    return summaries[:limit]


def _option_alerts(ratio_vol: float | None, unusual: list[dict[str, Any]], call_wall: dict[str, Any] | None, put_wall: dict[str, Any] | None, current_price: float | None, gamma: dict[str, Any]) -> list[str]:
    alerts: list[str] = []
    if ratio_vol is not None and ratio_vol <= 0.6:
        alerts.append("call_volume_bullish")
    if ratio_vol is not None and ratio_vol >= 1.2:
        alerts.append("put_volume_hedge")
    if unusual:
        alerts.append("unusual_options_activity")
    if current_price is not None and call_wall and call_wall.get("strike") is not None:
        strike = _to_float(call_wall.get("strike"))
        if strike is not None and abs(strike - current_price) / current_price <= 0.03:
            alerts.append("near_call_wall")
    if current_price is not None and put_wall and put_wall.get("strike") is not None:
        strike = _to_float(put_wall.get("strike"))
        if strike is not None and abs(current_price - strike) / current_price <= 0.03:
            alerts.append("near_put_wall")
    net_gamma = _to_float(gamma.get("net_gamma_proxy"))
    if net_gamma is not None and net_gamma > 500_000:
        alerts.append("call_gamma_positive")
    elif net_gamma is not None and net_gamma < -500_000:
        alerts.append("put_gamma_negative")
    return list(dict.fromkeys(alerts))


def analyze_options_chain(symbol: str, rows: list[dict[str, Any]], current_price: float | None = None, collected_at: str | None = None) -> dict[str, Any]:
    symbol = str(symbol or "UNKNOWN").upper()
    normalized = [row for item in rows if isinstance(item, dict) and (row := _normalize_option_row(symbol, item))]
    collected_at = collected_at or datetime.now(timezone.utc).isoformat()
    if not normalized:
        return {
            "available": False,
            "summary": f"{symbol} 옵션판: 데이터 부족",
            "symbol": symbol,
            "collected_at": collected_at,
            "focus_lines": [f"옵션판: {symbol} 옵션 체인 데이터 부족"],
            "next_actions": ["Cboe delayed options endpoint 또는 yfinance option_chain 접근 상태 확인"],
        }
    expirations = sorted({str(row.get("expiration")) for row in normalized if row.get("expiration")})
    nearest = expirations[0] if expirations else None
    calls = [row for row in normalized if row.get("option_type") == "call"]
    puts = [row for row in normalized if row.get("option_type") == "put"]
    call_volume = _sum(calls, "volume")
    put_volume = _sum(puts, "volume")
    call_oi = _sum(calls, "open_interest")
    put_oi = _sum(puts, "open_interest")
    unusual = sorted(
        [row for row in normalized if _to_int(row.get("volume")) >= 500 and (_to_float(row.get("vol_oi_ratio")) or 0) >= 1.5],
        key=lambda row: (_to_float(row.get("vol_oi_ratio")) or 0, _to_int(row.get("volume"))),
        reverse=True,
    )[:10]
    max_pain = _max_pain(normalized, nearest)
    gamma = _gamma_exposure(normalized, current_price)
    call_wall = _wall(normalized, "call")
    put_wall = _wall(normalized, "put")
    ratio_vol = round(put_volume / call_volume, 2) if call_volume else None
    ratio_oi = round(put_oi / call_oi, 2) if call_oi else None
    expiration_summaries = _expiration_summaries(normalized)
    alerts = _option_alerts(ratio_vol, unusual, call_wall, put_wall, current_price, gamma)
    if ratio_vol is not None and ratio_vol >= 1.2:
        bias = "풋 거래량 우위, 방어/하방 헤지 강함"
    elif ratio_vol is not None and ratio_vol <= 0.7:
        bias = "콜 거래량 우위, 상방 베팅 우세"
    else:
        bias = "콜/풋 균형권"
    unusual_text = "없음"
    if unusual:
        unusual_text = ", ".join(
            f"{str(row.get('option_type', '?'))[0].upper()}{row.get('strike')} vol/OI {row.get('vol_oi_ratio')}"
            for row in unusual[:3]
        )
    expiry_text = " | ".join(
        f"{row['expiration']} Cvol {row['call_volume']} / Pvol {row['put_volume']} / P/C {_fmt_ratio(row['put_call_volume_ratio'])}"
        for row in expiration_summaries[:3]
    ) or "데이터 부족"
    focus_lines = [
        f"옵션판: {symbol} / price {_fmt(current_price)} / expiry {nearest} / P/C vol {_fmt_ratio(ratio_vol)} / P/C OI {_fmt_ratio(ratio_oi)}",
        f"옵션 source/time: Cboe delayed or provided payload / {collected_at}",
        f"옵션 트리거: {', '.join(alerts) if alerts else '없음'}",
        f"만기별: {expiry_text}",
        f"콜월/풋월: 콜 {call_wall['strike'] if call_wall else 'n/a'} / 풋 {put_wall['strike'] if put_wall else 'n/a'} / max pain {max_pain['strike'] if max_pain else 'n/a'}",
        f"상위 거래량: calls {', '.join(str(row['strike']) for row in _top(calls, 'volume', 3)) or 'n/a'} / puts {', '.join(str(row['strike']) for row in _top(puts, 'volume', 3)) or 'n/a'}",
        f"특이거래: {unusual_text}",
        f"감마/판단: {gamma['read']} / {bias}",
    ]
    next_actions = [
        "콜월 위로 종가 안착하면 상방 confirmation, 실패하면 저항/trim 후보",
        "풋월 이탈 시 헤지성 매도 압력 확인, max pain 부근은 만기 자석 가능성",
        "특이거래는 뉴스/차트 돌파와 같이 확인하고 단독 매수 근거로 쓰지 말 것",
    ]
    return {
        "available": True,
        "summary": f"{symbol} 옵션판: {bias}",
        "symbol": symbol,
        "underlying_price": current_price,
        "collected_at": collected_at,
        "nearest_expiration": nearest,
        "expirations": expirations,
        "totals": {"call_volume": call_volume, "put_volume": put_volume, "call_open_interest": call_oi, "put_open_interest": put_oi},
        "ratios": {"put_call_volume_ratio": ratio_vol, "put_call_open_interest_ratio": ratio_oi},
        "walls": {"call_wall": call_wall, "put_wall": put_wall},
        "max_pain": max_pain,
        "gamma": gamma,
        "alerts": alerts,
        "expiration_summaries": expiration_summaries,
        "top_calls_by_volume": _top(calls, "volume"),
        "top_puts_by_volume": _top(puts, "volume"),
        "top_calls_by_oi": _top(calls, "open_interest"),
        "top_puts_by_oi": _top(puts, "open_interest"),
        "unusual_volume": _top(unusual, "volume", 10),
        "focus_lines": focus_lines,
        "next_actions": next_actions,
    }


def fetch_cboe_options_payload(symbol: str) -> dict[str, Any]:
    encoded = urllib.parse.quote(str(symbol).upper(), safe="")
    url = f"https://cdn.cboe.com/api/global/delayed_quotes/options/{encoded}.json"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))


def build_options_flow_report(symbol: str, cboe_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    symbol = str(symbol or "UNKNOWN").upper()
    source = "cboe_delayed"
    try:
        payload = cboe_payload if cboe_payload is not None else fetch_cboe_options_payload(symbol)
    except Exception as exc:
        return {
            "available": False,
            "source": "cboe_delayed_error",
            "symbol": symbol,
            "summary": f"{symbol} 옵션판: Cboe delayed 호출 실패",
            "focus_lines": [f"옵션판: {symbol} / Cboe 호출 실패: {exc}"],
            "next_actions": ["잠시 후 재시도하거나 yfinance 옵션팩으로 fallback 확인"],
            "error": str(exc),
        }
    data = payload.get("data") if isinstance(payload, dict) else {}
    if not isinstance(data, dict):
        data = {}
    options = data.get("options") if isinstance(data.get("options"), list) else []
    current_price = _to_float(data.get("current_price") or data.get("last") or data.get("close"))
    collected_at = str(payload.get("timestamp") or datetime.now(timezone.utc).isoformat()) if isinstance(payload, dict) else datetime.now(timezone.utc).isoformat()
    report = analyze_options_chain(symbol, options, current_price=current_price, collected_at=collected_at)
    report["source"] = source
    return report


def _sweep_score(report: dict[str, Any]) -> float:
    if not report.get("available"):
        return -1.0
    alerts = list(report.get("alerts") or [])
    unusual = list(report.get("unusual_volume") or [])
    ratios = report.get("ratios") or {}
    ratio_vol = _to_float(ratios.get("put_call_volume_ratio"))
    directional_bonus = 0.0
    if ratio_vol is not None:
        directional_bonus = abs(ratio_vol - 1.0)
    return round(len(alerts) * 10 + len(unusual) * 2 + directional_bonus, 3)


def build_watchlist_options_sweep(symbols: list[str], payloads: dict[str, dict[str, Any]] | None = None, limit: int = 12) -> dict[str, Any]:
    selected = []
    seen: set[str] = set()
    for symbol in symbols or []:
        upper = str(symbol or "").upper()
        if upper and upper not in seen:
            seen.add(upper)
            selected.append(upper)
    reports: list[dict[str, Any]] = []
    for symbol in selected[:limit]:
        report = build_options_flow_report(symbol, cboe_payload=(payloads or {}).get(symbol))
        report["sweep_score"] = _sweep_score(report)
        reports.append(report)
    ranked = sorted(reports, key=lambda row: row.get("sweep_score", -1), reverse=True)
    available = any(row.get("available") for row in ranked)
    top_parts = []
    for row in ranked[:5]:
        if not row.get("available"):
            continue
        alerts = ",".join(list(row.get("alerts") or [])[:2]) or "no-trigger"
        ratios = row.get("ratios") or {}
        top_parts.append(f"{row['symbol']} score {row['sweep_score']} / P/C {_fmt_ratio(ratios.get('put_call_volume_ratio'))} / {alerts}")
    focus_lines = [
        "옵션 관심종목: " + (" | ".join(top_parts) if top_parts else "데이터 부족"),
        f"스캔 심볼: {', '.join(selected[:limit])}",
    ]
    next_actions = [
        "상위 score 종목은 옵션 트리거와 차트 돌파/뉴스를 같이 확인",
        "P/C 급변은 단독 진입 신호가 아니라 헤지/투기 수요 구분 필요",
    ]
    return {
        "available": available,
        "summary": f"옵션 관심종목 스윕: {ranked[0]['symbol']} 우선" if ranked else "옵션 관심종목 스윕: 데이터 부족",
        "symbols": selected[:limit],
        "ranked": [
            {
                "symbol": row.get("symbol"),
                "available": row.get("available"),
                "summary": row.get("summary"),
                "sweep_score": row.get("sweep_score"),
                "alerts": row.get("alerts", []),
                "ratios": row.get("ratios", {}),
                "walls": row.get("walls", {}),
                "max_pain": row.get("max_pain"),
            }
            for row in ranked
        ],
        "focus_lines": focus_lines,
        "next_actions": next_actions,
        "reports": reports,
    }
