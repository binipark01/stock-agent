from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

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
DEFAULT_TOSS_STOCK_CODE_CACHE_PATH = Path(__file__).resolve().parents[1] / "data" / "toss_stock_codes.json"
TOSS_US_INDEX_PAGES = {
    "COMP.NAI": ("나스닥", "https://www.tossinvest.com/indices/COMP.NAI"),
    "SPX.CBI": ("S&P 500", "https://www.tossinvest.com/indices/SPX.CBI"),
    "SOX.NAI": ("필라델피아 반도체", "https://www.tossinvest.com/indices/SOX.NAI"),
}
TOSS_US_STOCK_CODES = {
    # Observed public Toss stock-id for PLTR order page. This is not the ISIN.
    # Jina-readable URL pattern: https://www.tossinvest.com/stocks/US20200930014/order
    "PLTR": "US20200930014",
    # Observed public Toss base page for Redwire.
    # Jina-readable URL pattern: https://www.tossinvest.com/stocks/US20210903005
    "RDW": "US20210903005",
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
    cleaned = re.sub(r"[^0-9+\-.]", "", value.replace(",", ""))
    if cleaned in {"-", "--", ""}:
        return 0.0
    return float(cleaned)


def _load_toss_stock_code_cache(cache_path: str | Path | bool | None = DEFAULT_TOSS_STOCK_CODE_CACHE_PATH) -> dict[str, str]:
    if cache_path is False or cache_path is None:
        return {}
    path = Path(cache_path)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(symbol).upper(): str(code) for symbol, code in data.items() if str(code).startswith("US")}


def _save_toss_stock_code_cache(cache: dict[str, str], cache_path: str | Path | bool | None = DEFAULT_TOSS_STOCK_CODE_CACHE_PATH) -> None:
    if cache_path is False or cache_path is None:
        return
    path = Path(cache_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(sorted(cache.items())), ensure_ascii=False, indent=2), encoding="utf-8")


def extract_toss_stock_code_from_markdown(markdown: str, symbol: str) -> str | None:
    upper_symbol = symbol.upper()
    code_pattern = re.compile(r"(?:https?://www\.tossinvest\.com)?/stocks/(US[A-Z0-9]{8,24})", re.IGNORECASE)
    candidates: list[tuple[int, str]] = []
    for match in code_pattern.finditer(markdown):
        code = match.group(1).upper()
        window = markdown[max(0, match.start() - 350) : min(len(markdown), match.end() + 350)]
        window_upper = window.upper()
        score = 1
        if upper_symbol in window_upper:
            score += 20
        if f"({upper_symbol})" in window_upper or f" {upper_symbol}" in window_upper:
            score += 5
        if "/COMMUNITY" not in window_upper and "/ORDER" not in window_upper:
            score += 1
        candidates.append((score, code))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    if candidates[0][0] > 1 or len({code for _, code in candidates}) == 1:
        return candidates[0][1]
    return None


def _toss_stock_search_urls(symbol: str) -> list[str]:
    query = quote_plus(f"site:tossinvest.com/stocks {symbol} TossInvest")
    return [
        f"https://duckduckgo.com/html/?q={query}",
        f"https://www.bing.com/search?q={query}",
    ]


def resolve_toss_stock_code(
    symbol: str,
    fetcher=None,
    cache_path: str | Path | bool | None = DEFAULT_TOSS_STOCK_CODE_CACHE_PATH,
    code_map: dict[str, str] | None = None,
) -> str | None:
    upper_symbol = symbol.upper()
    merged_code_map = {**TOSS_US_STOCK_CODES, **(code_map or {})}
    if merged_code_map.get(upper_symbol):
        return merged_code_map[upper_symbol]

    cache = _load_toss_stock_code_cache(cache_path)
    if cache.get(upper_symbol):
        return cache[upper_symbol]

    fetch = fetcher or _fetch_jina_markdown
    for search_url in _toss_stock_search_urls(upper_symbol):
        try:
            markdown = fetch(search_url)
        except Exception:
            continue
        code = extract_toss_stock_code_from_markdown(markdown, upper_symbol)
        if code:
            cache[upper_symbol] = code
            _save_toss_stock_code_cache(cache, cache_path)
            return code
    return None


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


