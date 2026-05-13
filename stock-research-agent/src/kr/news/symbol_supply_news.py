"""KRX single-symbol supply + news brief template."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

import requests

try:  # package import
    from ..flow.symbol_flow import build_krx_symbol_flow_snapshot_v2
    from ..kiwoom.client import KiwoomRestClient, build_kiwoom_data_client
    from ...watchlists import normalize_symbol
except ImportError:  # direct-script import via python3 src/main.py
    from kr.flow.symbol_flow import build_krx_symbol_flow_snapshot_v2
    from kr.kiwoom.client import KiwoomRestClient, build_kiwoom_data_client
    from watchlists import normalize_symbol

KST = timezone(timedelta(hours=9))
NAVER_MOBILE_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://m.stock.naver.com/",
}


def _now_kst_iso() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


def normalize_krx_code(symbol: str | None) -> str:
    raw = str(symbol or "").strip()
    if not raw:
        return raw
    try:
        raw = normalize_symbol(raw)
    except Exception:
        pass
    raw = raw.upper().strip()
    if raw.startswith("A") and len(raw) == 7 and raw[1:].isdigit():
        raw = raw[1:]
    if raw.endswith(".KS") or raw.endswith(".KQ"):
        raw = raw[:-3]
    return raw


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("%", "")
    if not text:
        return None
    negative = False
    while text and text[0] in "+-":
        if text[0] == "-":
            negative = not negative
        text = text[1:]
    try:
        number = int(float(text))
    except ValueError:
        return None
    return -number if negative else number


def _fmt_qty(value: Any) -> str:
    number = _to_int(value)
    if number is None:
        return "확인불가"
    sign = "+" if number > 0 else ""
    return f"{sign}{number:,}주"


def _pct_from_price(close_price: Any, compare_to_previous: Any) -> float | None:
    close = _to_int(close_price)
    diff = _to_int(compare_to_previous)
    if close is None or diff is None:
        return None
    prev = close - diff
    if prev == 0:
        return None
    return diff / prev * 100


def fetch_naver_stock_integration(symbol: str, session: Any | None = None) -> dict[str, Any]:
    code = normalize_krx_code(symbol)
    sess = session or requests
    response = sess.get(
        f"https://m.stock.naver.com/api/stock/{code}/integration",
        headers=NAVER_MOBILE_HEADERS,
        timeout=8,
    )
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, dict) else {}


def fetch_naver_stock_news(symbol: str, limit: int = 5, session: Any | None = None) -> list[dict[str, Any]]:
    code = normalize_krx_code(symbol)
    sess = session or requests
    response = sess.get(
        f"https://m.stock.naver.com/api/news/stock/{code}",
        params={"pageSize": str(limit), "page": "1"},
        headers=NAVER_MOBILE_HEADERS,
        timeout=8,
    )
    response.raise_for_status()
    payload = response.json()
    groups = payload if isinstance(payload, list) else [payload]
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for group in groups:
        if not isinstance(group, dict):
            continue
        for item in group.get("items") or []:
            if not isinstance(item, dict):
                continue
            key = str(item.get("id") or f"{item.get('officeId')}:{item.get('articleId')}:{item.get('title')}")
            if key in seen:
                continue
            seen.add(key)
            office_id = item.get("officeId")
            article_id = item.get("articleId")
            url = item.get("url")
            if not url and office_id and article_id:
                url = f"https://n.news.naver.com/mnews/article/{office_id}/{article_id}"
            rows.append(
                {
                    "id": key,
                    "title": item.get("title") or "",
                    "source": item.get("officeName") or item.get("source") or "Naver",
                    "datetime": item.get("datetime") or "",
                    "body": item.get("body") or "",
                    "url": url,
                }
            )
            if len(rows) >= limit:
                return rows
    return rows[:limit]


def _latest_deal_trend(integration: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(integration, dict):
        return {}
    rows = integration.get("dealTrendInfos") or []
    if isinstance(rows, list) and rows:
        return rows[0] if isinstance(rows[0], dict) else {}
    return {}


def _flow_trade_volume(flow: dict[str, Any]) -> str | None:
    evidence = flow.get("raw_evidence") or {}
    for key in ["ka10045_row", "ka10008_row", "ka90008_row"]:
        row = evidence.get(key) if isinstance(evidence, dict) else None
        if isinstance(row, dict):
            qty = _to_int(row.get("trde_qty"))
            if qty is not None and qty > 0:
                return f"{qty:,}"
    return None


def _headline_implication(title: str) -> str:
    text = title.lower()
    if any(k in title for k in ["급등", "상승", "수혜", "호재", "최고치", "강세"]):
        return "긍정/모멘텀"
    if any(k in title for k in ["급락", "하락", "리콜", "악재", "소송", "과징금", "관세"]):
        return "리스크 확인"
    if any(k in text for k in ["실적", "earnings", "매출", "영업이익"]):
        return "실적 체크"
    return "중립"


def build_krx_symbol_supply_news_report(
    symbol: str,
    *,
    client: Any | None = None,
    as_of_date: str | None = None,
    flow_snapshot: dict[str, Any] | None = None,
    integration: dict[str, Any] | None = None,
    news_items: list[dict[str, Any]] | None = None,
    max_news: int = 5,
) -> dict[str, Any]:
    code = normalize_krx_code(symbol)
    if flow_snapshot is None:
        if client is None:
            client = build_kiwoom_data_client()
        flow_snapshot = build_krx_symbol_flow_snapshot_v2(client, code, as_of_date=as_of_date)
    if integration is None:
        try:
            integration = fetch_naver_stock_integration(code)
        except Exception as exc:
            integration = {"error": f"{type(exc).__name__}: {str(exc)[:120]}"}
    if news_items is None:
        try:
            news_items = fetch_naver_stock_news(code, limit=max_news)
        except Exception as exc:
            news_items = [{"title": "뉴스 조회 실패", "source": "Naver", "datetime": "", "body": str(exc)[:160], "url": None}]

    trend = _latest_deal_trend(integration)
    stock_name = (integration or {}).get("stockName") or flow_snapshot.get("name") or code
    pct = _pct_from_price(trend.get("closePrice"), trend.get("compareToPreviousClosePrice"))
    signal = flow_snapshot.get("supply_signal") or "수급확인"
    program_qty = _to_int(flow_snapshot.get("program_net_buy_qty"))
    chase_note = "추격 부담: 가격이 이미 크게 움직였으면 눌림 확인 우선"
    if signal in {"기관매도", "프로그램매도", "기준일미확인"}:
        chase_note = "단정 금지: 기준일/프로그램/기관 방향 재확인 필요"
    elif pct is not None and pct >= 5:
        chase_note = "수급은 좋지만 당일 상승폭 큼: 추격보다 눌림/익일 연속성 확인"
    elif program_qty is not None and program_qty > 0:
        chase_note = "수급 양호: 프로그램 순매수 유지 여부가 핵심"

    return {
        "mode": "krx_symbol_brief",
        "symbol": code,
        "name": stock_name,
        "source": {
            "flow": "kiwoom",
            "flow_env": flow_snapshot.get("env"),
            "flow_base_url": flow_snapshot.get("base_url"),
            "news": "naver_mobile_stock_news",
            "integration": "naver_mobile_stock_integration",
        },
        "collected_at": _now_kst_iso(),
        "flow_snapshot": flow_snapshot,
        "naver_deal_trend": trend,
        "news_items": news_items[:max_news],
        "supply_signal": signal,
        "price_pct": pct,
        "template_sections": ["판정", "수급", "가격", "뉴스", "리스크", "액션"],
        "next_actions": [
            chase_note,
            "기관/외국인/프로그램 수량과 data_dates가 같은 방향인지 확인",
            "뉴스는 제목 모멘텀만 보지 말고 본문에서 실적/정책/일회성 재료 구분",
        ],
    }


def format_krx_symbol_supply_news_report(report: dict[str, Any]) -> list[str]:
    flow = report.get("flow_snapshot") or {}
    trend = report.get("naver_deal_trend") or {}
    source = report.get("source") or {}
    pct = report.get("price_pct")
    pct_text = f"{pct:+.2f}%" if pct is not None else "pct 확인불가"
    lines = [
        f"{report.get('name')}({report.get('symbol')}) 수급+뉴스 템플릿 / collected_at={report.get('collected_at')}",
        f"[판정] {report.get('supply_signal')} / flow_env={source.get('flow_env')} / base={source.get('flow_base_url')}",
        f"[수급] 기관 { _fmt_qty(flow.get('institution_net_buy_qty')) } / 외국인 { _fmt_qty(flow.get('foreign_net_buy_qty')) } / 프로그램 { _fmt_qty(flow.get('program_net_buy_qty')) }",
        f"[기준일] requested={flow.get('requested_date')} / data_dates={flow.get('data_dates')} / today_confirmed={flow.get('is_today_confirmed')}",
    ]
    if trend:
        volume_text = _flow_trade_volume(flow) or trend.get('accumulatedTradingVolume', '확인불가')
        lines.append(
            f"[가격] {trend.get('closePrice', '확인불가')}원 / 전일대비 {trend.get('compareToPreviousClosePrice', '확인불가')}원 ({pct_text}) / 거래량 {volume_text}"
        )
        lines.append(
            f"[Naver 수급] 기준일 {trend.get('bizdate', '확인불가')} / 기관 {_fmt_qty(trend.get('organPureBuyQuant'))} / 외국인 {_fmt_qty(trend.get('foreignerPureBuyQuant'))} / 개인 {_fmt_qty(trend.get('individualPureBuyQuant'))}"
        )
    warnings = flow.get("warnings") or []
    if warnings:
        lines.append("[리스크] " + " / ".join(str(w) for w in warnings[:3]))
    news = report.get("news_items") or []
    if news:
        lines.append("[뉴스]")
        for idx, item in enumerate(news[:5], 1):
            title = item.get("title") or "제목 없음"
            lines.append(f"{idx}. {title} / {item.get('source', 'Naver')} / {item.get('datetime', '')} / {_headline_implication(title)}")
    lines.append("[액션] " + " / ".join(report.get("next_actions") or []))
    return lines
