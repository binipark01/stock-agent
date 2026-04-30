from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any

try:
    from .sector_theme_config import (
        BENCHMARK_SYMBOLS,
        CORE_SECTOR_ETFS,
        DEFAULT_SECTOR_STRENGTH_SYMBOLS,
        REGIME_SYMBOLS,
        THEME_ETFS,
        USER_SUB_THEME_BASKETS,
        USER_THEME_BASKETS,
    )
except ImportError:  # direct script execution
    from sector_theme_config import (
        BENCHMARK_SYMBOLS,
        CORE_SECTOR_ETFS,
        DEFAULT_SECTOR_STRENGTH_SYMBOLS,
        REGIME_SYMBOLS,
        THEME_ETFS,
        USER_SUB_THEME_BASKETS,
        USER_THEME_BASKETS,
    )


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


def _pct_change(quote: dict[str, Any]) -> float | None:
    direct = _to_float(quote.get("pct_change") or quote.get("change_pct") or quote.get("regularMarketChangePercent"))
    if direct is not None:
        return round(direct, 2)
    price = _to_float(quote.get("price") or quote.get("last") or quote.get("last_price") or quote.get("regularMarketPrice"))
    previous = _to_float(quote.get("previous_close") or quote.get("previousClose") or quote.get("regularMarketPreviousClose"))
    if price is None or previous in (None, 0):
        return None
    return round(((price - float(previous)) / float(previous)) * 100, 2)


def _normalize_quote(symbol: str, raw: Any) -> dict[str, Any]:
    raw = raw or {}
    if isinstance(raw, dict) and isinstance(raw.get("quote"), dict):
        quote = dict(raw.get("quote") or {})
        quote.setdefault("source", raw.get("source"))
        quote.setdefault("timestamp", raw.get("collected_at"))
    elif isinstance(raw, dict):
        quote = dict(raw)
    else:
        quote = {}
    quote["symbol"] = str(quote.get("symbol") or symbol).upper()
    quote["pct_change"] = _pct_change(quote)
    return quote


def _fmt_pct(value: Any) -> str:
    numeric = _to_float(value)
    return "n/a" if numeric is None else f"{numeric:+.2f}%"


def _fmt_price(value: Any) -> str:
    numeric = _to_float(value)
    return "n/a" if numeric is None else f"{numeric:g}"


def _korean_regime_label(label: str) -> str:
    return {"risk_off": "리스크오프", "risk_on": "리스크온", "neutral": "중립"}.get(label, label)


