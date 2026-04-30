from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import requests

try:
    from .repository import (
        fetch_latest_toss_indices,
        fetch_latest_toss_news,
        get_connection,
        insert_toss_index_snapshot,
        insert_toss_news_item,
    )
except ImportError:  # direct script execution
    from repository import (
        fetch_latest_toss_indices,
        fetch_latest_toss_news,
        get_connection,
        insert_toss_index_snapshot,
        insert_toss_news_item,
    )


USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
JINA_PREFIX = "https://r.jina.ai/http://"
TOSS_US_INDEX_PAGES = {
    "COMP.NAI": ("나스닥", "https://www.tossinvest.com/indices/COMP.NAI"),
    "SPX.CBI": ("S&P 500", "https://www.tossinvest.com/indices/SPX.CBI"),
    "SOX.NAI": ("필라델피아 반도체", "https://www.tossinvest.com/indices/SOX.NAI"),
}
TOSS_NEWS_FEED_URL = "https://www.tossinvest.com/feed/news"
US_NEWS_SYMBOL_KEYWORDS = {
    "NVDA": ["nvidia", "엔비디아"],
    "MSFT": ["microsoft", "마이크로소프트", "azure", "copilot"],
    "AMZN": ["amazon", "aws", "아마존"],
    "META": ["meta", "facebook", "메타"],
    "GOOGL": ["google", "alphabet", "구글"],
    "AMD": ["amd"],
    "AVGO": ["broadcom", "브로드컴"],
    "TSM": ["tsmc"],
    "PLTR": ["palantir", "팔란티어"],
    "INTC": ["intel", "인텔"],
}
THEME_KEYWORDS = {
    "ai": ["ai", "인공지능"],
    "ai_infra": ["data center", "데이터센터", "데이터 센터", "capex", "gpu", "server", "클러스터"],
    "semis": ["반도체", "semiconductor", "chip", "foundry"],
    "software": ["software", "소프트웨어", "saas", "cloud", "클라우드"],
    "macro": ["ipo", "inflation", "물가", "증시", "뉴욕증시", "협상"],
    "security": ["security", "보안", "cybersecurity", "사이버보안"],
    "power": ["power", "전력", "utility", "전력망"],
    "defense": ["defense", "defence", "국방", "방산", "military"],
}


