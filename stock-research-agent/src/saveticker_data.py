from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import requests

try:
    from .repository import get_connection, fetch_latest_saveticker_items, insert_saveticker_item
except ImportError:
    from repository import get_connection, fetch_latest_saveticker_items, insert_saveticker_item


USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
SAVETICKER_URL = "https://www.saveticker.com/app/news"
SAVETICKER_API_URL = "https://api.saveticker.com/api/news/list"
JINA_PREFIX = "https://r.jina.ai/http://"
US_SYMBOLS = {"NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "META", "GOOGL", "AMD", "AVGO", "TSM", "PLTR", "INTC", "SMCI", "ORCL", "GME", "LULU"}
NEWS_KINDS = {"속보", "정보", "분석", "종합"}
THEME_KEYWORDS = {
    "ai": ["ai", "앤트로픽", "사이버캡", "반도체", "gpu", "서버"],
    "software": ["software", "소프트웨어", "cloud", "클라우드"],
    "macro": ["백악관", "파월", "연준", "fed", "금리", "인플레이션", "cpi", "이란", "전쟁", "증시", "협상"],
    "earnings": ["실적발표", "실적 발표", "분기 실적", "가이던스"],
    "security": ["security", "보안", "cybersecurity", "사이버보안"],
    "power": ["power", "전력", "utility", "전력망"],
    "defense": ["defense", "defence", "국방", "방산", "military"],
    "crypto": ["bitcoin", "비트코인", "ethereum", "이더리움", "crypto", "코인"],
}
IMPORTANT_SYMBOLS = {
    "NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "META", "GOOGL", "AMD", "AVGO", "TSM",
    "PLTR", "COIN", "MSTR", "HOOD", "SOFI", "IREN", "RKLB", "OKLO", "BMNR", "RDW",
}


def _fetch_jina_markdown(url: str) -> str:
    response = requests.get(f"{JINA_PREFIX}{url}", headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()
    return response.text


def _extract_ticker_names(api_item: dict) -> list[str]:
    tickers: list[str] = []
    for tag in api_item.get("tag_names") or []:
        if not isinstance(tag, str) or not tag.startswith("$"):
            continue
        symbol = tag[1:].strip().upper()
        if symbol:
            tickers.append(symbol)
    for ticker in api_item.get("tickers") or []:
        symbol = None
        if isinstance(ticker, str):
            symbol = ticker
        elif isinstance(ticker, dict):
            symbol = ticker.get("symbol") or ticker.get("ticker") or ticker.get("name")
        if symbol:
            symbol = str(symbol).replace("$", "").strip().upper()
            if symbol:
                tickers.append(symbol)
    return list(dict.fromkeys(tickers))


def normalize_saveticker_api_item(api_item: dict) -> dict:
    tag_names = [tag for tag in (api_item.get("tag_names") or []) if isinstance(tag, str)]
    kind = next((tag for tag in tag_names if tag in NEWS_KINDS), "정보")
    title = str(api_item.get("title") or "").strip()
    news_id = api_item.get("id")
    source_name = str(api_item.get("source") or "SAVE").strip() or "SAVE"
    author_name = str(api_item.get("author_name") or "").strip()
    source = f"saveticker_api:{source_name}"
    if author_name:
        source = f"{source}:{author_name}"
    return {
        "headline": title,
        "kind": kind,
        "published_text": str(api_item.get("created_at") or ""),
        "tickers": _extract_ticker_names(api_item),
        "popularity_text": str(api_item.get("view_count") or ""),
        "source": source,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "url": f"{SAVETICKER_URL}/{news_id}" if news_id is not None else SAVETICKER_URL,
    }


def _fetch_saveticker_api_news(limit: int = 20, *, sources: str | None = None, tickers: str | None = None, search: str | None = None) -> list[dict]:
    params = {"page": 1, "page_size": limit}
    if sources:
        params["sources"] = sources
    if tickers:
        params["tickers"] = tickers
    if search:
        params["search"] = search
    response = requests.get(SAVETICKER_API_URL, params=params, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}, timeout=20)
    response.raise_for_status()
    payload = response.json()
    return [normalize_saveticker_api_item(item) for item in payload.get("news_list", []) if isinstance(item, dict) and item.get("title")]


def parse_saveticker_news_markdown(markdown: str) -> list[dict]:
    items: list[dict] = []
    lines = [line.strip() for line in markdown.splitlines() if line.strip()]
    i = 0
    while i < len(lines):
        line = lines[i]
        if line in {"속보", "정보", "분석"}:
            kind = line
            published_text = lines[i + 1] if i + 1 < len(lines) else ""
            headline = lines[i + 2] if i + 2 < len(lines) else ""
            j = i + 3
            tickers: list[str] = []
            popularity_text = ""
            while j < len(lines):
                if lines[j] == "#" and j + 1 < len(lines):
                    maybe_ticker = lines[j + 1].strip().upper()
                    if maybe_ticker in US_SYMBOLS:
                        tickers.append(maybe_ticker)
                        j += 2
                        continue
                if re.match(r"^\d+(?:\.\d+)?K$", lines[j]):
                    popularity_text = lines[j]
                    break
                if lines[j] in {"속보", "정보", "분석"}:
                    break
                j += 1
            if headline:
                items.append(
                    {
                        "headline": headline,
                        "kind": kind,
                        "published_text": published_text,
                        "tickers": tickers,
                        "popularity_text": popularity_text,
                        "source": "saveticker",
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                        "url": SAVETICKER_URL,
                    }
                )
            i = j if j > i else i + 1
        else:
            i += 1
    return items


def map_saveticker_item(item: dict) -> dict:
    headline = (item.get("headline") or "").lower()
    tickers = list(item.get("tickers") or [])
    themes = []
    for theme, keywords in THEME_KEYWORDS.items():
        if any(keyword.lower() in headline for keyword in keywords):
            themes.append(theme)
    mapped = dict(item)
    mapped["tickers"] = tickers
    mapped["mapped_themes"] = themes
    mapped["is_rumor"] = "카더라" in headline
    return mapped


def score_saveticker_item(item: dict, portfolio_symbols: set[str] | None = None) -> int:
    portfolio_symbols = portfolio_symbols or set()
    mapped = map_saveticker_item(item)
    score = len(mapped["tickers"]) * 10 + len(mapped["mapped_themes"]) * 3
    if any(ticker in portfolio_symbols for ticker in mapped["tickers"]):
        score += 20
    if mapped["kind"] == "속보":
        score += 5
    if mapped["is_rumor"]:
        score -= 8
    return score


def _normalize_symbol_set(symbols: set[str] | list[str] | tuple[str, ...] | None) -> set[str]:
    return {str(symbol).replace("$", "").upper().strip() for symbol in (symbols or []) if str(symbol).strip()}


def _parse_popularity(popularity_text: str | None) -> float:
    text = str(popularity_text or "").strip().replace(",", "")
    if not text:
        return 0.0
    multiplier = 1.0
    if text[-1:].upper() == "K":
        multiplier = 1000.0
        text = text[:-1]
    elif text[-1:].upper() == "M":
        multiplier = 1_000_000.0
        text = text[:-1]
    try:
        return float(text) * multiplier
    except ValueError:
        return 0.0


def _saveticker_row_to_item(row) -> dict:
    return {
        "headline": row["headline"],
        "kind": row["kind"],
        "published_text": row["published_text"],
        "tickers": [ticker for ticker in (row["tickers_text"] or "").split(",") if ticker],
        "popularity_text": row["popularity_text"],
        "source": row["source"],
        "collected_at": row["collected_at"],
        "url": row["url"],
    }


def score_saveticker_breaking_importance(
    item: dict,
    portfolio_symbols: set[str] | list[str] | tuple[str, ...] | None = None,
    watchlist_symbols: set[str] | list[str] | tuple[str, ...] | None = None,
) -> dict:
    portfolio = _normalize_symbol_set(portfolio_symbols)
    watchlist = _normalize_symbol_set(watchlist_symbols)
    mapped = map_saveticker_item(item)
    tickers = [str(ticker).upper() for ticker in mapped.get("tickers", [])]
    ticker_set = set(tickers)
    themes = mapped.get("mapped_themes", [])
    source = str(mapped.get("source") or "")
    popularity = _parse_popularity(mapped.get("popularity_text"))

    score = 0
    relevance = "general"
    if ticker_set & portfolio:
        score += 45
        relevance = "portfolio"
    elif ticker_set & watchlist:
        score += 30
        relevance = "watchlist"
    elif ticker_set & IMPORTANT_SYMBOLS:
        score += 18
        relevance = "important_symbol"
    elif tickers:
        score += 10
        relevance = "symbol"

    if mapped.get("kind") == "속보":
        score += 8
    elif mapped.get("kind") == "분석":
        score += 3

    score += min(len(themes) * 7, 21)
    if "macro" in themes and not tickers:
        score += 12
    if any(theme in themes for theme in ["ai", "defense", "crypto", "earnings", "power"]):
        score += 4
    if popularity >= 20_000:
        score += 6
    elif popularity >= 5_000:
        score += 4
    elif popularity >= 1_000:
        score += 2
    if "reuters" in source.lower() or "financial juice" in source.lower():
        score += 2
    if mapped.get("is_rumor"):
        score -= 10

    if mapped.get("is_rumor"):
        trust_label = "루머/검증필요"
        action_hint = "추가 검증 전 포지션 확대 금지"
    elif relevance == "portfolio":
        trust_label = "보통"
        action_hint = "보유 비중/손절선 영향 즉시 점검"
    elif relevance == "watchlist":
        trust_label = "보통"
        action_hint = "관심종목 진입 후보면 가격 반응 확인"
    elif "macro" in themes:
        trust_label = "보통"
        action_hint = "지수/금리/섹터 영향 먼저 확인"
    else:
        trust_label = "보통"
        action_hint = "관련 종목과 공식 소스 교차확인"

    enriched = dict(mapped)
    enriched.update(
        {
            "tickers": tickers,
            "importance_score": score,
            "importance_label": "상" if score >= 50 else "중" if score >= 30 else "하",
            "trust_label": trust_label,
            "relevance": relevance,
            "action_hint": action_hint,
        }
    )
    return enriched


def select_important_saveticker_breaking(
    items: list[dict],
    portfolio_symbols: set[str] | list[str] | tuple[str, ...] | None = None,
    watchlist_symbols: set[str] | list[str] | tuple[str, ...] | None = None,
    limit: int = 5,
    min_score: int = 18,
) -> list[dict]:
    scored = [score_saveticker_breaking_importance(item, portfolio_symbols, watchlist_symbols) for item in items]
    filtered = [item for item in scored if item["importance_score"] >= min_score]
    ranked = sorted(
        filtered,
        key=lambda item: (
            -item["importance_score"],
            1 if item.get("is_rumor") else 0,
            item.get("published_text", ""),
        ),
    )
    deduped: list[dict] = []
    seen_headlines: set[str] = set()
    for item in ranked:
        headline_key = re.sub(r"\s+", " ", item.get("headline", "")).strip().lower()
        if headline_key in seen_headlines:
            continue
        seen_headlines.add(headline_key)
        deduped.append(item)
        if len(deduped) >= limit:
            break
    return deduped


def build_saveticker_important_breaking(
    db_path: str | Path,
    portfolio_symbols: set[str] | list[str] | tuple[str, ...] | None = None,
    watchlist_symbols: set[str] | list[str] | tuple[str, ...] | None = None,
    limit: int = 5,
    min_score: int = 18,
) -> str:
    conn = get_connection(db_path)
    rows = fetch_latest_saveticker_items(conn, limit=50)
    conn.close()
    items = [_saveticker_row_to_item(row) for row in rows]
    selected = select_important_saveticker_breaking(
        items,
        portfolio_symbols=portfolio_symbols,
        watchlist_symbols=watchlist_symbols,
        limit=limit,
        min_score=min_score,
    )

    lines = ["[SaveTicker 중요 속보]"]
    if not selected:
        lines.append("- 중요 기준을 넘긴 SaveTicker 속보 없음")
        return "\n".join(lines)

    for item in selected:
        ticker_text = ", ".join(item["tickers"]) if item["tickers"] else "시장/매크로"
        theme_text = ", ".join(item["mapped_themes"]) if item["mapped_themes"] else "일반"
        lines.append(
            f"- 중요도 {item['importance_label']}({item['importance_score']}) / 신뢰도: {item['trust_label']} / 관련: {ticker_text} / "
            f"{item['headline']} / {item['kind']} / {item['published_text']} / 테마: {theme_text} / 액션: {item['action_hint']}"
        )
    return "\n".join(lines)


def store_saveticker_items(conn, items: list[dict]) -> None:
    for item in items:
        insert_saveticker_item(
            conn,
            headline=item["headline"],
            kind=item.get("kind", ""),
            published_text=item.get("published_text", ""),
            tickers_text=",".join(item.get("tickers", [])),
            popularity_text=item.get("popularity_text", ""),
            source=item.get("source", "saveticker"),
            collected_at=item["collected_at"],
            url=item.get("url"),
        )


def fetch_saveticker_news(limit: int = 20) -> list[dict]:
    try:
        api_items = _fetch_saveticker_api_news(limit=limit)
        if api_items:
            return api_items[:limit]
    except requests.RequestException:
        pass
    markdown = _fetch_jina_markdown(SAVETICKER_URL)
    return parse_saveticker_news_markdown(markdown)[:limit]


def run_saveticker_ingest(db_path: str | Path) -> dict:
    conn = get_connection(db_path)
    items = fetch_saveticker_news(limit=20)
    store_saveticker_items(conn, items)
    conn.commit()
    conn.close()
    return {"saveticker_items": len(items), "db_path": str(db_path)}


def build_saveticker_brief(db_path: str | Path, portfolio_symbols: set[str] | None = None) -> str:
    conn = get_connection(db_path)
    rows = fetch_latest_saveticker_items(conn, limit=20)
    conn.close()
    mapped_rows = []
    for row in rows:
        mapped_rows.append(
            map_saveticker_item(
                {
                    "headline": row["headline"],
                    "kind": row["kind"],
                    "published_text": row["published_text"],
                    "tickers": [ticker for ticker in (row["tickers_text"] or "").split(",") if ticker],
                    "popularity_text": row["popularity_text"],
                    "source": row["source"],
                    "collected_at": row["collected_at"],
                    "url": row["url"],
                }
            )
        )
    ranked = sorted(mapped_rows, key=lambda item: (-score_saveticker_item(item, portfolio_symbols), item.get("published_text", "")))

    lines = ["[SaveTicker 속보]"]
    if not ranked:
        lines.append("- 저장된 SaveTicker 뉴스 없음")
        return "\n".join(lines)

    for item in ranked[:3]:
        ticker_text = ", ".join(item["tickers"]) if item["tickers"] else "없음"
        theme_text = ", ".join(item["mapped_themes"]) if item["mapped_themes"] else "없음"
        rumor_text = " / rumor" if item["is_rumor"] else ""
        lines.append(f"- {item['headline']} / {item['kind']} / {item['published_text']} / 관련종목: {ticker_text} / 테마: {theme_text}{rumor_text}")
    return "\n".join(lines)
