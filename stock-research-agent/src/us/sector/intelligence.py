"""Higher-level US sector/theme leadership intelligence.

This module sits above the 5-minute sector snapshot and the stateful flow tracker.
It deliberately keeps the language as proxy / confirmation / guard-rail rather than
claiming real institution flow from public quote data.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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


def _num(row: dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        value = _to_float(row.get(key))
        if value is not None:
            return value
    return default


def _fmt_pct(value: Any) -> str:
    number = _to_float(value)
    return "n/a" if number is None else f"{number:+.2f}%"


def _symbols_from_theme(theme: dict[str, Any], *, limit: int | None = None) -> list[str]:
    symbols: list[str] = []
    for bucket in (theme.get("leaders") or [], theme.get("constituents") or []):
        for row in bucket:
            symbol = str(row.get("symbol") or "").upper().strip()
            if symbol and symbol not in symbols:
                symbols.append(symbol)
                if limit and len(symbols) >= limit:
                    return symbols
    return symbols


def _top_leader(theme: dict[str, Any]) -> dict[str, Any]:
    leaders = theme.get("leaders") or []
    if leaders:
        return leaders[0]
    constituents = theme.get("constituents") or []
    if constituents:
        return sorted(constituents, key=lambda row: _num(row, "pct_change", "regularMarketChangePercent"), reverse=True)[0]
    return {}


def _theme_map(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(theme.get("key") or ""): theme for theme in report.get("theme_baskets", []) or [] if theme.get("key")}


def _rankable_themes(report: dict[str, Any]) -> list[dict[str, Any]]:
    return [theme for theme in report.get("theme_baskets", []) or [] if theme.get("key")]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def score_theme_persistence(theme: dict[str, Any]) -> dict[str, Any]:
    """Score whether a leading theme looks like a durable rotation or a one-off spike."""
    avg = _num(theme, "average_pct_change", "pct_change")
    breadth = _num(theme, "breadth_positive_pct", "breadth")
    relative = _num(theme, "relative_to_spy_pct", "relative_to_benchmark_pct")
    etf = _num(theme, "etf_pct_change", "etf_change_pct", "proxy_etf_pct_change")
    ret_5d = _num(theme, "return_5d_pct", "five_day_pct", "pct_change_5d")
    ret_20d = _num(theme, "return_20d_pct", "twenty_day_pct", "pct_change_20d")
    volume_change = _num(theme, "trading_value_change_pct", "relative_volume_pct", "volume_change_pct")
    breakout_count = int(_num(theme, "breakout_count", "new_high_count", default=0.0))
    flow_score = _num(theme, "flow_score", default=0.0)

    score = 0
    reasons: list[str] = []
    if avg >= 2.0:
        score += 15
        reasons.append(f"1D 평균 {_fmt_pct(avg)}")
    elif avg >= 1.0:
        score += 10
        reasons.append(f"1D 양호 {_fmt_pct(avg)}")
    elif avg > 0:
        score += 5
        reasons.append(f"1D 플러스 {_fmt_pct(avg)}")
    elif avg < -0.5:
        score -= 8
        reasons.append(f"1D 약세 {_fmt_pct(avg)}")

    if breadth >= 75:
        score += 18
        reasons.append(f"상승비율 {breadth:.0f}% 확산")
    elif breadth >= 60:
        score += 12
        reasons.append(f"상승비율 {breadth:.0f}% 양호")
    elif breadth >= 45:
        score += 7
        reasons.append(f"상승비율 {breadth:.0f}% 부분 확산")
    elif breadth > 0:
        score -= 6
        reasons.append(f"상승비율 {breadth:.0f}% 좁음")

    if relative >= 1.5:
        score += 10
        reasons.append(f"SPY대비 {_fmt_pct(relative)}")
    elif relative >= 0.5:
        score += 6
        reasons.append(f"SPY대비 우위 {_fmt_pct(relative)}")
    elif relative < -0.5:
        score -= 6
        reasons.append(f"SPY대비 열위 {_fmt_pct(relative)}")

    if etf >= 1.0:
        score += 10
        reasons.append(f"ETF 확인 {_fmt_pct(etf)}")
    elif etf > 0:
        score += 5
        reasons.append(f"ETF 플러스 {_fmt_pct(etf)}")

    if ret_5d >= 6.0:
        score += 16
        reasons.append(f"5D {_fmt_pct(ret_5d)}")
    elif ret_5d >= 3.0:
        score += 10
        reasons.append(f"5D {_fmt_pct(ret_5d)}")
    elif ret_5d > 0:
        score += 5
        reasons.append(f"5D 플러스 {_fmt_pct(ret_5d)}")
    elif ret_5d <= -2.0:
        score -= 5
        reasons.append(f"5D 약세 {_fmt_pct(ret_5d)}")

    if ret_20d >= 12.0:
        score += 16
        reasons.append(f"20D {_fmt_pct(ret_20d)}")
    elif ret_20d >= 5.0:
        score += 10
        reasons.append(f"20D {_fmt_pct(ret_20d)}")
    elif ret_20d > 0:
        score += 5
        reasons.append(f"20D 플러스 {_fmt_pct(ret_20d)}")

    if volume_change >= 50.0:
        score += 8
        reasons.append(f"거래대금 증가 {volume_change:.0f}%")
    elif volume_change >= 20.0:
        score += 5
        reasons.append(f"거래대금 증가 {volume_change:.0f}%")

    if breakout_count >= 3:
        score += 8
        reasons.append(f"신고/돌파 {breakout_count}개")
    elif breakout_count >= 1:
        score += 4
        reasons.append(f"돌파 {breakout_count}개")

    if flow_score >= 70:
        score += 8
        reasons.append(f"수급 proxy score {flow_score:.0f}")

    score = max(0, min(100, int(round(score))))
    if score >= 75:
        label = "중기 주도"
    elif score >= 60:
        label = "3~5일 지속 가능"
    elif avg >= 1.5 and breadth < 45:
        label = "단발 급등"
    elif score >= 45:
        label = "하루짜리 주도"
    else:
        label = "약함/대기"
    return {"score": score, "label": label, "reasons": reasons or ["지속성 근거 부족"]}


def score_symbol_entry(row: dict[str, Any], theme_context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Classify a leader as chaseable, pullback-only, or breakout-confirmation."""
    pct = _num(row, "pct_change", "regularMarketChangePercent")
    pct5 = _num(row, "pct_change_5m")
    vwap = _num(row, "vwap_position_pct")
    rsi = _to_float(row.get("rsi14"))
    bb = _to_float(row.get("bollinger_position_pct"))
    breadth = _to_float((theme_context or {}).get("breadth_positive_pct"))

    chase = 45
    wait = 45
    reasons: list[str] = []
    if breadth is not None and breadth >= 70:
        chase += 8
        reasons.append("테마 확산")
    if pct >= 5.0:
        chase -= 10
        wait += 12
        reasons.append("당일 급등")
    elif pct >= 1.0:
        chase += 6
        reasons.append("상대강도")
    if pct5 >= 1.0:
        chase -= 8
        wait += 12
        reasons.append("5m 급등")
    elif 0 < pct5 <= 0.7:
        chase += 4
        reasons.append("5m 완만")
    if vwap >= 1.5:
        chase -= 7
        wait += 15
        reasons.append("VWAP 이격")
    elif 0 <= vwap <= 1.0:
        chase += 6
        reasons.append("VWAP 위 안착")
    if rsi is not None and rsi >= 75:
        chase -= 12
        wait += 18
        reasons.append("RSI 과열")
    elif rsi is not None and 45 <= rsi < 70:
        chase += 4
        reasons.append("RSI 정상")
    if bb is not None and bb >= 90:
        chase -= 8
        wait += 12
        reasons.append("BB 상단 과열")
    elif bb is not None and 45 <= bb < 85:
        chase += 4
        reasons.append("BB 추세권")

    chase = max(0, min(100, int(round(chase))))
    wait = max(0, min(100, int(round(wait))))
    if wait >= chase + 10:
        judgment = "눌림 대기"
    elif chase >= wait + 15:
        judgment = "추격 가능"
    else:
        judgment = "재돌파 확인"
    return {
        "symbol": str(row.get("symbol") or ""),
        "judgment": judgment,
        "chase_score": chase,
        "wait_score": wait,
        "reason": ", ".join(reasons) or "데이터 부족",
    }