def parse_toss_day_market_markdown(markdown: str, symbol: str | None = None, source_url: str | None = None) -> dict:
    text = "\n".join(line.strip() for line in markdown.splitlines() if line.strip())
    upper_symbol = (symbol or "").upper()

    if not upper_symbol and source_url:
        for candidate, toss_code in TOSS_US_STOCK_CODES.items():
            if toss_code in source_url:
                upper_symbol = candidate
                break
    if not upper_symbol:
        symbol_match = re.search(r"\b([A-Z]{1,5})\b", text)
        upper_symbol = symbol_match.group(1) if symbol_match else "UNKNOWN"

    usd_match = re.search(r"\$\s*([+-]?[\d,]+(?:\.\d+)?)", text)
    krw_match = re.search(r"([+-]?[\d,]+)\s*원", text)
    session_match = re.search(r"(데이마켓|주간거래|주간장|데이장)", text)
    session_label = session_match.group(1) if session_match else ("정규장" if "지난 정규장" in text else "데이마켓")

    change_krw = None
    change_pct = None
    session_line = ""
    for raw_line in markdown.splitlines():
        if session_label in raw_line or (session_label == "정규장" and "지난 정규장" in raw_line):
            session_line = raw_line.strip()
            break
    if not session_line:
        for raw_line in markdown.splitlines():
            if any(keyword in raw_line for keyword in ["지난 정규장", "전일", "정규장보다"]):
                session_line = raw_line.strip()
                break
    if session_line:
        change_match = re.search(r"([+-]?[\d,]+)\s*원", session_line)
        pct_match = re.search(r"([+-]?[\d,]+(?:\.\d+)?)\s*%", session_line)
        if change_match:
            change_krw = _parse_number(change_match.group(1))
        if pct_match:
            pct_sign = -1 if (change_match and change_match.group(1).strip().startswith("-")) or "-" in session_line[: pct_match.start()] else 1
            change_pct = pct_sign * abs(_parse_number(pct_match.group(1)))

    time_match = re.search(r"\b(\d{1,2}:\d{2}:\d{2})\b", text)
    volume_match = re.search(r"거래량\s*([\d,]+)", text)
    if not volume_match:
        volume_match = re.search(r"([\d,]+)\s*주", text)

    if not usd_match:
        raise ValueError(f"No Toss day-market USD quote found for {upper_symbol}")

    return {
        "symbol": upper_symbol,
        "source": "tossinvest_jina",
        "source_label": "Toss/Jina",
        "source_url": source_url,
        "session_label": session_label,
        "usd_price": _parse_number(usd_match.group(1)),
        "krw_price": _parse_number(krw_match.group(1)) if krw_match else None,
        "change_krw": change_krw,
        "change_pct": change_pct,
        "last_trade_time": time_match.group(1) if time_match else None,
        "volume": int(_parse_number(volume_match.group(1))) if volume_match else None,
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }


def fetch_toss_day_market_quote(
    symbol: str,
    stock_code: str | None = None,
    fetcher=None,
    resolver_fetcher=None,
    cache_path: str | Path | bool | None = DEFAULT_TOSS_STOCK_CODE_CACHE_PATH,
    code_map: dict[str, str] | None = None,
) -> dict:
    upper_symbol = symbol.upper()
    toss_code = stock_code or resolve_toss_stock_code(upper_symbol, fetcher=resolver_fetcher, cache_path=cache_path, code_map=code_map)
    if not toss_code:
        return {
            "symbol": upper_symbol,
            "available": False,
            "reason": "unknown_toss_stock_code",
            "source_label": "Toss/Jina",
        }
    source_url = f"https://www.tossinvest.com/stocks/{toss_code}"
    try:
        markdown = (fetcher or _fetch_jina_markdown)(source_url)
        quote = parse_toss_day_market_markdown(markdown, symbol=upper_symbol, source_url=source_url)
        quote["available"] = True
        quote["toss_code"] = toss_code
        return quote
    except Exception as exc:
        return {
            "symbol": upper_symbol,
            "available": False,
            "reason": f"parse_or_fetch_failed: {exc}",
            "source_url": source_url,
            "source_label": "Toss/Jina",
        }