def _fetch_jina_markdown(url: str) -> str:
    response = requests.get(f"{JINA_PREFIX}{url}", headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()
    return response.text


def _parse_number(value: str) -> float:
    cleaned = value.replace(",", "").replace("원", "").replace("주", "").replace("%", "").strip()
    if cleaned in {"-", "--", ""}:
        return 0.0
    return float(cleaned)


def parse_toss_index_markdown(index_code: str, markdown: str) -> dict:
    patterns = [
        re.compile(
            r"\|\s*(\d{2}\.\d{2})\s*\|\s*([\d,]+\.\d+|[\d,]+)\s*\|\s*([+-]?[\d,]+\.\d+|[+-]?[\d,]+)\s*\|\s*([+-]?[\d,]+\.\d+%)\s*\|\s*([\d,]+)\s*\|\s*([^|]+)\|\s*([\d,]+\.\d+|[\d,]+)\s*\|\s*([\d,]+\.\d+|[\d,]+)\s*\|\s*([\d,]+\.\d+|[\d,]+)\s*\|"
        ),
        re.compile(
            r"\|\s*(\d{2}\.\d{2})\s*\|\s*([\d,]+\.\d+|[\d,]+)\s*\|\s*([+-]?[\d,]+\.\d+|[+-]?[\d,]+)\s*\|\s*([+-]?[\d,]+\.\d+%)\s*\|\s*([\d,]+)\s*\|\s*([\d,]+\.\d+|[\d,]+)\s*\|\s*([\d,]+\.\d+|[\d,]+)\s*\|\s*([\d,]+\.\d+|[\d,]+)\s*\|"
        ),
        re.compile(
            r"\|\s*(\d{2}\.\d{2})\s*\|\s*([\d,]+\.\d+|[\d,]+)\s*\|\s*([+-]?[\d,]+\.\d+|[+-]?[\d,]+)\s*\|\s*([+-]?[\d,]+\.\d+%)\s*\|\s*([\d,]+\.\d+|[\d,]+)\s*\|\s*([\d,]+\.\d+|[\d,]+)\s*\|\s*([\d,]+\.\d+|[\d,]+)\s*\|"
        ),
    ]
    row_match = None
    trading_value_text = None
    for idx, pattern in enumerate(patterns):
        row_match = pattern.search(markdown)
        if row_match:
            if idx == 0:
                trading_value_text = row_match.group(6).strip()
                volume = _parse_number(row_match.group(5))
                open_idx, high_idx, low_idx = 7, 8, 9
            elif idx == 1:
                trading_value_text = None
                volume = _parse_number(row_match.group(5))
                open_idx, high_idx, low_idx = 6, 7, 8
            else:
                trading_value_text = None
                volume = None
                open_idx, high_idx, low_idx = 5, 6, 7
            break
    if not row_match:
        raise ValueError(f"No price row found for {index_code}")

    index_name = TOSS_US_INDEX_PAGES.get(index_code, (index_code, ""))[0]
    return {
        "index_code": index_code,
        "index_name": index_name,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "close": _parse_number(row_match.group(2)),
        "change_value": _parse_number(row_match.group(3)),
        "change_pct": _parse_number(row_match.group(4)),
        "volume": volume,
        "trading_value_text": trading_value_text,
        "open": _parse_number(row_match.group(open_idx)),
        "high": _parse_number(row_match.group(high_idx)),
        "low": _parse_number(row_match.group(low_idx)),
        "source": "tossinvest_jina",
        "note": f"latest daily row from tossinvest for {index_name}",
    }


def parse_toss_news_feed_markdown(markdown: str) -> list[dict]:
    items: list[dict] = []
    url_pattern = re.compile(r"https://www\.tossinvest\.com/[^)\s]*contentType=news[^)\s]*")
    source_pattern = re.compile(r"\s([가-힣A-Za-z0-9]+)\s+・\s+([^\[]+)$")

    for raw_line in markdown.splitlines():
        line = " ".join(raw_line.split())
        if "contentType=news" not in line:
            continue
        url_match = url_pattern.search(line)
        if not url_match:
            continue
        url = url_match.group(0)
        prefix = line[: url_match.start()].strip()
        prefix = re.sub(r"^\[!\[Image.*?\]\([^)]*\)", "", prefix).strip()
        prefix = prefix.rstrip('](').strip()
        meta_match = source_pattern.search(prefix)
        if not meta_match:
            continue
        source_name = meta_match.group(1).strip()
        published_text = meta_match.group(2).strip()
        headline = prefix[: meta_match.start()].strip()
        headline = re.sub(r"\[[^\]]+\]\([^)]*\)", "", headline).strip()
        if not headline or len(headline) < 5:
            continue
        items.append(
            {
                "headline": headline,
                "source_name": source_name,
                "published_text": published_text,
                "url": url,
                "source": "tossinvest_feed",
                "collected_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    deduped = []
    seen = set()
    for item in items:
        if item["url"] in seen:
            continue
        seen.add(item["url"])
        deduped.append(item)
    return deduped


def map_toss_news_item(item: dict) -> dict:
    headline = (item.get("headline") or "").lower()
    mapped_symbols = []
    mapped_themes = []

    for symbol, keywords in US_NEWS_SYMBOL_KEYWORDS.items():
        if any(keyword.lower() in headline for keyword in keywords):
            mapped_symbols.append(symbol)

    for theme, keywords in THEME_KEYWORDS.items():
        if any(keyword.lower() in headline for keyword in keywords):
            mapped_themes.append(theme)

    mapped = dict(item)
    mapped["mapped_symbols"] = mapped_symbols
    mapped["mapped_themes"] = mapped_themes
    mapped["is_rumor"] = any(keyword in headline for keyword in ["카더라", "취소설", "미확인", "설", "rumor", "unconfirmed"])
    return mapped


def score_toss_news_item(item: dict, portfolio_symbols: set[str] | None = None) -> int:
    portfolio_symbols = portfolio_symbols or set()
    mapped = map_toss_news_item(item)
    score = len(mapped["mapped_symbols"]) * 10 + len(mapped["mapped_themes"]) * 3
    if any(symbol in portfolio_symbols for symbol in mapped["mapped_symbols"]):
        score += 20
    if "macro" in mapped["mapped_themes"]:
        score += 1
    if mapped["is_rumor"]:
        score -= 8
    return score


def fetch_toss_us_indices() -> list[dict]:
    results: list[dict] = []
    for index_code, (_, url) in TOSS_US_INDEX_PAGES.items():
        markdown = _fetch_jina_markdown(url)
        try:
            results.append(parse_toss_index_markdown(index_code, markdown))
        except ValueError:
            continue
    return results


def fetch_toss_us_news(limit: int = 5) -> list[dict]:
    items: list[dict] = []
    seen = set()
    for _, (_, url) in TOSS_US_INDEX_PAGES.items():
        markdown = _fetch_jina_markdown(url)
        for item in parse_toss_news_feed_markdown(markdown):
            if item["url"] in seen:
                continue
            seen.add(item["url"])
            items.append(map_toss_news_item(item))
            if len(items) >= limit:
                return items

    markdown = _fetch_jina_markdown(TOSS_NEWS_FEED_URL)
    for item in parse_toss_news_feed_markdown(markdown):
        if item["url"] in seen:
            continue
        seen.add(item["url"])
        items.append(item)
        if len(items) >= limit:
            break
    return items


def store_toss_index_snapshot(conn, payload: dict) -> None:
    insert_toss_index_snapshot(conn, **payload)


def store_toss_news_items(conn, items: list[dict]) -> None:
    for item in items:
        insert_toss_news_item(
            conn,
            headline=item["headline"],
            source_name=item.get("source_name", ""),
            published_text=item.get("published_text", ""),
            url=item["url"],
            source=item.get("source", "tossinvest_feed"),
            collected_at=item["collected_at"],
        )


def run_toss_ingest(db_path: str | Path) -> dict:
    conn = get_connection(db_path)
    index_rows = fetch_toss_us_indices()
    news_rows = fetch_toss_us_news(limit=5)
    for row in index_rows:
        store_toss_index_snapshot(conn, row)
    store_toss_news_items(conn, news_rows)
    conn.commit()
    conn.close()
    return {
        "toss_indices": len(index_rows),
        "toss_news": len(news_rows),
        "db_path": str(db_path),
    }


def build_toss_market_brief(db_path: str | Path, portfolio_symbols: set[str] | None = None) -> str:
    conn = get_connection(db_path)
    index_rows = fetch_latest_toss_indices(conn, limit=10)
    news_rows = fetch_latest_toss_news(conn, limit=6)
    conn.close()

    lines = ["[토스증권 미국장 보조지표]"]
    if index_rows:
        for row in index_rows:
            lines.append(
                f"- {row['index_name']}({row['index_code']}): {row['close']:.2f} / {row['change_pct']:+.2f}% / 거래량 {int(row['volume'] or 0):,}"
            )
    else:
        lines.append("- 저장된 토스증권 미국지수 데이터 없음")

    if news_rows:
        ranked_news = sorted(
            (map_toss_news_item(dict(row)) for row in news_rows),
            key=lambda item: (-score_toss_news_item(item, portfolio_symbols), item.get("published_text", "")),
        )
        lines.append("[토스증권 주요 뉴스]")
        for row in ranked_news[:3]:
            symbol_text = ", ".join(row["mapped_symbols"]) if row["mapped_symbols"] else "없음"
            theme_text = ", ".join(row["mapped_themes"]) if row["mapped_themes"] else "없음"
            lines.append(f"- {row['headline']} / {row['source_name']} / {row['published_text']} / 관련종목: {symbol_text} / 테마: {theme_text}")
    return "\n".join(lines)