def _classify_regime(quotes: dict[str, dict[str, Any]]) -> dict[str, Any]:
    signals: list[str] = []
    risk_off_score = 0
    risk_on_score = 0

    vix = quotes.get("^VIX", {})
    vix_price = _to_float(vix.get("price"))
    vix_pct = _pct_change(vix)
    if vix_price is not None:
        if vix_price >= 25:
            risk_off_score += 3
            signals.append(f"VIX {vix_price:g} 고위험권")
        elif vix_price >= 20:
            risk_off_score += 2
            signals.append(f"VIX {vix_price:g} 20 상회")
        elif vix_price <= 16:
            risk_on_score += 1
            signals.append(f"VIX {vix_price:g} 안정권")
    if vix_pct is not None and vix_pct >= 8:
        risk_off_score += 2
        signals.append(f"VIX 급등 {_fmt_pct(vix_pct)}")
    elif vix_pct is not None and vix_pct <= -5:
        risk_on_score += 1
        signals.append(f"VIX 하락 {_fmt_pct(vix_pct)}")

    for symbol, name in (("CL=F", "WTI"), ("BZ=F", "Brent")):
        quote = quotes.get(symbol, {})
        pct = _pct_change(quote)
        if pct is not None and pct >= 2:
            risk_off_score += 1
            signals.append(f"{name}/오일 상승 {_fmt_pct(pct)}")
        elif pct is not None and pct <= -2:
            risk_on_score += 1
            signals.append(f"{name}/오일 하락 {_fmt_pct(pct)}")

    tnx_pct = _pct_change(quotes.get("^TNX", {}))
    if tnx_pct is not None and tnx_pct >= 1:
        risk_off_score += 1
        signals.append(f"10Y 금리 상승 {_fmt_pct(tnx_pct)}")
    elif tnx_pct is not None and tnx_pct <= -1:
        risk_on_score += 1
        signals.append(f"10Y 금리 하락 {_fmt_pct(tnx_pct)}")

    dxy_pct = _pct_change(quotes.get("DX-Y.NYB", {}))
    if dxy_pct is not None and dxy_pct >= 0.8:
        risk_off_score += 1
        signals.append(f"DXY 강세 {_fmt_pct(dxy_pct)}")
    elif dxy_pct is not None and dxy_pct <= -0.8:
        risk_on_score += 1
        signals.append(f"DXY 약세 {_fmt_pct(dxy_pct)}")

    qqq_pct = _pct_change(quotes.get("QQQ", {}))
    spy_pct = _pct_change(quotes.get("SPY", {}))
    if qqq_pct is not None and spy_pct is not None:
        if qqq_pct < spy_pct - 0.4:
            risk_off_score += 1
            signals.append(f"QQQ가 SPY 대비 약세 {qqq_pct - spy_pct:+.2f}%p")
        elif qqq_pct > spy_pct + 0.4 and risk_off_score <= 1:
            risk_on_score += 1
            signals.append(f"QQQ가 SPY 대비 강세 {qqq_pct - spy_pct:+.2f}%p")

    if risk_off_score >= 3:
        label = "risk_off"
    elif risk_on_score > risk_off_score and risk_on_score >= 2:
        label = "risk_on"
    else:
        label = "neutral"
    if not signals:
        signals.append("VIX/오일/금리/DXY 뚜렷한 충격 없음")
    return {"label": label, "korean_label": _korean_regime_label(label), "risk_off_score": risk_off_score, "risk_on_score": risk_on_score, "signals": signals}