def _format_day_market_focus(quote: dict) -> str:
    symbol = quote.get("symbol", "UNKNOWN")
    if not quote.get("available", True):
        return f"{symbol} 데이마켓: 가격 확인 실패 / reason={quote.get('reason', 'unknown')} / source={quote.get('source_label', 'Toss/Jina')}"
    parts = [f"{symbol} {quote.get('session_label', '데이마켓')}: ${quote['usd_price']:.2f}"]
    if quote.get("krw_price") is not None:
        parts.append(f"{int(quote['krw_price']):,}원")
    if quote.get("change_pct") is not None:
        parts.append(f"{quote['change_pct']:+.2f}%")
    if quote.get("change_krw") is not None:
        parts.append(f"{int(quote['change_krw']):+,}원")
    if quote.get("last_trade_time"):
        parts.append(str(quote["last_trade_time"]))
    if quote.get("volume") is not None:
        parts.append(f"거래량 {int(quote['volume']):,}")
    parts.append(f"source={quote.get('source_label', 'Toss/Jina')}")
    return " / ".join(parts)


def build_toss_day_market_quote_report(request: str, symbols: list[str] | None = None, runtime_context: dict | None = None) -> dict:
    runtime_context = runtime_context or {}
    requested_symbols = symbols or []
    if not requested_symbols:
        requested_symbols = [symbol for symbol in TOSS_US_STOCK_CODES if symbol.lower() in request.lower()]
    if not requested_symbols:
        requested_symbols = ["PLTR"]

    markdown_map = runtime_context.get("toss_day_market_markdown") or {}
    quote_map = runtime_context.get("day_market_quotes") or {}
    code_map = {**TOSS_US_STOCK_CODES, **(runtime_context.get("toss_code_map") or {})}

    quotes = []
    for symbol in requested_symbols[:5]:
        upper_symbol = symbol.upper()
        if upper_symbol in quote_map:
            quote = dict(quote_map[upper_symbol])
            quote.setdefault("symbol", upper_symbol)
            quote.setdefault("available", True)
            quote.setdefault("source_label", "runtime")
        elif upper_symbol in markdown_map:
            quote = parse_toss_day_market_markdown(markdown_map[upper_symbol], symbol=upper_symbol, source_url=f"runtime://{upper_symbol}")
            quote["available"] = True
        else:
            quote = fetch_toss_day_market_quote(
                upper_symbol,
                stock_code=code_map.get(upper_symbol),
                fetcher=runtime_context.get("toss_fetcher"),
                resolver_fetcher=runtime_context.get("toss_resolver_fetcher"),
                cache_path=runtime_context.get("toss_code_cache_path", DEFAULT_TOSS_STOCK_CODE_CACHE_PATH),
                code_map=code_map,
            )
        quotes.append(quote)

    available_quotes = [quote for quote in quotes if quote.get("available", True) and quote.get("usd_price") is not None]
    if available_quotes:
        first = available_quotes[0]
        pct_text = f" ({first['change_pct']:+.2f}%)" if first.get("change_pct") is not None else ""
        summary = f"토스 데이마켓: {first['symbol']} ${first['usd_price']:.2f}{pct_text}"
    else:
        summary = "토스 데이마켓 가격을 확인하지 못했습니다."

    return {
        "summary": summary,
        "symbols": requested_symbols,
        "quotes": quotes,
        "focus_lines": [_format_day_market_focus(quote) for quote in quotes],
        "next_actions": [
            "데이마켓/주간거래는 국내 브로커별 호가·스프레드·체결 가능 수량 차이를 실매매 전 호가/스프레드 화면에서 확인",
            "Yahoo 정규장/프리·애프터 가격과 혼동 금지: 이 값은 Toss 공개 페이지 기반 보조 가격",
            "가격이 비거나 실패하면 Toss 페이지 구조 변경/공개 접근 제한 가능성이 있어 앱 현재가로 재확인",
        ],
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