def _claims_from_social_report(social_report: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not social_report:
        return []
    for key in ("claims", "actionable_claims", "signals", "posts"):
        value = social_report.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    scan = social_report.get("threads_view_scan") if isinstance(social_report.get("threads_view_scan"), dict) else None
    if scan:
        return _claims_from_social_report(scan)
    return []


def social_confirmation_for_theme(theme: dict[str, Any], social_report: dict[str, Any] | None) -> dict[str, Any]:
    key = str(theme.get("key") or "").lower()
    name = str(theme.get("name") or "").lower()
    universe = set(_symbols_from_theme(theme))
    handles: list[str] = []
    symbols: list[str] = []
    bullish = 0
    bearish = 0
    score = 0
    for claim in _claims_from_social_report(social_report):
        claim_theme = str(claim.get("theme") or claim.get("theme_key") or "").lower()
        claim_symbols = {str(sym).upper() for sym in claim.get("symbols", []) or []}
        if not (
            claim_theme == key
            or (claim_theme and (claim_theme in name or key in claim_theme))
            or bool(universe & claim_symbols)
        ):
            continue
        handle = str(claim.get("author_handle") or claim.get("handle") or "").lstrip("@")
        if handle and handle not in handles:
            handles.append(handle)
        for symbol in sorted(universe & claim_symbols):
            if symbol not in symbols:
                symbols.append(symbol)
        direction = str(claim.get("direction") or claim.get("stance") or "").lower()
        relevance = int(_num(claim, "relevance_score", "confidence_score", default=50.0))
        if "bear" in direction or "하락" in direction:
            bearish += 1
            score -= max(10, relevance // 4)
        elif "bull" in direction or "상승" in direction:
            bullish += 1
            score += max(15, relevance // 3)
        else:
            score += max(5, relevance // 8)
    score = max(0, min(100, score))
    confirmed = bullish > bearish and (bool(handles) or bool(symbols))
    return {
        "confirmed": confirmed,
        "score": score,
        "handles": handles[:5],
        "symbols": symbols[:8],
        "bullish_count": bullish,
        "bearish_count": bearish,
    }


def _flow_signals_for_theme(theme_key: str, report: dict[str, Any], flow_events: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    for event in flow_events or []:
        if str(event.get("theme_key") or "") == theme_key:
            signals.append(event)
    for item in ((report.get("flow_proxies") or {}).get("candidates") or []):
        if str(item.get("theme_key") or "") == theme_key:
            signals.append({"event_type": "flow_proxy", "title": "수급 proxy", "summary": item.get("summary") or "거래대금/VWAP/상대강도 기반 proxy"})
    return signals


def build_macro_pressure_filter(report: dict[str, Any]) -> dict[str, Any]:
    macro = dict(report.get("macro_context") or report.get("macro") or {})
    benchmark = report.get("benchmark") or report.get("benchmarks") or {}
    lines: list[str] = []
    risk_flags: list[str] = []
    us10y = _to_float(macro.get("us10y_5m_pct") or macro.get("us10y_change_pct") or macro.get("rates_5m_pct"))
    dxy = _to_float(macro.get("dxy_5m_pct") or macro.get("dxy_change_pct"))
    wti = _to_float(macro.get("wti_5m_pct") or benchmark.get("WTI"))
    vix = _to_float(macro.get("vix_5m_pct") or benchmark.get("VIX"))
    copper = _to_float(macro.get("copper_5d_pct") or macro.get("copper_change_pct"))
    if us10y is not None and us10y >= 1.0:
        risk_flags.append("rates_up")
        lines.append(f"금리 급등 {us10y:+.2f}%: 성장/소형/코인 추격 경계")
    if dxy is not None and dxy >= 0.5:
        risk_flags.append("dollar_up")
        lines.append(f"달러 강세 {dxy:+.2f}%: 해외매출/고베타 부담")
    if vix is not None and vix >= 2.0:
        risk_flags.append("vix_up")
        lines.append(f"VIX 상승 {vix:+.2f}%: 강한 테마도 눌림 우선")
    if wti is not None and wti >= 1.5:
        risk_flags.append("oil_up")
        lines.append(f"WTI 상승 {wti:+.2f}%: 에너지 강세와 인플레 리스크 동시 확인")
    if copper is not None and copper >= 2.0:
        lines.append(f"구리/산업금속 강세 {copper:+.2f}%: 소재·전력 인프라 확인")
    return {"risk_flags": risk_flags, "lines": lines, "macro": macro, "benchmark": benchmark}


def _build_guard(themes: list[dict[str, Any]], watchlist: list[str] | None, portfolio: list[str] | None) -> dict[str, Any]:
    watch = {str(sym).upper() for sym in watchlist or []}
    port = {str(sym).upper() for sym in portfolio or []}
    theme_symbols: list[str] = []
    for theme in themes[:3]:
        for symbol in _symbols_from_theme(theme):
            if symbol not in theme_symbols:
                theme_symbols.append(symbol)
    watch_hits = [sym for sym in theme_symbols if sym in watch]
    portfolio_hits = [sym for sym in theme_symbols if sym in port]
    lines: list[str] = []
    if watch_hits:
        lines.append("관심종목 주도테마 진입: " + ", ".join(watch_hits[:8]))
    if portfolio_hits:
        lines.append("보유종목 주도테마 노출: " + ", ".join(portfolio_hits[:8]))
    if not lines:
        lines.append("관심/보유 종목 직접 히트 없음")
    return {"watchlist_hits": watch_hits, "portfolio_hits": portfolio_hits, "lines": lines}


def _tier_from_theme(theme: dict[str, Any], report: dict[str, Any], flow_events: list[dict[str, Any]] | None, social_report: dict[str, Any] | None) -> dict[str, Any]:
    persistence = score_theme_persistence(theme)
    social = social_confirmation_for_theme(theme, social_report)
    flow_signals = _flow_signals_for_theme(str(theme.get("key") or ""), report, flow_events)
    leader = _top_leader(theme)
    entry = score_symbol_entry(leader, theme) if leader else {"judgment": "데이터 부족", "chase_score": 0, "wait_score": 0, "reason": "leader 없음"}
    combined = persistence["score"] + min(12, len(flow_signals) * 6) + (8 if social.get("confirmed") else 0)
    return {
        "theme_key": str(theme.get("key") or ""),
        "theme_name": theme.get("name") or theme.get("key"),
        "average_pct_change": _to_float(theme.get("average_pct_change")),
        "breadth_positive_pct": _to_float(theme.get("breadth_positive_pct")),
        "leaders": _symbols_from_theme(theme, limit=5),
        "top_leader": leader,
        "persistence": persistence,
        "flow_signals": flow_signals,
        "social_confirmation": social,
        "entry_signal": entry,
        "combined_score": max(0, min(100, int(round(combined)))),
    }


def build_sector_intelligence_report(
    sector_report: dict[str, Any],
    *,
    flow_events: list[dict[str, Any]] | None = None,
    social_report: dict[str, Any] | None = None,
    watchlist: list[str] | None = None,
    portfolio: list[str] | None = None,
) -> dict[str, Any]:
    tiers = [_tier_from_theme(theme, sector_report, flow_events, social_report) for theme in _rankable_themes(sector_report)]
    tiers.sort(key=lambda item: (item["combined_score"], item.get("average_pct_change") or -999), reverse=True)
    top = tiers[0] if tiers else {}
    top_themes = []
    theme_by_key = _theme_map(sector_report)
    for tier in tiers[:3]:
        theme = theme_by_key.get(tier["theme_key"])
        if theme:
            top_themes.append(theme)
    guard = _build_guard(top_themes, watchlist, portfolio)
    macro = build_macro_pressure_filter(sector_report)

    flow_line = "수급 proxy: 신규 이벤트 없음"
    if top and top.get("flow_signals"):
        sig = top["flow_signals"][0]
        flow_line = f"수급 proxy: {sig.get('title') or '감지'} / {sig.get('summary') or '거래대금·VWAP·상대강도 기반'}"
    social_line = "Threads 확인: 신호 없음"
    if top and (top.get("social_confirmation") or {}).get("confirmed"):
        handles = ", ".join("@" + h for h in top["social_confirmation"].get("handles", [])[:3])
        social_line = f"Threads 확인: {handles} 쪽 같은 테마 확인"
    if top:
        persistence = top["persistence"]
        summary = f"주도섹터 intelligence: {top['theme_name']} / {persistence['label']} {persistence['score']}점"
        action = top.get("entry_signal", {})
        action_line = f"매매 관점: {top.get('leaders', [''])[0] if top.get('leaders') else top['theme_name']} {action.get('judgment', '확인')} / 추격{action.get('chase_score', 0)}/대기{action.get('wait_score', 0)}"
        leader_line = f"주도 후보: {top['theme_name']} 평균 {_fmt_pct(top.get('average_pct_change'))}, 상승비율 {top.get('breadth_positive_pct') or 0:.0f}%, 대장 {', '.join(top.get('leaders', [])[:3])}"
    else:
        summary = "주도섹터 intelligence: 분석 가능한 테마 없음"
        action_line = "매매 관점: 데이터 확보 후 판단"
        leader_line = "주도 후보: n/a"
    focus_lines = [leader_line, flow_line, social_line]
    focus_lines.extend(macro["lines"][:3])
    focus_lines.extend(f"Guard: {line}" for line in guard["lines"][:2])
    focus_lines.append(action_line)
    next_actions = [
        "상위 테마 대장주 VWAP/5분 눌림 확인",
        "수급 proxy 이벤트가 신규/가속인지, 단순 급등인지 분리",
        "Threads 신호는 가격·ETF·상승비율 확인 후만 conviction 가산",
    ]
    if macro["risk_flags"]:
        next_actions.insert(0, "금리/VIX/WTI 리스크가 켜지면 강한 테마도 추격보다 눌림 대기")
    return {
        "mode": "sector_intelligence",
        "collected_at": sector_report.get("collected_at") or _now_iso(),
        "summary": summary,
        "leadership_tiers": tiers,
        "flow_events": flow_events or [],
        "macro_filter": macro,
        "guard": guard,
        "focus_lines": focus_lines,
        "next_actions": next_actions,
    }


def build_premarket_plan(
    sector_report: dict[str, Any],
    *,
    previous_report: dict[str, Any] | None = None,
    social_report: dict[str, Any] | None = None,
    watchlist: list[str] | None = None,
) -> dict[str, Any]:
    intel = build_sector_intelligence_report(sector_report, social_report=social_report, watchlist=watchlist)
    top = intel["leadership_tiers"][0] if intel["leadership_tiers"] else {}
    trigger_symbols = list(top.get("leaders") or [])[:5]
    for symbol in watchlist or []:
        sym = str(symbol).upper()
        if sym in (top.get("leaders") or []) and sym not in trigger_symbols:
            trigger_symbols.append(sym)
    avg = _to_float(top.get("average_pct_change")) or 0.0
    leader = top.get("top_leader") or {}
    leader_pct = _num(leader, "pct_change")
    chase_warnings: list[str] = []
    if avg >= 2.5 or leader_pct >= 4.0:
        chase_warnings.append(f"갭상 추격 금지: {top.get('theme_name', '상위 테마')} 평균 {_fmt_pct(avg)}, 대장 {_fmt_pct(leader_pct)}")
    elif top:
        chase_warnings.append("장초 5분 확산 확인 전 추격 금지")
    pullback_plan = [f"{sym}: VWAP/5분 눌림 또는 전일고 재돌파 확인" for sym in trigger_symbols[:5]] or ["상위 테마 대장주 VWAP 눌림 확인"]
    focus_lines = [
        f"프리장 주도 후보: {top.get('theme_name', 'n/a')} / {top.get('persistence', {}).get('label', 'n/a')}",
        "트리거: " + ", ".join(trigger_symbols[:5]) if trigger_symbols else "트리거: n/a",
        *chase_warnings[:2],
    ]
    return {
        "mode": "premarket_plan",
        "summary": f"프리장 플랜: {top.get('theme_name', 'n/a')} 중심, 추격보다 눌림/재돌파 확인",
        "leadership_tiers": intel["leadership_tiers"],
        "trigger_symbols": trigger_symbols,
        "chase_warnings": chase_warnings,
        "pullback_plan": pullback_plan,
        "focus_lines": focus_lines,
        "next_actions": ["개장 5~15분 상승비율 유지 확인", "갭상 대장은 VWAP 이탈 시 추격 금지", "전일 주도 테마 지속 여부 확인"],
    }


def build_closing_review(open_report: dict[str, Any], close_report: dict[str, Any]) -> dict[str, Any]:
    open_intel = build_sector_intelligence_report(open_report)
    close_intel = build_sector_intelligence_report(close_report)
    open_leader = open_intel["leadership_tiers"][0] if open_intel["leadership_tiers"] else {}
    close_leader = close_intel["leadership_tiers"][0] if close_intel["leadership_tiers"] else {}
    close_by_key = {tier["theme_key"]: tier for tier in close_intel["leadership_tiers"]}
    fakeouts: list[dict[str, Any]] = []
    for tier in open_intel["leadership_tiers"][:3]:
        close_tier = close_by_key.get(tier["theme_key"])
        open_avg = _to_float(tier.get("average_pct_change")) or 0.0
        close_avg = _to_float((close_tier or {}).get("average_pct_change")) or -999.0
        if open_avg >= 1.5 and close_avg < 0.5:
            fakeouts.append({"theme_key": tier["theme_key"], "theme_name": tier["theme_name"], "open_avg": open_avg, "close_avg": close_avg})
    next_watch = [
        {"theme_key": tier["theme_key"], "theme_name": tier["theme_name"], "reason": tier["persistence"]["label"]}
        for tier in close_intel["leadership_tiers"][:3]
        if (tier.get("average_pct_change") or 0) >= 1.0 and (tier.get("breadth_positive_pct") or 0) >= 60
    ]
    follow_through = bool(open_leader and close_leader and open_leader.get("theme_key") == close_leader.get("theme_key") and not fakeouts)
    focus_lines = [
        f"마감 주도: {close_leader.get('theme_name', 'n/a')}",
        f"장초→마감: {open_leader.get('theme_name', 'n/a')} → {close_leader.get('theme_name', 'n/a')}",
    ]
    if fakeouts:
        focus_lines.append("속임수: " + ", ".join(item["theme_name"] for item in fakeouts[:3]))
    if next_watch:
        focus_lines.append("내일 관찰: " + ", ".join(item["theme_name"] for item in next_watch[:3]))
    return {
        "mode": "closing_review",
        "summary": f"마감 복기: {close_leader.get('theme_name', 'n/a')} 마감 주도 / {'지속' if follow_through else '로테이션'}",
        "opening_leader": open_leader,
        "closing_leader": close_leader,
        "follow_through": follow_through,
        "fakeouts": fakeouts,
        "next_session_watch": next_watch,
        "focus_lines": focus_lines,
        "next_actions": ["마감 주도 테마 대장주 종가 위치 확인", "장초 속임수 테마는 다음날 갭상 추격 금지", "지속 테마만 눌림 후보로 유지"],
    }


def record_leadership_outcome(
    log_path: str | Path,
    alert_report: dict[str, Any],
    later_sector_report: dict[str, Any],
    *,
    horizon_label: str,
) -> dict[str, Any]:
    tiers = alert_report.get("leadership_tiers") or []
    if not tiers:
        raise ValueError("alert_report has no leadership_tiers")
    top = tiers[0]
    key = str(top.get("theme_key") or "")
    later_theme = _theme_map(later_sector_report).get(key, {})
    alert_avg = _to_float(top.get("average_pct_change")) or 0.0
    later_avg = _to_float(later_theme.get("average_pct_change")) or 0.0
    entry = {
        "recorded_at": _now_iso(),
        "alert_collected_at": alert_report.get("collected_at"),
        "later_collected_at": later_sector_report.get("collected_at"),
        "horizon_label": horizon_label,
        "theme_key": key,
        "theme_name": top.get("theme_name"),
        "alert_theme_return": alert_avg,
        "later_theme_return": later_avg,
        "realized_theme_return_delta": round(later_avg - alert_avg, 4),
        "persistence_label": (top.get("persistence") or {}).get("label"),
        "persistence_score": (top.get("persistence") or {}).get("score"),
    }
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    return entry


def format_sector_intelligence_text(report: dict[str, Any]) -> str:
    lines = [report.get("summary") or "sector intelligence"]
    for line in report.get("focus_lines", [])[:8]:
        lines.append(f"- {line}")
    actions = report.get("next_actions") or []
    if actions:
        lines.append("다음 액션: " + " / ".join(actions[:3]))
    return "\n".join(lines)