def _rank_sector_quotes(quotes: dict[str, dict[str, Any]], spy_pct: float, qqq_pct: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    names = {**CORE_SECTOR_ETFS, **THEME_ETFS}
    for symbol, name in names.items():
        quote = quotes.get(symbol)
        if not quote:
            continue
        pct = _pct_change(quote)
        if pct is None:
            continue
        relative_to_spy = round(pct - spy_pct, 2)
        relative_to_qqq = round(pct - qqq_pct, 2)
        score = round(pct + relative_to_spy + (relative_to_qqq * 0.5), 3)
        rows.append(
            {
                "symbol": symbol,
                "name": name,
                "pct_change": round(pct, 2),
                "relative_to_spy_pct": relative_to_spy,
                "relative_to_qqq_pct": relative_to_qqq,
                "strength_score": score,
                "price": quote.get("price"),
                "source": quote.get("source"),
                "timestamp": quote.get("timestamp") or quote.get("collected_at"),
            }
        )
    return sorted(rows, key=lambda row: row["strength_score"], reverse=True)


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2


def _rank_theme_baskets(quotes: dict[str, dict[str, Any]], spy_pct: float, qqq_pct: float) -> list[dict[str, Any]]:
    baskets: list[dict[str, Any]] = []
    for key, basket in USER_THEME_BASKETS.items():
        symbols = tuple(str(symbol).upper() for symbol in basket.get("symbols", ()))
        excluded = {str(symbol).upper() for symbol in basket.get("excluded_from_score", ())}
        constituents: list[dict[str, Any]] = []
        score_rows: list[dict[str, Any]] = []
        for symbol in symbols:
            quote = quotes.get(symbol)
            if not quote:
                continue
            pct = _pct_change(quote)
            if pct is None:
                continue
            row = {
                "symbol": symbol,
                "pct_change": round(pct, 2),
                "relative_to_spy_pct": round(pct - spy_pct, 2),
                "relative_to_qqq_pct": round(pct - qqq_pct, 2),
                "price": quote.get("price"),
                "source": quote.get("source"),
                "timestamp": quote.get("timestamp") or quote.get("collected_at"),
                "score_eligible": symbol not in excluded,
            }
            constituents.append(row)
            if row["score_eligible"]:
                score_rows.append(row)
        if not score_rows:
            continue
        pct_values = [float(row["pct_change"]) for row in score_rows]
        avg_pct = sum(pct_values) / len(pct_values)
        median_pct = _median(pct_values)
        breadth_positive_pct = (sum(1 for value in pct_values if value > 0) / len(pct_values)) * 100
        avg_relative_to_spy = avg_pct - spy_pct
        avg_relative_to_qqq = avg_pct - qqq_pct
        breadth_bonus = (breadth_positive_pct - 50.0) / 25.0
        strength_score = avg_pct + avg_relative_to_spy + (avg_relative_to_qqq * 0.5) + breadth_bonus
        leaders = sorted(score_rows, key=lambda row: row["pct_change"], reverse=True)[:3]
        laggards = sorted(score_rows, key=lambda row: row["pct_change"])[:3]
        baskets.append(
            {
                "key": key,
                "name": str(basket.get("name") or key),
                "symbols": list(symbols),
                "covered_symbols": [row["symbol"] for row in constituents],
                "excluded_symbols": sorted(symbol for symbol in excluded if symbol in {row["symbol"] for row in constituents}),
                "constituents": sorted(constituents, key=lambda row: row["pct_change"], reverse=True),
                "score_symbols": [row["symbol"] for row in score_rows],
                "average_pct_change": round(avg_pct, 2),
                "median_pct_change": round(float(median_pct), 2) if median_pct is not None else None,
                "breadth_positive_pct": round(breadth_positive_pct, 1),
                "relative_to_spy_pct": round(avg_relative_to_spy, 2),
                "relative_to_qqq_pct": round(avg_relative_to_qqq, 2),
                "strength_score": round(strength_score, 3),
                "leaders": leaders,
                "laggards": laggards,
            }
        )
    return sorted(baskets, key=lambda row: row["strength_score"], reverse=True)


def _rank_sub_theme_baskets(quotes: dict[str, dict[str, Any]], spy_pct: float, qqq_pct: float) -> list[dict[str, Any]]:
    baskets: list[dict[str, Any]] = []
    parent_names = {key: str(value.get("name") or key) for key, value in USER_THEME_BASKETS.items()}
    for key, basket in USER_SUB_THEME_BASKETS.items():
        symbols = tuple(str(symbol).upper() for symbol in basket.get("symbols", ()))
        excluded = {str(symbol).upper() for symbol in basket.get("excluded_from_score", ())}
        parent_key = str(basket.get("parent") or "")
        parent_name = parent_names.get(parent_key, parent_key or "테마")
        constituents: list[dict[str, Any]] = []
        score_rows: list[dict[str, Any]] = []
        for symbol in symbols:
            quote = quotes.get(symbol)
            if not quote:
                continue
            pct = _pct_change(quote)
            if pct is None:
                continue
            row = {
                "symbol": symbol,
                "pct_change": round(pct, 2),
                "relative_to_spy_pct": round(pct - spy_pct, 2),
                "relative_to_qqq_pct": round(pct - qqq_pct, 2),
                "price": quote.get("price"),
                "source": quote.get("source"),
                "timestamp": quote.get("timestamp") or quote.get("collected_at"),
                "score_eligible": symbol not in excluded,
            }
            constituents.append(row)
            if row["score_eligible"]:
                score_rows.append(row)
        if not score_rows:
            continue
        pct_values = [float(row["pct_change"]) for row in score_rows]
        avg_pct = sum(pct_values) / len(pct_values)
        median_pct = _median(pct_values)
        breadth_positive_pct = (sum(1 for value in pct_values if value > 0) / len(pct_values)) * 100
        avg_relative_to_spy = avg_pct - spy_pct
        avg_relative_to_qqq = avg_pct - qqq_pct
        breadth_bonus = (breadth_positive_pct - 50.0) / 25.0
        strength_score = avg_pct + avg_relative_to_spy + (avg_relative_to_qqq * 0.5) + breadth_bonus
        leaders = sorted(score_rows, key=lambda row: row["pct_change"], reverse=True)[:3]
        laggards = sorted(score_rows, key=lambda row: row["pct_change"])[:3]
        baskets.append(
            {
                "key": key,
                "name": str(basket.get("name") or key),
                "parent_key": parent_key,
                "parent_name": parent_name,
                "symbols": list(symbols),
                "covered_symbols": [row["symbol"] for row in constituents],
                "excluded_symbols": sorted(symbol for symbol in excluded if symbol in {row["symbol"] for row in constituents}),
                "constituents": sorted(constituents, key=lambda row: row["pct_change"], reverse=True),
                "score_symbols": [row["symbol"] for row in score_rows],
                "average_pct_change": round(avg_pct, 2),
                "median_pct_change": round(float(median_pct), 2) if median_pct is not None else None,
                "breadth_positive_pct": round(breadth_positive_pct, 1),
                "relative_to_spy_pct": round(avg_relative_to_spy, 2),
                "relative_to_qqq_pct": round(avg_relative_to_qqq, 2),
                "strength_score": round(strength_score, 3),
                "leaders": leaders,
                "laggards": laggards,
            }
        )
    return sorted(baskets, key=lambda row: row["strength_score"], reverse=True)


def _line_for(prefix: str, rows: list[dict[str, Any]]) -> str:
    if not rows:
        return f"{prefix}: 데이터 부족"
    parts = [
        f"{row['name']} {row['symbol']} {_fmt_pct(row['pct_change'])} / SPY 대비 {_fmt_pct(row['relative_to_spy_pct'])}"
        for row in rows[:3]
    ]
    return f"{prefix}: " + " | ".join(parts)


def _theme_line_for(prefix: str, rows: list[dict[str, Any]]) -> str:
    if not rows:
        return f"{prefix}: 데이터 부족"
    parts = []
    for row in rows[:3]:
        leaders = ", ".join(f"{leader['symbol']} {_fmt_pct(leader['pct_change'])}" for leader in row.get("leaders", [])[:2])
        parts.append(
            f"{row['name']} 평균 {_fmt_pct(row['average_pct_change'])} / 상승비율 {row['breadth_positive_pct']:.1f}% / 주도 {leaders or 'n/a'}"
        )
    return f"{prefix}: " + " | ".join(parts)


def _sub_theme_line_for(prefix: str, rows: list[dict[str, Any]]) -> str:
    if not rows:
        return f"{prefix}: 데이터 부족"
    parts = []
    for row in rows[:3]:
        leaders = ", ".join(f"{leader['symbol']} {_fmt_pct(leader['pct_change'])}" for leader in row.get("leaders", [])[:2])
        parts.append(
            f"{row['parent_name']} > {row['name']} 평균 {_fmt_pct(row['average_pct_change'])} / 상승비율 {row['breadth_positive_pct']:.1f}% / 주도 {leaders or 'n/a'}"
        )
    return f"{prefix}: " + " | ".join(parts)


def _build_rotation_alerts(strong_sub_themes: list[dict[str, Any]], weak_sub_themes: list[dict[str, Any]], limit: int = 2) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    used_pairs: set[tuple[str, str, str]] = set()
    for strong in strong_sub_themes:
        strong_parent = str(strong.get("parent_key") or "")
        if not strong_parent:
            continue
        strong_avg = _to_float(strong.get("average_pct_change"))
        if strong_avg is None or strong_avg <= 0:
            continue
        for weak in weak_sub_themes:
            weak_parent = str(weak.get("parent_key") or "")
            if weak_parent != strong_parent or weak.get("key") == strong.get("key"):
                continue
            weak_avg = _to_float(weak.get("average_pct_change"))
            if weak_avg is None or weak_avg >= 0:
                continue
            pair = (strong_parent, str(strong.get("key") or ""), str(weak.get("key") or ""))
            if pair in used_pairs:
                continue
            used_pairs.add(pair)
            into_leaders = [row for row in strong.get("leaders", []) if isinstance(row, dict)][:2]
            out_rows = [row for row in weak.get("leaders", []) if isinstance(row, dict)][:2]
            score_gap = (_to_float(strong.get("strength_score")) or 0.0) - (_to_float(weak.get("strength_score")) or 0.0)
            alerts.append(
                {
                    "parent_key": strong_parent,
                    "parent_name": strong.get("parent_name"),
                    "into_sub_theme_key": strong.get("key"),
                    "into_sub_theme": strong.get("name"),
                    "out_of_sub_theme_key": weak.get("key"),
                    "out_of_sub_theme": weak.get("name"),
                    "into_average_pct_change": round(float(strong_avg), 2),
                    "out_of_average_pct_change": round(float(weak_avg), 2),
                    "score_gap": round(score_gap, 3),
                    "into_leaders": into_leaders,
                    "out_of_examples": out_rows,
                    "interpretation": f"{strong.get('parent_name')} 내부 {strong.get('name')}로 자금 이동 / {weak.get('name')} 약세",
                }
            )
            break
    return sorted(alerts, key=lambda row: row["score_gap"], reverse=True)[:limit]


def _rotation_line(alerts: list[dict[str, Any]]) -> str:
    if not alerts:
        return "로테이션 해석: 뚜렷한 세부테마 내부 로테이션 없음"
    parts = []
    for alert in alerts[:2]:
        into = ", ".join(f"{row['symbol']} {_fmt_pct(row['pct_change'])}" for row in alert.get("into_leaders", [])[:2])
        out_of = ", ".join(f"{row['symbol']} {_fmt_pct(row['pct_change'])}" for row in alert.get("out_of_examples", [])[:2])
        parts.append(
            f"{alert['parent_name']} 내부 {alert['into_sub_theme']}로 자금 이동 / {alert['out_of_sub_theme']} 약세"
            f"(강세 {into or 'n/a'} vs 약세 {out_of or 'n/a'})"
        )
    return "로테이션 해석: " + " | ".join(parts)


def _rank_watchlist_movers(theme_baskets: list[dict[str, Any]], sub_theme_baskets: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    movers: list[dict[str, Any]] = []
    symbol_sub_themes: dict[str, dict[str, Any]] = {}
    for sub in sub_theme_baskets or []:
        for row in sub.get("constituents", []) or []:
            if not isinstance(row, dict) or not row.get("score_eligible", True):
                continue
            symbol = str(row.get("symbol") or "")
            if not symbol:
                continue
            previous = symbol_sub_themes.get(symbol)
            if previous is None or float(sub.get("strength_score") or 0) > float(previous.get("strength_score") or 0):
                symbol_sub_themes[symbol] = {
                    "key": sub.get("key"),
                    "name": sub.get("name"),
                    "parent_key": sub.get("parent_key"),
                    "parent_name": sub.get("parent_name"),
                    "strength_score": sub.get("strength_score"),
                }
    for basket in theme_baskets:
        theme_name = str(basket.get("name") or basket.get("key") or "테마")
        theme_key = str(basket.get("key") or theme_name)
        for row in basket.get("constituents", []) or []:
            if not isinstance(row, dict) or not row.get("score_eligible", True):
                continue
            pct = _to_float(row.get("pct_change"))
            if pct is None:
                continue
            relative_to_spy = _to_float(row.get("relative_to_spy_pct")) or 0.0
            relative_to_qqq = _to_float(row.get("relative_to_qqq_pct")) or 0.0
            mover_score = abs(pct) + max(relative_to_spy, 0.0) + max(relative_to_qqq, 0.0) * 0.5
            direction = "강세" if pct >= 0 else "약세"
            symbol = str(row.get("symbol") or "")
            sub_theme = symbol_sub_themes.get(symbol, {})
            sub_theme_name = str(sub_theme.get("name") or "")
            reason = f"{theme_name}>{sub_theme_name} 내부 {direction}" if sub_theme_name else f"{theme_name} 내부 {direction}"
            movers.append(
                {
                    "symbol": symbol,
                    "theme": theme_name,
                    "theme_key": theme_key,
                    "sub_theme": sub_theme_name or None,
                    "sub_theme_key": sub_theme.get("key"),
                    "pct_change": round(pct, 2),
                    "relative_to_spy_pct": round(relative_to_spy, 2),
                    "relative_to_qqq_pct": round(relative_to_qqq, 2),
                    "mover_score": round(mover_score, 3),
                    "direction": direction,
                    "reason": reason,
                    "price": row.get("price"),
                    "source": row.get("source"),
                    "timestamp": row.get("timestamp"),
                }
            )
    return sorted(movers, key=lambda row: row["mover_score"], reverse=True)


def _movers_line(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "오늘 먼저 볼 종목: 데이터 부족"
    parts = []
    for row in rows[:5]:
        scope = row.get("sub_theme") or row.get("theme")
        parts.append(f"{row['symbol']} {_fmt_pct(row['pct_change'])}({scope})")
    return "오늘 먼저 볼 종목: " + " | ".join(parts)


def _etf_context_line(strong: list[dict[str, Any]], weak: list[dict[str, Any]]) -> str:
    strong_part = "데이터 부족"
    weak_part = "데이터 부족"
    if strong:
        row = strong[0]
        strong_part = f"강세 {row['name']} {row['symbol']} {_fmt_pct(row['pct_change'])}"
    if weak:
        row = weak[0]
        weak_part = f"약세 {row['name']} {row['symbol']} {_fmt_pct(row['pct_change'])}"
    return f"ETF 시장 참고: {strong_part} / {weak_part}"


def build_sector_strength_report(quotes: dict[str, Any], collected_at: str | None = None, top_n: int = 3) -> dict[str, Any]:
    normalized = {str(symbol).upper(): _normalize_quote(str(symbol), raw) for symbol, raw in (quotes or {}).items()}
    collected_at = collected_at or next((str(q.get("timestamp") or q.get("collected_at")) for q in normalized.values() if q.get("timestamp") or q.get("collected_at")), None) or datetime.now(timezone.utc).isoformat()

    spy_pct = _pct_change(normalized.get("SPY", {}))
    qqq_pct = _pct_change(normalized.get("QQQ", {}))
    if spy_pct is None or qqq_pct is None:
        return {
            "available": False,
            "summary": "섹터 강약: SPY/QQQ 기준 데이터가 부족합니다",
            "collected_at": collected_at,
            "focus_lines": ["섹터 강약: SPY/QQQ 기준 데이터가 부족합니다"],
            "next_actions": ["SPY/QQQ와 주요 섹터 ETF quote가 들어오는지 먼저 확인"],
            "strong": [],
            "weak": [],
            "regime": {"label": "unavailable", "korean_label": "데이터 부족", "signals": []},
            "quotes": normalized,
        }

    ranked = _rank_sector_quotes(normalized, spy_pct, qqq_pct)
    theme_baskets = _rank_theme_baskets(normalized, spy_pct, qqq_pct)
    sub_theme_baskets = _rank_sub_theme_baskets(normalized, spy_pct, qqq_pct)
    watchlist_movers = _rank_watchlist_movers(theme_baskets, sub_theme_baskets)
    strong = ranked[:top_n]
    weak = sorted(ranked, key=lambda row: row["strength_score"])[:top_n]
    strong_themes = theme_baskets[:top_n]
    weak_themes = sorted(theme_baskets, key=lambda row: row["strength_score"])[:top_n]
    strong_sub_themes = sub_theme_baskets[:top_n]
    weak_sub_themes = sorted(sub_theme_baskets, key=lambda row: row["strength_score"])[:top_n]
    rotation_alerts = _build_rotation_alerts(strong_sub_themes, weak_sub_themes)
    regime = _classify_regime(normalized)
    regime_text = regime["korean_label"]
    leader = strong_themes[0]["name"] if strong_themes else (strong[0]["symbol"] if strong else "n/a")
    laggard = weak_themes[0]["name"] if weak_themes else (weak[0]["symbol"] if weak else "n/a")
    if strong_themes and weak_themes and strong_themes[0].get("key") == weak_themes[0].get("key") and strong_sub_themes and weak_sub_themes:
        leader = f"{strong_sub_themes[0]['parent_name']} > {strong_sub_themes[0]['name']}"
        laggard = f"{weak_sub_themes[0]['parent_name']} > {weak_sub_themes[0]['name']}"
    summary_prefix = "장중 테마 강약" if theme_baskets else "장중 섹터 강약"
    focus_lines = [
        f"시장 레짐: {regime_text} / {'; '.join(regime['signals'][:3])}",
        _theme_line_for("강한 테마", strong_themes),
        _theme_line_for("약한 테마", weak_themes),
        _sub_theme_line_for("강한 세부테마", strong_sub_themes),
        _sub_theme_line_for("약한 세부테마", weak_sub_themes),
        _rotation_line(rotation_alerts),
        _movers_line(watchlist_movers),
        _etf_context_line(strong, weak),
        f"벤치마크: SPY {_fmt_pct(spy_pct)} / QQQ {_fmt_pct(qqq_pct)} / 기준시각 {collected_at}",
    ]
    next_actions = [
        "강한 테마가 SPY/QQQ 대비 계속 우위인지 5분 뒤 재확인",
        "약한 테마 반등 매수는 VIX와 QQQ 회복 확인 후 판단",
    ]
    if rotation_alerts:
        top_rotation = rotation_alerts[0]
        next_actions.insert(
            0,
            f"{top_rotation['into_sub_theme']} 추격은 {top_rotation['out_of_sub_theme']} 회복 전까지 눌림/분할로 제한",
        )
    if regime["label"] == "risk_off":
        next_actions.insert(0, "리스크오프: 고베타/성장주 추격매수 비중 낮추고 손절선 짧게")
    elif regime["label"] == "risk_on":
        next_actions.insert(0, "리스크온: 주도 섹터 눌림에서만 후보 압축")

    return {
        "available": True,
        "summary": f"{summary_prefix}: {leader} 주도 / {laggard} 약세 / 레짐 {regime_text}",
        "collected_at": collected_at,
        "benchmarks": {"SPY": spy_pct, "QQQ": qqq_pct},
        "strong": strong,
        "weak": weak,
        "theme_baskets": theme_baskets,
        "strong_themes": strong_themes,
        "weak_themes": weak_themes,
        "sub_theme_baskets": sub_theme_baskets,
        "strong_sub_themes": strong_sub_themes,
        "weak_sub_themes": weak_sub_themes,
        "rotation_alerts": rotation_alerts,
        "watchlist_movers": watchlist_movers[:10],
        "regime": regime,
        "focus_lines": focus_lines,
        "next_actions": next_actions,
        "quotes": normalized,
    }


def fetch_sector_strength_quotes(symbols: tuple[str, ...] | list[str] | None = None) -> dict[str, dict[str, Any]]:
    try:
        from .yfinance_data import fetch_yahoo_chart_quote_pack, fetch_yfinance_quote_pack
    except ImportError:  # direct script execution via src/main.py
        from yfinance_data import fetch_yahoo_chart_quote_pack, fetch_yfinance_quote_pack

    selected = tuple(symbols or DEFAULT_SECTOR_STRENGTH_SYMBOLS)
    quotes: dict[str, dict[str, Any]] = {}
    for symbol in selected:
        pack = fetch_yahoo_chart_quote_pack(symbol)
        if not (isinstance(pack, dict) and pack.get("available")):
            fallback_pack = fetch_yfinance_quote_pack(symbol)
            if isinstance(fallback_pack, dict):
                if isinstance(pack, dict) and pack.get("warning"):
                    fallback_pack = dict(fallback_pack)
                    fallback_pack["chart_warning"] = pack.get("warning")
                pack = fallback_pack
        quote = dict(pack.get("quote") or {}) if isinstance(pack, dict) else {}
        quote["symbol"] = symbol
        quote["source"] = pack.get("source") if isinstance(pack, dict) else "unknown"
        quote["timestamp"] = pack.get("collected_at") if isinstance(pack, dict) else None
        quote["available"] = bool(pack.get("available")) if isinstance(pack, dict) else False
        if pack.get("warning") if isinstance(pack, dict) else False:
            quote["warning"] = pack.get("warning")
        if pack.get("warnings") if isinstance(pack, dict) else False:
            quote["warnings"] = pack.get("warnings")
        quotes[symbol] = quote
    return quotes
