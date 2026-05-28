#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable
try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.main import build_response
from src.telegram_notify import (
    TELEGRAM_TEXT_LIMIT,
    TelegramConfig,
    build_telegram_payload,
    load_telegram_config,
    send_telegram_message,
    summarize_telegram_result,
)


ResponseBuilder = Callable[[], dict[str, Any]]
Sender = Callable[[dict[str, Any], TelegramConfig], dict[str, Any]]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Send 5-minute sector-strength/regime alerts to Telegram")
    parser.add_argument("--interval-seconds", type=int, default=300, help="alert interval; default 300 seconds")
    parser.add_argument("--once", action="store_true", help="send one alert and exit")
    parser.add_argument("--dry-run", action="store_true", help="print sanitized Telegram payload without real send")
    parser.add_argument("--env-file", default=os.getenv("TELEGRAM_ENV_FILE"), help="Telegram env file path")
    parser.add_argument("--timeout-seconds", type=int, default=15, help="Telegram send timeout")
    parser.add_argument("--json", action="store_true", dest="as_json", help="print sanitized JSON result")
    parser.add_argument("--market-hours-only", action="store_true", help="send only during US regular market hours")
    parser.add_argument("--change-only", action="store_true", help="send only when alert signature changes or cooldown expires")
    parser.add_argument("--cooldown-seconds", type=int, default=900, help="minimum repeat interval for unchanged alerts; default 900 seconds")
    parser.add_argument("--state-file", default=str(ROOT / "logs" / "sector_strength_alert_state.json"), help="state file for change-only/cooldown")
    parser.add_argument("--mode", choices=["sector_strength", "oil_vix", "market_regime"], default="sector_strength", help="alert payload mode; oil_vix is for VIX/WTI spike alerts")
    parser.add_argument("--trigger-only", action="store_true", help="send only when the selected mode has explicit trigger alerts")
    return parser


def build_sector_response() -> dict[str, Any]:
    response = build_response('{"mode":"sector_strength","request":"장중 섹터 강약 5분 알림"}')
    response = _enrich_sector_response_with_theme_news(response)
    response = _enrich_sector_response_with_symbol_issues(response)
    return _rerank_sector_response_with_llm(response)


def build_oil_vix_response() -> dict[str, Any]:
    return build_response('{"mode":"oil_vix","request":"VIX/WTI 급등 감시 알림"}')


def build_market_regime_response() -> dict[str, Any]:
    return build_response('{"mode":"market_regime","request":"장 분위기 급변 감시 알림"}')


def response_builder_for_mode(mode: str) -> ResponseBuilder:
    if mode == "oil_vix":
        return build_oil_vix_response
    if mode == "market_regime":
        return build_market_regime_response
    return build_sector_response


YAHOO_FINANCE_SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"
SYMBOL_ISSUE_CACHE_VERSION = 5
THEME_NEWS_CACHE_VERSION = 4
GENERIC_COMPANY_WORDS = {
    "the",
    "and",
    "inc",
    "corp",
    "corporation",
    "company",
    "co",
    "ltd",
    "limited",
    "plc",
    "holdings",
    "holding",
    "group",
    "class",
    "common",
    "stock",
    "ordinary",
    "shares",
    "technologies",
    "technology",
}


def _env_flag(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off", ""}


def _env_int(name: str, default: int, minimum: int = 0, maximum: int | None = None) -> int:
    try:
        value = int(str(os.getenv(name, default)).strip())
    except (TypeError, ValueError):
        value = default
    value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _symbol_issues_enabled() -> bool:
    return _env_flag("SECTOR_ALERT_ENABLE_SYMBOL_ISSUES", False)


def _theme_news_enabled() -> bool:
    return _env_flag("SECTOR_ALERT_ENABLE_THEME_NEWS", True)


def _symbol_issue_cache_file() -> Path:
    raw = os.getenv("SECTOR_ALERT_SYMBOL_ISSUE_CACHE_FILE")
    return Path(raw) if raw else ROOT / "logs" / "sector_symbol_issue_cache.json"


def _theme_news_cache_file() -> Path:
    raw = os.getenv("SECTOR_ALERT_THEME_NEWS_CACHE_FILE")
    return Path(raw) if raw else ROOT / "logs" / "sector_theme_news_cache.json"


def _load_symbol_issue_cache() -> dict[str, Any]:
    path = _symbol_issue_cache_file()
    if not path.exists():
        return {"version": SYMBOL_ISSUE_CACHE_VERSION, "items": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"version": SYMBOL_ISSUE_CACHE_VERSION, "items": {}}
    if not isinstance(payload, dict) or payload.get("version") != SYMBOL_ISSUE_CACHE_VERSION or not isinstance(payload.get("items"), dict):
        return {"version": SYMBOL_ISSUE_CACHE_VERSION, "items": {}}
    payload["version"] = SYMBOL_ISSUE_CACHE_VERSION
    return payload


def _save_symbol_issue_cache(cache: dict[str, Any]) -> None:
    path = _symbol_issue_cache_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        return


def _load_theme_news_cache() -> dict[str, Any]:
    path = _theme_news_cache_file()
    if not path.exists():
        return {"version": THEME_NEWS_CACHE_VERSION, "items": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"version": THEME_NEWS_CACHE_VERSION, "items": {}}
    if not isinstance(payload, dict) or payload.get("version") != THEME_NEWS_CACHE_VERSION or not isinstance(payload.get("items"), dict):
        return {"version": THEME_NEWS_CACHE_VERSION, "items": {}}
    payload["version"] = THEME_NEWS_CACHE_VERSION
    return payload


def _save_theme_news_cache(cache: dict[str, Any]) -> None:
    path = _theme_news_cache_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        return


def _cached_symbol_issue(cache: dict[str, Any], symbol: str, now: datetime, ttl_seconds: int) -> tuple[bool, str]:
    items = cache.get("items") if isinstance(cache.get("items"), dict) else {}
    entry = items.get(symbol.upper()) if isinstance(items, dict) else None
    if not isinstance(entry, dict):
        return False, ""
    cached_at = str(entry.get("cached_at") or "")
    try:
        cached_dt = datetime.fromisoformat(cached_at.replace("Z", "+00:00"))
    except Exception:
        return False, ""
    if (_to_utc(now) - _to_utc(cached_dt)).total_seconds() > ttl_seconds:
        return False, ""
    return True, str(entry.get("issue") or "").strip()


def _write_cached_symbol_issue(cache: dict[str, Any], symbol: str, issue: str, now: datetime) -> None:
    items = cache.setdefault("items", {})
    if not isinstance(items, dict):
        items = {}
        cache["items"] = items
    items[symbol.upper()] = {"cached_at": _to_utc(now).isoformat(), "issue": issue.strip()}


def _cached_theme_news(cache: dict[str, Any], symbol: str, now: datetime, ttl_seconds: int) -> tuple[bool, list[dict[str, Any]]]:
    items = cache.get("items") if isinstance(cache.get("items"), dict) else {}
    entry = items.get(symbol.upper()) if isinstance(items, dict) else None
    if not isinstance(entry, dict):
        return False, []
    cached_at = str(entry.get("cached_at") or "")
    try:
        cached_dt = datetime.fromisoformat(cached_at.replace("Z", "+00:00"))
    except Exception:
        return False, []
    if (_to_utc(now) - _to_utc(cached_dt)).total_seconds() > ttl_seconds:
        return False, []
    raw_hits = entry.get("hits")
    if not isinstance(raw_hits, list):
        return True, []
    return True, [hit for hit in raw_hits if isinstance(hit, dict)]


def _write_cached_theme_news(cache: dict[str, Any], symbol: str, hits: list[dict[str, Any]], now: datetime) -> None:
    items = cache.setdefault("items", {})
    if not isinstance(items, dict):
        items = {}
        cache["items"] = items
    items[symbol.upper()] = {"cached_at": _to_utc(now).isoformat(), "hits": hits}


def _clean_issue_text(text: Any, max_chars: int = 150) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip(" -/\t\r\n")
    if len(cleaned) <= max_chars:
        return cleaned
    cut = cleaned[:max_chars].rstrip()
    for sep in (" — ", " - ", ": ", "; ", ". ", ", "):
        idx = cut.rfind(sep)
        if idx >= 70:
            cut = cut[:idx].rstrip(" -:;,.")
            break
    return cut.strip()


def _company_tokens_from_quotes(quotes: Any, symbol: str) -> list[str]:
    symbol_upper = symbol.upper()
    names: list[str] = []
    if isinstance(quotes, list):
        for quote in quotes:
            if not isinstance(quote, dict):
                continue
            if str(quote.get("symbol") or "").upper() != symbol_upper:
                continue
            for key in ("longname", "shortname"):
                name = str(quote.get(key) or "").strip()
                if name:
                    names.append(name)
            break
    tokens: list[str] = []
    for name in names:
        for token in re.findall(r"[a-z0-9]+", name.lower()):
            if len(token) < 4 or token in GENERIC_COMPANY_WORDS:
                continue
            tokens.append(token)
    return list(dict.fromkeys(tokens))


def _clean_company_display_name(name: str, symbol: str) -> str:
    cleaned = re.sub(
        r"\b(Inc\.?|Corporation|Corp\.?|Company|Co\.?|Ltd\.?|Limited|PLC|Holdings?|Group|Class\s+[A-Z]|Common Stock|Stock)\b",
        "",
        name,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned.replace(",", " ")).strip(" -")
    cleaned = re.sub(r"^(Is|Are|Can|Could|Will|Would|Why|How|What|If)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+\.", "", cleaned).strip(" .,-")
    return cleaned or symbol.upper()


def _company_name_from_quotes(quotes: Any, symbol: str) -> str:
    symbol_upper = symbol.upper()
    if isinstance(quotes, list):
        for quote in quotes:
            if not isinstance(quote, dict):
                continue
            if str(quote.get("symbol") or "").upper() != symbol_upper:
                continue
            name = str(quote.get("longname") or quote.get("shortname") or "").strip()
            if name:
                return _clean_company_display_name(name, symbol_upper)
    return symbol_upper


def _headline_company_hint(title: str, fallback: str) -> str:
    match = re.search(r"\b([A-Z][A-Za-z0-9&.\- ]{2,60})\s+\(([A-Z][A-Z0-9.\-]{0,9})\)", title)
    if match:
        hint = re.sub(r"^(Is|Are|Can|Could|Will|Would|Why|How|What|If)\s+", "", match.group(1).strip(), flags=re.IGNORECASE)
        return _clean_company_display_name(hint, fallback)
    return fallback


def _headline_topic_phrases(title_lower: str) -> list[str]:
    phrases: list[str] = []
    checks = [
        (("spacex", "ipo"), "SpaceX IPO 기대감"),
        (("ai", "data"), "AI 데이터센터"),
        (("data center",), "데이터센터"),
        (("data campus",), "데이터센터 캠퍼스"),
        (("acquir",), "인수"),
        (("manufacturing hub",), "생산거점 확장"),
        (("silicon facility",), "실리콘 시설"),
        (("restart",), "재가동"),
        (("price target",), "목표가 조정"),
        (("analyst",), "애널리스트 평가"),
        (("bullish",), "긍정 평가"),
        (("short-seller",), "공매도 의혹"),
        (("earnings",), "실적"),
        (("profitability",), "수익성 개선"),
        (("loss",), "적자 축소"),
        (("memory",), "메모리 수요"),
        (("ai boom",), "AI 수요"),
        (("rare earth",), "희토류"),
        (("lunar",), "달 탐사"),
        (("orbital",), "궤도 사업"),
        (("space",), "우주 관련주"),
    ]
    for tokens, phrase in checks:
        if all(token in title_lower for token in tokens) and phrase not in phrases:
            phrases.append(phrase)
    return phrases


def _koreanize_yahoo_news_title(symbol: str, title: str, company_name: str) -> str:
    clean_title = _clean_issue_text(title, max_chars=240)
    company = _headline_company_hint(clean_title, company_name)
    lower = clean_title.lower()

    if "spacex" in lower and "ipo" in lower:
        if "space" in lower or "rocket" in lower or "satellite" in lower:
            return f"{company} 등 우주 관련주가 SpaceX IPO 기대감에 상승"
        return f"{company}가 SpaceX IPO 기대감 관련 뉴스로 부각"
    if ("ai data campus" in lower or "data campus" in lower or "data center" in lower) and ("acquir" in lower or "announc" in lower):
        return f"{company}가 AI 데이터센터 캠퍼스 확보 소식에 상승"
    if "manufacturing hub" in lower and ("expand" in lower or "expanding" in lower):
        if "lunar" in lower or "orbital" in lower:
            return f"{company}가 달·궤도 사업 생산거점 확장 소식에 상승"
        return f"{company}가 생산거점 확장 소식에 상승"
    if "silicon facility" in lower and ("restart" in lower or "restarting" in lower):
        return f"{company}가 실리콘 시설 재가동 기대감으로 강세"
    if "price target" in lower:
        if "triple" in lower or "boost" in lower or "raise" in lower or "raised" in lower:
            return f"{company}가 목표가 대폭 상향 영향으로 부각"
        return f"{company} 목표가 조정 뉴스 부각"
    if "short-seller" in lower and "bullish" in lower:
        return f"{company}가 공매도 의혹에도 긍정 평가가 나오며 급등"
    if "profitability" in lower and ("loss" in lower or "losses" in lower):
        return f"{company}가 적자 축소와 수익성 개선 기대감으로 부각"
    if "memory" in lower and ("micron" in lower or symbol.upper() == "MU"):
        return f"{company}가 AI 메모리 수요 기대감으로 강세"
    if "earnings" in lower and "ai boom" in lower:
        return f"{company}가 AI 수요 속 저평가 논리로 부각"
    if "rare earth" in lower and symbol.upper() == "USAR":
        return f"{company}가 희토류 장기 성장 가능성 뉴스로 부각"

    action = ""
    if any(word in lower for word in ("surge", "surges", "soar", "soars", "jump", "jumps", "rally", "rallies", "rise", "rises", "gain", "gains", "up ")):
        action = "상승"
    topics = _headline_topic_phrases(lower)
    if topics and action:
        return f"{company}가 {'·'.join(topics[:3])} 이슈로 {action}"
    if topics:
        return f"{company} 관련 {'·'.join(topics[:3])} 이슈 부각"
    if action:
        return f"{company} 상승 관련 뉴스 부각"
    return f"{company} 관련 뉴스 부각"


def _yahoo_news_score(item: dict[str, Any], symbol: str, company_tokens: list[str]) -> tuple[int, int]:
    title = str(item.get("title") or "")
    title_lower = title.lower()
    related = {
        str(ticker).upper()
        for ticker in item.get("relatedTickers", [])
        if str(ticker).strip()
    } if isinstance(item.get("relatedTickers"), list) else set()
    direct = symbol.upper() in related
    token_hit = any(token in title_lower for token in company_tokens)
    if not direct and not token_hit:
        return (-1, 0)
    score = 0
    if direct:
        score += 100
    if token_hit:
        score += 80
    if direct and len(related) <= 3:
        score += 15
    if len(related) > 6 and not token_hit:
        score -= 35
    try:
        published = int(item.get("providerPublishTime") or 0)
    except (TypeError, ValueError):
        published = 0
    return score, published


def _select_yahoo_news_issue(symbol: str, payload: dict[str, Any]) -> str:
    news = payload.get("news") if isinstance(payload.get("news"), list) else []
    if not news:
        return ""
    company_tokens = _company_tokens_from_quotes(payload.get("quotes"), symbol)
    ranked: list[tuple[tuple[int, int], dict[str, Any]]] = []
    for item in news:
        if not isinstance(item, dict) or not item.get("title"):
            continue
        score = _yahoo_news_score(item, symbol, company_tokens)
        if score[0] < 0:
            continue
        ranked.append((score, item))
    if not ranked:
        return ""
    _score, selected = max(ranked, key=lambda row: row[0])
    title = str(selected.get("title") or "").strip()
    if not title:
        return ""
    company_name = _company_name_from_quotes(payload.get("quotes"), symbol)
    korean_title = _koreanize_yahoo_news_title(symbol, title, company_name)
    return f"뉴스 - {korean_title}"


LOW_SIGNAL_THEME_NEWS_MARKERS = (
    "stock market today",
    "sector update",
    "markets wrap",
    "weekly wrap",
    "live coverage",
    "high growth tech stocks",
    "under-the-radar",
    "unpopular stocks",
    "trending stock",
    "buy and hold for decades",
    "make you a millionaire",
    "what to know beyond why",
)


THEME_NEWS_TOPIC_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("spacex", "ipo"), "SpaceX IPO 기대감"),
    (("rocket", "satellite"), "로켓·위성주 동반 강세"),
    (("space stocks", "soar"), "우주주 동반 강세"),
    (("space-related stocks",), "우주 관련주 동반 강세"),
    (("profitability", "loss"), "수익성 개선 기대"),
    (("short-seller", "bullish"), "공매도 리포트 후 긍정 평가"),
    (("short-seller",), "공매도 리포트"),
    (("silicon-28", "restart"), "실리콘-28 시설 재가동"),
    (("silicon facility", "restart"), "실리콘 시설 재가동"),
    (("rare earth",), "희토류 공급망 이슈"),
    (("price target", "triple"), "목표가 대폭 상향"),
    (("price target", "boost"), "목표가 상향"),
    (("price target", "raise"), "목표가 상향"),
    (("price target", "raised"), "목표가 상향"),
    (("price target",), "목표가 조정"),
    (("market cap",), "시가총액 재평가"),
    (("memory melt-up",), "메모리주 동반 강세"),
    (("memory", "micron"), "AI 메모리 수요"),
    (("ai", "memory"), "AI 메모리 수요"),
    (("power chip",), "전력반도체 동반 강세"),
    (("guidance boost",), "가이던스 상향"),
    (("ai data campus",), "AI 데이터센터 캠퍼스 확보"),
    (("data campus",), "데이터센터 캠퍼스 확보"),
    (("data center", "campus"), "데이터센터 캠퍼스 확보"),
    (("bitcoin miner", "ai infrastructure"), "채굴주 AI 인프라 전환"),
    (("bitcoin miner stocks", "nvidia"), "채굴주 AI 수혜 기대"),
    (("bitcoin", "miner"), "비트코인 채굴주 이슈"),
    (("robotaxi", "revenue outlook"), "로보택시 매출 전망 상향"),
    (("fleet targets",), "로보택시 운행 규모 확대"),
    (("ai infrastructure", "buildout"), "AI 인프라 투자 기대"),
    (("ai infrastructure",), "AI 인프라 수요"),
    (("stablecoin pilot",), "스테이블코인 실증"),
    (("quantum", "stablecoin"), "양자·스테이블코인 실증"),
    (("post quantum",), "포스트퀀텀 보안"),
    (("ai robotics",), "AI 로보틱스"),
    (("semiconductor industrial project",), "반도체 산업 프로젝트"),
    (("global demand for ai infrastructure",), "AI 인프라 수요"),
    (("weight drug",), "비만치료제 수요"),
    (("ozempic",), "GLP-1 소비 영향"),
    (("glp-1",), "GLP-1 이슈"),
    (("flat sales", "weaker revenue"), "매출 둔화 우려"),
    (("weaker revenue",), "매출 둔화 우려"),
    (("earnings transcript",), "실적 발표"),
    (("earnings report",), "실적 이후 흐름"),
    (("q1", "forecasts"), "분기 실적 예상 상회"),
    (("revenue outlook",), "매출 전망 상향"),
    (("acquiring",), "자산 인수"),
    (("acquires",), "자산 인수"),
    (("valuation",), "밸류에이션 재평가"),
)


def _theme_news_topics(title_lower: str) -> list[str]:
    topics: list[str] = []
    for tokens, phrase in THEME_NEWS_TOPIC_RULES:
        if all(token in title_lower for token in tokens) and phrase not in topics:
            topics.append(phrase)
    return topics


def _price_target_direction_text(title: str) -> str:
    text = str(title or "")
    lower = text.lower()

    def money(value: str) -> str:
        numeric = float(value.replace(",", ""))
        if numeric.is_integer():
            return f"${int(numeric)}"
        return f"${numeric:g}"

    def direction_from_values(new_value: str, old_value: str) -> str:
        new_number = float(new_value.replace(",", ""))
        old_number = float(old_value.replace(",", ""))
        move = f"{money(old_value)}→{money(new_value)}"
        if new_number > old_number:
            return f"목표가 상향({move})"
        if new_number < old_number:
            return f"목표가 하향({move})"
        return f"목표가 유지({move})"

    to_from = re.search(
        r"\bto\s+\$?([0-9][0-9,]*(?:\.\d+)?)\s+from\s+\$?([0-9][0-9,]*(?:\.\d+)?)",
        text,
        flags=re.IGNORECASE,
    )
    if to_from:
        return direction_from_values(to_from.group(1), to_from.group(2))

    from_to = re.search(
        r"\bfrom\s+\$?([0-9][0-9,]*(?:\.\d+)?)\s+to\s+\$?([0-9][0-9,]*(?:\.\d+)?)",
        text,
        flags=re.IGNORECASE,
    )
    if from_to:
        return direction_from_values(from_to.group(2), from_to.group(1))

    if any(word in lower for word in ("triple", "doubles", "double price target")):
        return "목표가 대폭 상향"
    if any(word in lower for word in ("boost", "raise", "raised", "raises", "hike", "hiked", "hikes", "lift", "lifts", "lifted", "ups price target", "increases price target")):
        return "목표가 상향"
    if any(word in lower for word in ("cut", "cuts", "lower", "lowers", "lowered", "trim", "trims", "trimmed", "reduce", "reduces", "reduced")):
        return "목표가 하향"
    if any(word in lower for word in ("maintain", "maintains", "maintained", "reiterate", "reiterates", "reiterated")):
        return "목표가 유지"
    return ""


def _theme_news_detail_for_title(symbol: str, title: str, topics: list[str]) -> str:
    lower = title.lower()
    symbol_upper = symbol.upper()
    if "spacex" in lower and "ipo" in lower:
        if "files" in lower or "filed" in lower or "upcoming" in lower:
            return "SpaceX IPO 신청 뉴스로 우주·위성주 전반에 매수세"
        return "SpaceX IPO 기대감으로 우주·위성주 전반에 매수세"
    if "profitability" in lower and ("loss" in lower or "losses" in lower):
        return "적자 축소와 수익성 개선 기대가 부각"
    if "expanded lonestar" in lower or ("lonestar" in lower and "deal" in lower):
        return "Lonestar 계약 확대와 차세대 플랫폼 진전으로 재평가"
    if "short-seller" in lower and "bullish" in lower:
        return "공매도 리포트 이후에도 긍정 평가가 나오며 반등 재료"
    if "short-seller" in lower and ("backing" in lower or "reiterates" in lower):
        return "공매도 리포트 이후 증권사 방어성 평가가 붙음"
    if "silicon-28" in lower and ("restart" in lower or "restarts" in lower):
        return "Silicon-28 농축시설 일부 재가동과 2026년 3분기 출하 기대"
    if "silicon facility" in lower and ("restart" in lower or "restarting" in lower):
        return "실리콘 시설 재가동 기대가 붙음"
    if "rare earth" in lower:
        return "미국 내 희토류 공급망 재편 기대가 부각"
    if "made in america" in lower:
        return "미국 제조·공급망 재편 이슈가 희토류주 관심으로 연결"
    if "price target" in lower:
        target_direction = _price_target_direction_text(title)
        if target_direction:
            if "하향" in target_direction:
                return f"{target_direction}으로 투자심리 부담"
            if "유지" in target_direction:
                return f"{target_direction}로 기존 평가 유지"
            if "micron" in lower or symbol_upper in {"MU", "SNDK", "WDC", "STX"}:
                return f"{target_direction}으로 AI 메모리 성장성 재평가"
            return f"{target_direction}으로 투자심리 개선"
        return ""
    if "memory melt-up" in lower:
        return "Micron 급등 영향으로 메모리·스토리지주 동반 강세"
    if "market cap" in lower and "micron" in lower:
        return "Micron 시가총액 재평가가 메모리 밸류체인으로 확산"
    if "power chip" in lower or "guidance boost" in lower:
        return "전력반도체 가이던스 개선 기대가 주변 칩주로 확산"
    if "ai data campus" in lower or "data campus" in lower:
        if "kentucky" in lower or "muskie" in lower or "1 gw" in lower:
            return "켄터키 1GW AI 데이터센터 캠퍼스 확보로 인프라 전환 기대"
        return "AI 데이터센터 캠퍼스 확보로 인프라 전환 기대"
    if "bitcoin miner" in lower and ("nvidia" in lower or "ai" in lower):
        return "비트코인 채굴주가 AI 인프라 수혜 후보로 재평가"
    if "finance chief" in lower and "ai infrastructure" in lower:
        return "재무 책임자 교체와 AI 인프라 전환 스토리 부각"
    if "self-funded water project" in lower:
        return "자체 자금 인프라 프로젝트로 데이터센터 확장 여력 점검"
    if "robotaxi" in lower and ("revenue outlook" in lower or "fleet targets" in lower):
        return "로보택시 매출 전망과 운행대수 목표 상향"
    if "q1" in lower and "forecasts" in lower:
        return "분기 실적 예상 상회와 가이던스 개선"
    if "ai infrastructure buildout" in lower or ("ai infrastructure" in lower and "betting" in lower):
        return "AI 인프라 증설 사이클에 대한 기관 매수 기대"
    if "ntm sales outlook" in lower or "scale-up potential" in lower:
        return "AI 컴퓨팅 수요 기반 매출 확대 가능성 부각"
    if "stablecoin pilot" in lower:
        return "한국 은행권 스테이블코인 실증 참여로 양자 보안 기대"
    if "post quantum" in lower:
        return "포스트퀀텀 보안과 AI 로보틱스 적용 기대"
    if "semiconductor industrial project" in lower:
        return "유럽 반도체 산업 프로젝트 입지 선정으로 사업 확장 기대"
    if "global demand for ai infrastructure" in lower:
        return "AI 인프라 수요 확대를 회사 성장 재료로 제시"
    if "earnings report" in lower:
        return "실적 발표 이후 주가 재평가 흐름"
    if "weight drug" in lower or "ozempic" in lower:
        return "GLP-1 비만치료제 확산이 소비·헬스케어 수요 변화로 연결"
    if "flat sales" in lower or "weaker revenue" in lower:
        return "매출 정체와 사용자당 매출 약화 우려"
    if "valuation" in lower:
        if "expanded lonestar" in lower or "next generation platforms" in lower:
            return "계약 확대와 차세대 플랫폼 진전으로 밸류에이션 재점검"
        return ""
    if topics:
        return f"{'·'.join(topics[:2])} 관련 재료 부각"
    return ""


def _is_low_signal_theme_news_title(title_lower: str) -> bool:
    return any(marker in title_lower for marker in LOW_SIGNAL_THEME_NEWS_MARKERS)


def _select_yahoo_theme_news_hits(symbol: str, payload: dict[str, Any], max_hits: int = 3) -> list[dict[str, Any]]:
    news = payload.get("news") if isinstance(payload.get("news"), list) else []
    if not news:
        return []
    company_tokens = _company_tokens_from_quotes(payload.get("quotes"), symbol)
    ranked: list[tuple[tuple[int, int], dict[str, Any]]] = []
    for item in news:
        if not isinstance(item, dict) or not item.get("title"):
            continue
        title = _clean_issue_text(item.get("title"), max_chars=240)
        title_lower = title.lower()
        if _is_low_signal_theme_news_title(title_lower):
            continue
        topics = _theme_news_topics(title_lower)
        if not topics:
            continue
        detail = _theme_news_detail_for_title(symbol, title, topics)
        if not detail:
            continue
        score, published = _yahoo_news_score(item, symbol, company_tokens)
        if score < 0:
            continue
        related = item.get("relatedTickers") if isinstance(item.get("relatedTickers"), list) else []
        symbol_in_title = symbol.upper() in re.findall(r"\b[A-Z][A-Z0-9.\-]{0,9}\b", title)
        token_hit = any(token in title_lower for token in company_tokens)
        if len(related) > 8 and not symbol_in_title and not token_hit and not any("동반 강세" in topic for topic in topics):
            continue
        score += 30 * min(len(topics), 3)
        if symbol_in_title or token_hit:
            score += 40
        summary = "·".join(topics[:2])
        hit = {
            "symbol": symbol.upper(),
            "topic": topics[0],
            "summary": summary,
            "detail": detail,
            "published": published,
            "score": score,
        }
        ranked.append(((score, published), hit))
    ranked.sort(key=lambda row: row[0], reverse=True)
    hits: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for _rank, hit in ranked:
        marker = (str(hit.get("symbol") or ""), str(hit.get("topic") or ""))
        if marker in seen:
            continue
        seen.add(marker)
        hits.append(hit)
        if len(hits) >= max_hits:
            break
    return hits


def _fetch_yahoo_symbol_issue(symbol: str, timeout: int) -> str:
    params = {
        "q": symbol.upper(),
        "quotesCount": 5,
        "newsCount": 10,
        "listsCount": 0,
        "enableFuzzyQuery": "false",
    }
    url = f"{YAHOO_FINANCE_SEARCH_URL}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return ""
    return _select_yahoo_news_issue(symbol, payload if isinstance(payload, dict) else {})


def _fetch_yahoo_symbol_theme_news(symbol: str, timeout: int) -> list[dict[str, Any]]:
    params = {
        "q": symbol.upper(),
        "quotesCount": 5,
        "newsCount": 10,
        "listsCount": 0,
        "enableFuzzyQuery": "false",
    }
    url = f"{YAHOO_FINANCE_SEARCH_URL}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return []
    return _select_yahoo_theme_news_hits(symbol, payload if isinstance(payload, dict) else {})


def _format_sec_symbol_issue(symbol: str, filing: dict[str, Any]) -> str:
    form = _clean_issue_text(filing.get("form"), max_chars=20)
    filing_date = _clean_issue_text(filing.get("filing_date"), max_chars=20)
    description = _clean_issue_text(filing.get("description") or filing.get("primary_document"), max_chars=70)
    if form.upper() == "8-K":
        label = "공식 이벤트 공시"
    elif form.upper() in {"10-Q", "10-K"}:
        label = "정기보고서"
    elif form.upper() in {"S-3", "S-1", "424B5", "424B3"}:
        label = "증권신고서"
    elif form.upper() in {"13F-HR", "SC 13G", "SC 13D"}:
        label = "지분 공시"
    else:
        label = "공식 공시"
    date_part = f" {filing_date}" if filing_date else ""
    desc_part = f" - {description}" if description and description.upper() != form.upper() else ""
    return f"SEC {symbol.upper()} {form}{date_part} {label}{desc_part}".strip()


def _fetch_sec_symbol_issue(symbol: str, timeout: int) -> str:
    try:
        from src.us.news.sec_filings import fetch_sec_filings_pack
    except Exception:
        return ""
    try:
        pack = fetch_sec_filings_pack(symbol, limit=2, timeout=timeout)
    except Exception:
        return ""
    filings = pack.get("filings") if isinstance(pack, dict) and isinstance(pack.get("filings"), list) else []
    if not filings:
        return ""
    first = filings[0]
    return _format_sec_symbol_issue(symbol, first) if isinstance(first, dict) else ""


def _fetch_alert_symbol_issue(symbol: str) -> str:
    timeout = _env_int("SECTOR_ALERT_SYMBOL_ISSUE_TIMEOUT_SECONDS", 8, minimum=2, maximum=30)
    if _env_flag("SECTOR_ALERT_ENABLE_YAHOO_NEWS_ISSUES", True):
        issue = _fetch_yahoo_symbol_issue(symbol, timeout=timeout)
        if issue:
            return issue
    if _env_flag("SECTOR_ALERT_ENABLE_SEC_ISSUES", True):
        return _fetch_sec_symbol_issue(symbol, timeout=timeout)
    return ""


def _sector_issue_symbols(report: dict[str, Any], max_symbols: int) -> list[str]:
    ordered: list[str] = []

    def add(symbol: Any) -> None:
        text = str(symbol or "").upper().strip()
        if text and text not in ordered:
            ordered.append(text)

    for collection in ("strong_themes", "weak_themes"):
        rows = report.get(collection)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            leaders = row.get("leaders")
            if not isinstance(leaders, list):
                continue
            for leader in leaders:
                if isinstance(leader, dict):
                    add(leader.get("symbol"))
                if len(ordered) >= max_symbols:
                    return ordered

    movers = report.get("watchlist_movers")
    if isinstance(movers, list):
        for row in movers:
            if isinstance(row, dict):
                add(row.get("symbol"))
            if len(ordered) >= max_symbols:
                return ordered
    return ordered


def _build_alert_symbol_issue_lookup(symbols: list[str]) -> dict[str, str]:
    if not symbols or not _symbol_issues_enabled():
        return {}
    ttl_seconds = _env_int("SECTOR_ALERT_SYMBOL_ISSUE_TTL_SECONDS", 1800, minimum=0)
    now = _now_utc()
    cache = _load_symbol_issue_cache()
    issues: dict[str, str] = {}
    changed = False
    for symbol in symbols:
        symbol_upper = symbol.upper().strip()
        if not symbol_upper:
            continue
        hit, cached_issue = _cached_symbol_issue(cache, symbol_upper, now, ttl_seconds)
        if hit:
            if cached_issue:
                issues[symbol_upper] = cached_issue
            continue
        issue = _fetch_alert_symbol_issue(symbol_upper)
        _write_cached_symbol_issue(cache, symbol_upper, issue, now)
        changed = True
        if issue:
            issues[symbol_upper] = issue
    if changed:
        _save_symbol_issue_cache(cache)
    return issues


def _theme_news_rows(report: dict[str, Any], max_themes: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    grouped: list[list[dict[str, Any]]] = []
    for collection in ("strong_themes", "weak_themes"):
        raw_rows = report.get(collection)
        grouped.append([row for row in raw_rows if isinstance(row, dict)] if isinstance(raw_rows, list) else [])
    index = 0
    while len(rows) < max_themes and any(index < len(group) for group in grouped):
        for group in grouped:
            if index >= len(group):
                continue
            row = group[index]
            key = str(row.get("key") or row.get("name") or "").strip()
            if key and key not in seen:
                seen.add(key)
                rows.append(row)
                if len(rows) >= max_themes:
                    return rows
        index += 1
    return rows


def _theme_news_leader_symbols(row: dict[str, Any], max_symbols: int) -> list[str]:
    symbols: list[str] = []
    leaders = row.get("leaders")
    if isinstance(leaders, list):
        for leader in leaders:
            if isinstance(leader, dict):
                symbol = str(leader.get("symbol") or "").upper().strip()
                if symbol and symbol not in symbols:
                    symbols.append(symbol)
            if len(symbols) >= max_symbols:
                return symbols
    constituents = row.get("constituents")
    if isinstance(constituents, list):
        for constituent in constituents:
            if isinstance(constituent, dict):
                symbol = str(constituent.get("symbol") or "").upper().strip()
                if symbol and symbol not in symbols:
                    symbols.append(symbol)
            if len(symbols) >= max_symbols:
                return symbols
    return symbols


def _build_symbol_theme_news_hits(symbols: list[str]) -> dict[str, list[dict[str, Any]]]:
    if not symbols:
        return {}
    ttl_seconds = _env_int("SECTOR_ALERT_THEME_NEWS_TTL_SECONDS", 1800, minimum=0)
    timeout = _env_int("SECTOR_ALERT_THEME_NEWS_TIMEOUT_SECONDS", 5, minimum=2, maximum=20)
    now = _now_utc()
    cache = _load_theme_news_cache()
    changed = False
    lookup: dict[str, list[dict[str, Any]]] = {}
    for symbol in symbols:
        symbol_upper = symbol.upper().strip()
        if not symbol_upper:
            continue
        hit, cached_hits = _cached_theme_news(cache, symbol_upper, now, ttl_seconds)
        if hit:
            lookup[symbol_upper] = cached_hits
            continue
        hits = _fetch_yahoo_symbol_theme_news(symbol_upper, timeout=timeout)
        _write_cached_theme_news(cache, symbol_upper, hits, now)
        lookup[symbol_upper] = hits
        changed = True
    if changed:
        _save_theme_news_cache(cache)
    return lookup


def _theme_news_summary_from_hits(hits: list[dict[str, Any]], max_topics: int) -> str:
    ranked = sorted(
        (hit for hit in hits if isinstance(hit, dict) and (hit.get("detail") or hit.get("topic")) and hit.get("symbol")),
        key=lambda hit: (int(hit.get("score") or 0), int(hit.get("published") or 0)),
        reverse=True,
    )
    clusters: dict[str, list[str]] = {}
    cluster_scores: dict[str, tuple[int, int]] = {}
    for hit in ranked:
        detail = _clean_issue_text(hit.get("detail") or hit.get("topic"), max_chars=95)
        symbol = str(hit.get("symbol") or "").upper().strip()
        if not detail or not symbol:
            continue
        symbols = clusters.setdefault(detail, [])
        if symbol not in symbols:
            symbols.append(symbol)
        rank = (int(hit.get("score") or 0), int(hit.get("published") or 0))
        cluster_scores[detail] = max(cluster_scores.get(detail, (0, 0)), rank)
    if not clusters:
        return ""
    ordered_details = sorted(clusters, key=lambda detail: cluster_scores.get(detail, (0, 0)), reverse=True)
    parts: list[str] = []
    for detail in ordered_details[:max_topics]:
        symbols = "·".join(clusters[detail][:3])
        parts.append(f"{detail}({symbols})" if symbols else detail)
    return ". ".join(parts)


def _build_alert_theme_news_lookup(report: dict[str, Any]) -> dict[str, str]:
    if not _theme_news_enabled():
        return {}
    max_themes = _env_int("SECTOR_ALERT_THEME_NEWS_MAX_THEMES", 12, minimum=0, maximum=12)
    max_symbols_per_theme = _env_int("SECTOR_ALERT_THEME_NEWS_SYMBOLS_PER_THEME", 3, minimum=1, maximum=6)
    max_topics = _env_int("SECTOR_ALERT_THEME_NEWS_TOPICS_PER_THEME", 2, minimum=1, maximum=4)
    rows = _theme_news_rows(report, max_themes=max_themes)
    if not rows:
        return {}
    ordered_symbols: list[str] = []
    symbols_by_theme: dict[str, list[str]] = {}
    for row in rows:
        key = str(row.get("key") or row.get("name") or "").strip()
        if not key:
            continue
        symbols = _theme_news_leader_symbols(row, max_symbols=max_symbols_per_theme)
        symbols_by_theme[key] = symbols
        for symbol in symbols:
            if symbol not in ordered_symbols:
                ordered_symbols.append(symbol)
    symbol_hits = _build_symbol_theme_news_hits(ordered_symbols)
    lookup: dict[str, str] = {}
    for row in rows:
        key = str(row.get("key") or row.get("name") or "").strip()
        name = str(row.get("name") or key).strip()
        if not key:
            continue
        hits: list[dict[str, Any]] = []
        for symbol in symbols_by_theme.get(key, []):
            hits.extend(symbol_hits.get(symbol, []))
        summary = _theme_news_summary_from_hits(hits, max_topics=max_topics)
        if not summary:
            continue
        lookup[key] = summary
        if name:
            lookup[name] = summary
            lookup[_short_theme_label(name)] = summary
    return lookup


def _enrich_sector_response_with_theme_news(response: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(response, dict) or response.get("mode") in {"oil_vix", "market_regime"}:
        return response
    if not _theme_news_enabled():
        return response
    data = response.get("data")
    if not isinstance(data, dict):
        return response
    report = data.get("sector_strength")
    if not isinstance(report, dict):
        return response
    theme_news = _build_alert_theme_news_lookup(report)
    if theme_news:
        report["theme_news"] = theme_news
    return response


def _enrich_sector_response_with_symbol_issues(response: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(response, dict) or response.get("mode") in {"oil_vix", "market_regime"}:
        return response
    if not _symbol_issues_enabled():
        return response
    data = response.get("data")
    if not isinstance(data, dict):
        return response
    report = data.get("sector_strength")
    if not isinstance(report, dict):
        return response
    max_symbols = _env_int("SECTOR_ALERT_MAX_ISSUE_SYMBOLS", 18, minimum=0, maximum=60)
    symbols = _sector_issue_symbols(report, max_symbols=max_symbols)
    issues = _build_alert_symbol_issue_lookup(symbols)
    if issues:
        report["symbol_issues"] = issues
    return response


def _llm_rerank_enabled() -> bool:
    explicit = os.getenv("SECTOR_ALERT_ENABLE_LLM_RERANK")
    if explicit is None:
        explicit = os.getenv("SECTOR_ALERT_LLM_RERANK")
    if explicit is not None:
        return explicit.strip().lower() not in {"0", "false", "no", "off", ""}
    return _llm_auth_available()


def _find_nested_string(value: Any, preferred: tuple[str, ...], min_len: int = 1) -> str:
    if isinstance(value, dict):
        for key in preferred:
            candidate = value.get(key)
            if isinstance(candidate, str) and len(candidate.strip()) >= min_len:
                return candidate.strip()
        for child in value.values():
            found = _find_nested_string(child, preferred, min_len=min_len)
            if found:
                return found
    if isinstance(value, list):
        for child in value:
            found = _find_nested_string(child, preferred, min_len=min_len)
            if found:
                return found
    return ""


def _codex_auth_candidates() -> list[Path]:
    candidates: list[Path] = []
    explicit = os.getenv("SECTOR_ALERT_CODEX_AUTH_FILE")
    if explicit:
        candidates.append(Path(explicit))
    codex_home = os.getenv("CODEX_HOME")
    if codex_home:
        candidates.append(Path(codex_home) / "auth.json")
    for home_var in ("USERPROFILE", "HOME"):
        home = os.getenv(home_var)
        if home:
            candidates.append(Path(home) / ".codex" / "auth.json")
    result: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path)
        if key not in seen:
            result.append(path)
            seen.add(key)
    return result


def _load_codex_oauth() -> dict[str, str]:
    if str(os.getenv("SECTOR_ALERT_LLM_AUTH_MODE") or "").strip().lower() in {"api_key", "apikey", "openai_api_key"}:
        return {}
    for path in _codex_auth_candidates():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        token = _find_nested_string(payload, ("access_token", "oauth_token", "token"), min_len=20)
        if not token:
            continue
        account_id = _find_nested_string(payload, ("account_id", "chatgpt_account_id"), min_len=1)
        return {"access_token": token, "account_id": account_id, "auth_file": str(path)}
    return {}


def _llm_api_key() -> str:
    return str(os.getenv("SECTOR_ALERT_LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()


def _llm_auth_available() -> bool:
    return bool(_load_codex_oauth().get("access_token") or _llm_api_key())


def _llm_base_url() -> str:
    raw = str(os.getenv("SECTOR_ALERT_LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").strip()
    return raw.rstrip("/") or "https://api.openai.com/v1"


def _codex_llm_base_url() -> str:
    raw = str(os.getenv("SECTOR_ALERT_CODEX_BACKEND_URL") or "https://chatgpt.com/backend-api/codex").strip()
    return raw.rstrip("/") or "https://chatgpt.com/backend-api/codex"


def _llm_model(auth_mode: str | None = None) -> str:
    configured = str(os.getenv("SECTOR_ALERT_LLM_MODEL") or "").strip()
    if configured:
        return configured
    if auth_mode == "codex_oauth":
        return "gpt-5.5"
    return "gpt-4.1-mini"


def _llm_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return round(float(str(value).replace(",", "")), 3)
    except (TypeError, ValueError):
        return None


def _llm_bool(value: Any) -> bool:
    numeric = _llm_float(value)
    return numeric is not None and numeric > 0


def _llm_leader_count_bounds() -> tuple[int, int]:
    minimum = _env_int("SECTOR_ALERT_LLM_MIN_LEADERS", 3, minimum=1, maximum=5)
    maximum = _env_int("SECTOR_ALERT_LLM_MAX_LEADERS", 5, minimum=minimum, maximum=5)
    return minimum, maximum


def _leader_candidates_for_llm(row: dict[str, Any], candidate_limit: int) -> list[dict[str, Any]]:
    raw = row.get("leader_candidates")
    if not isinstance(raw, list) or not raw:
        raw = row.get("leaders")
    if not isinstance(raw, list) or not raw:
        raw = row.get("constituents")
    if not isinstance(raw, list):
        return []
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    ordered = sorted(
        [item for item in raw if isinstance(item, dict)],
        key=lambda item: (
            _llm_float(item.get("leader_score")) if _llm_float(item.get("leader_score")) is not None else -1.0,
            _llm_float(item.get("pct_change")) if _llm_float(item.get("pct_change")) is not None else -999.0,
            _llm_float(item.get("trading_value")) if _llm_float(item.get("trading_value")) is not None else 0.0,
        ),
        reverse=True,
    )
    for item in ordered:
        symbol = str(item.get("symbol") or "").upper().strip()
        if not symbol or symbol in seen:
            continue
        basis = item.get("leader_score_basis") if isinstance(item.get("leader_score_basis"), dict) else {}
        candidates.append(
            {
                "symbol": symbol,
                "pct_change": _llm_float(item.get("pct_change")),
                "price": _llm_float(item.get("price")),
                "trading_value": _llm_float(item.get("trading_value")),
                "trading_value_vs_previous_pct": _llm_float(item.get("trading_value_vs_previous_pct")),
                "volume_vs_previous_pct": _llm_float(item.get("volume_vs_previous_pct")),
                "rsi14": _llm_float(item.get("rsi14")),
                "rule_score": _llm_float(item.get("leader_score")),
                "theme_anchor": _llm_bool(basis.get("theme_leader_rank")),
                "rule_basis": {
                    "pct_change_rank": _llm_float(basis.get("pct_change_rank")),
                    "trading_value_rank": _llm_float(basis.get("trading_value_rank")),
                    "trading_value_vs_previous_rank": _llm_float(basis.get("trading_value_vs_previous_rank")),
                    "volume_vs_previous_rank": _llm_float(basis.get("volume_vs_previous_rank")),
                    "theme_leader_rank": _llm_float(basis.get("theme_leader_rank")),
                },
            }
        )
        seen.add(symbol)
        if len(candidates) >= candidate_limit:
            break
    return candidates


def _theme_news_for_llm(report: dict[str, Any], row: dict[str, Any]) -> str:
    lookup = report.get("theme_news")
    if not isinstance(lookup, dict):
        return ""
    keys = [
        str(row.get("key") or "").strip(),
        str(row.get("name") or "").strip(),
        _short_theme_label(str(row.get("name") or "").strip()),
    ]
    for key in keys:
        if key and lookup.get(key):
            return str(lookup.get(key)).strip()
    return ""


def _llm_rerank_request_payload(report: dict[str, Any]) -> dict[str, Any]:
    max_themes = _env_int("SECTOR_ALERT_LLM_MAX_THEMES", 8, minimum=1, maximum=12)
    candidate_limit = _env_int("SECTOR_ALERT_LLM_CANDIDATE_LIMIT", 8, minimum=3, maximum=12)
    min_leaders, max_leaders = _llm_leader_count_bounds()
    rows = report.get("theme_baskets")
    if not isinstance(rows, list) or not rows:
        rows = report.get("strong_themes")
    if not isinstance(rows, list):
        rows = []
    symbol_issues = report.get("symbol_issues") if isinstance(report.get("symbol_issues"), dict) else {}
    themes: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        candidates = _leader_candidates_for_llm(row, candidate_limit)
        if len(candidates) < 2:
            continue
        for candidate in candidates:
            issue = symbol_issues.get(candidate["symbol"]) if isinstance(symbol_issues, dict) else None
            if issue:
                candidate["issue"] = str(issue)
        themes.append(
            {
                "key": str(row.get("key") or row.get("name") or "").strip(),
                "name": str(row.get("name") or row.get("key") or "").strip(),
                "breadth_positive_pct": _llm_float(row.get("breadth_positive_pct")),
                "average_pct_change": _llm_float(row.get("average_pct_change")),
                "trading_value": _llm_float(row.get("trading_value")),
                "theme_news": _theme_news_for_llm(report, row),
                "candidates": candidates,
            }
        )
        if len(themes) >= max_themes:
            break
    return {"leader_selection": {"minimum": min_leaders, "maximum": max_leaders}, "themes": themes}


def _extract_llm_text(payload: dict[str, Any]) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list):
                parts = [str(part.get("text") or "") for part in content if isinstance(part, dict)]
                return "\n".join(part for part in parts if part).strip()
    output = payload.get("output")
    if isinstance(output, list):
        parts: list[str] = []
        for item in output:
            content = item.get("content") if isinstance(item, dict) else None
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and isinstance(part.get("text"), str):
                        parts.append(part["text"])
        if parts:
            return "\n".join(parts).strip()
    return ""


def _parse_llm_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        cleaned = cleaned[start : end + 1]
    payload = json.loads(cleaned)
    return payload if isinstance(payload, dict) else {}


def _llm_prompt_payload(request_payload: dict[str, Any]) -> str:
    selection = request_payload.get("leader_selection") if isinstance(request_payload.get("leader_selection"), dict) else {}
    min_leaders = int(selection.get("minimum") or 3)
    max_leaders = int(selection.get("maximum") or 5)
    return json.dumps(
        {
            "task": f"각 테마에서 최종 대장주를 {min_leaders}~{max_leaders}개 고르거나 재정렬해라.",
            "rules": [
                "후보에 없는 symbol은 절대 만들지 말 것",
                "테마 대표성(theme_anchor), 오늘 등락률, 거래대금, 거래대금 전일대비 증가, 거래량 증가, theme_news/issue를 함께 판단",
                "RSI가 높다는 이유만으로 감점하지 말 것",
                "SPY 대비 상대강도는 판단 기준에서 제외",
                "잡주성 급등보다 테마를 대표하면서 돈이 붙은 종목을 우선",
                f"후보가 충분하면 {min_leaders}개 이상, 확실한 대장주가 더 있으면 {max_leaders}개까지 허용",
                f"확신이 낮은 종목으로 억지로 {max_leaders}개를 채우지 말 것",
            ],
            "return_schema": {"themes": [{"key": "theme key", "leaders": ["AAA", "BBB", "CCC", "DDD"], "reason": "짧은 한국어 이유"}]},
            "input": request_payload,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _llm_system_prompt() -> str:
    return (
        "You rerank US stock theme leader candidates for a short market alert. "
        "Choose 3 to 5 symbols when candidates allow it. "
        "Choose only symbols that are present in candidates. Return only valid JSON."
    )


def _extract_sse_llm_text(raw: str) -> str:
    deltas: list[str] = []
    fallback: list[str] = []
    for line in raw.splitlines():
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if not data or data == "[DONE]":
            continue
        try:
            value = json.loads(data)
        except Exception:
            continue
        if not isinstance(value, dict):
            continue
        if value.get("type") == "response.output_text.delta" and isinstance(value.get("delta"), str):
            deltas.append(value["delta"])
            continue
        if deltas:
            continue
        if isinstance(value.get("delta"), str):
            fallback.append(value["delta"])
        response = value.get("response")
        if isinstance(response, dict) and isinstance(response.get("output_text"), str):
            fallback.append(response["output_text"])
        item = value.get("item")
        if isinstance(item, dict):
            content = item.get("content")
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and isinstance(part.get("text"), str):
                        fallback.append(part["text"])
    return "".join(deltas) if deltas else "".join(fallback)


def _call_codex_oauth_leader_rerank(request_payload: dict[str, Any], auth: dict[str, str]) -> dict[str, Any]:
    timeout = _env_int("SECTOR_ALERT_LLM_TIMEOUT_SECONDS", 12, minimum=3, maximum=60)
    model = _llm_model("codex_oauth")
    thread_id = f"stock-alert-{int(time.time())}"
    body = {
        "model": model,
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": _llm_prompt_payload(request_payload)}],
            }
        ],
        "instructions": _llm_system_prompt(),
        "tools": [],
        "tool_choice": "auto",
        "parallel_tool_calls": False,
        "store": False,
        "stream": True,
        "include": [],
        "prompt_cache_key": thread_id,
        "client_metadata": {"codex_cli_installation_id": "stock-alert-cron"},
        "reasoning": None,
    }
    headers = {
        "Authorization": f"Bearer {auth['access_token']}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "originator": "codex_cli_rs",
        "User-Agent": "codex_cli_rs/0.130.0 (stock-alert)",
        "x-client-request-id": thread_id,
        "session_id": thread_id,
        "session-id": thread_id,
        "thread_id": thread_id,
        "thread-id": thread_id,
        "codex_cli_window_id": "stock-alert-cron",
    }
    if auth.get("account_id"):
        headers["ChatGPT-Account-ID"] = auth["account_id"]
    req = urllib.request.Request(
        f"{_codex_llm_base_url()}/responses",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310 - Codex OAuth backend
        raw = resp.read().decode("utf-8", errors="replace")
    parsed = _parse_llm_json(_extract_sse_llm_text(raw) or raw)
    if parsed:
        parsed.setdefault("_model", model)
        parsed.setdefault("_auth", "codex_oauth")
    return parsed


def _call_openai_key_leader_rerank(request_payload: dict[str, Any]) -> dict[str, Any]:
    api_key = _llm_api_key()
    if not api_key:
        return {}
    timeout = _env_int("SECTOR_ALERT_LLM_TIMEOUT_SECONDS", 12, minimum=3, maximum=60)
    model = _llm_model("api_key")
    body = {
        "model": model,
        "temperature": 0.1,
        "max_tokens": _env_int("SECTOR_ALERT_LLM_MAX_TOKENS", 1200, minimum=300, maximum=3000),
        "messages": [
            {
                "role": "system",
                "content": _llm_system_prompt(),
            },
            {
                "role": "user",
                "content": _llm_prompt_payload(request_payload),
            },
        ],
    }
    req = urllib.request.Request(
        f"{_llm_base_url()}/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310 - configurable HTTPS LLM endpoint
        raw = resp.read().decode("utf-8", errors="replace")
    response_payload = json.loads(raw)
    parsed = _parse_llm_json(_extract_llm_text(response_payload))
    if parsed:
        parsed.setdefault("_model", model)
        parsed.setdefault("_auth", "api_key")
    return parsed


def _call_llm_leader_rerank(request_payload: dict[str, Any]) -> dict[str, Any]:
    auth = _load_codex_oauth()
    if auth.get("access_token"):
        return _call_codex_oauth_leader_rerank(request_payload, auth)
    return _call_openai_key_leader_rerank(request_payload)


def _candidate_row_map(row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw: list[Any] = []
    for key in ("leader_candidates", "leaders", "constituents"):
        values = row.get(key)
        if isinstance(values, list):
            raw.extend(values)
    result: dict[str, dict[str, Any]] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol") or "").upper().strip()
        if symbol and symbol not in result:
            result[symbol] = item
    return result


def _apply_llm_leader_choices(report: dict[str, Any], llm_payload: dict[str, Any]) -> int:
    choices = llm_payload.get("themes")
    if not isinstance(choices, list):
        return 0
    min_leaders, max_leaders = _llm_leader_count_bounds()
    choice_by_key: dict[str, list[str]] = {}
    reason_by_key: dict[str, str] = {}
    for item in choices:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        leaders = item.get("leaders")
        if not key or not isinstance(leaders, list):
            continue
        symbols = [str(symbol).upper().strip() for symbol in leaders if str(symbol).strip()]
        if symbols:
            choice_by_key[key] = list(dict.fromkeys(symbols))[:max_leaders]
            if item.get("reason"):
                reason_by_key[key] = str(item.get("reason"))
    if not choice_by_key:
        return 0
    changed = 0
    model = str(llm_payload.get("_model") or _llm_model(str(llm_payload.get("_auth") or "")))
    for collection in ("theme_baskets", "strong_themes", "weak_themes"):
        rows = report.get(collection)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            key = str(row.get("key") or row.get("name") or "").strip()
            symbols = choice_by_key.get(key)
            if not symbols:
                continue
            candidates = _candidate_row_map(row)
            selected: list[dict[str, Any]] = []
            seen: set[str] = set()
            for symbol in symbols:
                candidate = candidates.get(symbol)
                if candidate and symbol not in seen:
                    selected.append(candidate)
                    seen.add(symbol)
                if len(selected) >= max_leaders:
                    break
            fallback = row.get("leader_candidates") if isinstance(row.get("leader_candidates"), list) else row.get("leaders")
            if len(selected) < min_leaders and isinstance(fallback, list):
                for item in fallback:
                    if not isinstance(item, dict):
                        continue
                    symbol = str(item.get("symbol") or "").upper().strip()
                    if symbol and symbol not in seen:
                        selected.append(item)
                        seen.add(symbol)
                    if len(selected) >= min_leaders:
                        break
            if selected:
                final_selected = selected[:max_leaders]
                before = [str(item.get("symbol") or "").upper().strip() for item in row.get("leaders", []) if isinstance(item, dict)]
                row["leaders"] = final_selected
                row["llm_leader_rerank"] = {
                    "model": model,
                    "selected_symbols": [str(item.get("symbol") or "").upper().strip() for item in final_selected],
                    "min_leaders": min_leaders,
                    "max_leaders": max_leaders,
                    "reason": reason_by_key.get(key),
                }
                after = [str(item.get("symbol") or "").upper().strip() for item in final_selected]
                if before[:max_leaders] != after:
                    changed += 1
    return changed


def _theme_line_for_alert(prefix: str, rows: Any) -> str:
    if not isinstance(rows, list) or not rows:
        return f"{prefix}: 기준 해당 없음"
    parts: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        leaders = ", ".join(
            f"{leader.get('symbol')} {_fmt_alert_pct(leader.get('pct_change'))}"
            for leader in row.get("leaders", [])
            if isinstance(leader, dict) and leader.get("symbol")
        )
        value_text = f" / 거래대금 {_fmt_alert_trading_value(row.get('trading_value'))}" if row.get("trading_value") is not None else ""
        volume_text = _alert_volume_suffix(row)
        parts.append(f"{row.get('name') or row.get('key')} 상승비율 {_fmt_alert_pct(row.get('breadth_positive_pct')).replace('+', '')}{value_text}{volume_text} / 주도 {leaders or 'n/a'}")
    return f"{prefix}: " + " | ".join(part for part in parts if part)


def _theme_leader_status_line_for_alert(rows: Any) -> str:
    if not isinstance(rows, list) or not rows:
        return "테마별 대장주: 기준 해당 없음"
    parts: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        leaders = row.get("leaders")
        if not isinstance(leaders, list) or not leaders or not isinstance(leaders[0], dict):
            continue
        leader = leaders[0]
        parts.append(f"{row.get('name') or row.get('key')}: {leader.get('symbol')} {_fmt_alert_pct(leader.get('pct_change'))}")
    return "테마별 대장주: " + " | ".join(parts) if parts else "테마별 대장주: 기준 해당 없음"


def _replace_focus_line(focus: list[Any], prefix: str, value: str) -> None:
    for idx, item in enumerate(focus):
        if str(item).startswith(prefix):
            focus[idx] = value
            return
    focus.append(value)


def _refresh_focus_lines_after_llm(response: dict[str, Any]) -> None:
    data = response.get("data") if isinstance(response.get("data"), dict) else {}
    report = data.get("sector_strength") if isinstance(data, dict) else {}
    if not isinstance(report, dict):
        return
    focus = response.get("focus")
    if not isinstance(focus, list):
        return
    _replace_focus_line(focus, "강한 테마:", _theme_line_for_alert("강한 테마", report.get("strong_themes")))
    _replace_focus_line(focus, "약한 테마:", _theme_line_for_alert("약한 테마", report.get("weak_themes")))
    _replace_focus_line(focus, "테마별 대장주:", _theme_leader_status_line_for_alert(report.get("theme_baskets")))


def _rerank_sector_response_with_llm(response: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(response, dict) or response.get("mode") in {"oil_vix", "market_regime"}:
        return response
    if not _llm_rerank_enabled() or not _llm_auth_available():
        return response
    data = response.get("data")
    report = data.get("sector_strength") if isinstance(data, dict) else None
    if not isinstance(report, dict):
        return response
    request_payload = _llm_rerank_request_payload(report)
    if not request_payload.get("themes"):
        return response
    try:
        llm_payload = _call_llm_leader_rerank(request_payload)
        changed = _apply_llm_leader_choices(report, llm_payload)
    except Exception as exc:
        report["llm_leader_rerank_error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
        return response
    if changed:
        report["llm_leader_rerank"] = {
            "model": str(llm_payload.get("_model") or _llm_model(str(llm_payload.get("_auth") or ""))),
            "auth": str(llm_payload.get("_auth") or ""),
            "changed_theme_count": changed,
        }
        _refresh_focus_lines_after_llm(response)
    return response


def _select_alert_focus_lines(focus: Any, max_items: int = 7) -> list[str]:
    if not isinstance(focus, list):
        return []
    cleaned = [str(item).strip() for item in focus if str(item).strip()]
    priority_prefixes = (
        "장 분위기:",
        "강한 테마:",
        "약한 테마:",
        "전날 강했던 테마:",
        "로테이션 해석:",
        "오늘 먼저 볼 종목:",
        "ETF 시장 참고:",
    )
    selected: list[str] = []
    seen: set[str] = set()
    for prefix in priority_prefixes:
        for text in cleaned:
            if text.startswith(prefix) and text not in seen:
                selected.append(text)
                seen.add(text)
                break
    for text in cleaned:
        if len(selected) >= max_items:
            break
        if text not in seen:
            selected.append(text)
            seen.add(text)
    return selected[:max_items]


def _strip_alert_display_noise(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return ""
    # Keep source/time correctness in the data pipeline, but do not surface
    # implementation/baseline labels in the mobile Telegram body.
    cleaned = cleaned.replace(" / source toss_wts_stock_prices", "")
    cleaned = cleaned.replace("source toss_wts_stock_prices", "")
    cleaned = cleaned.replace("(거래대금/VWAP 기반 proxy)", "")
    cleaned = cleaned.replace(" / Toss base 대비", "")
    cleaned = cleaned.replace(", Toss base 대비", "")
    cleaned = cleaned.replace("Toss base 대비", "")
    cleaned = cleaned.replace(" / 세션 토스 데이마켓/주간거래", "")
    cleaned = cleaned.replace("세션 토스 데이마켓/주간거래", "")
    cleaned = cleaned.replace(", 토스 데이마켓/주간거래", "")
    cleaned = cleaned.replace("토스 데이마켓/주간거래, ", "")
    cleaned = cleaned.replace("토스 데이마켓/주간거래", "")
    cleaned = re.sub(r"\s*/\s*/\s*", " / ", cleaned)
    cleaned = re.sub(r",\s*,", ",", cleaned)
    cleaned = re.sub(r";\s*,", ";", cleaned)
    cleaned = re.sub(r"\(\s*([^)]*?)\s*,\s*\)", r"(\1)", cleaned)
    cleaned = re.sub(r"\(\s*([^)]*?)\s*;\s*\)", r"(\1)", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = cleaned.replace(" / 기준시각", " / 기준시각")
    cleaned = _compact_alert_volume_text(cleaned)
    return cleaned.strip(" ,/")


def _clean_focus_lines(focus: Any) -> list[str]:
    if not isinstance(focus, list):
        return []
    lines: list[str] = []
    for item in focus:
        cleaned = _strip_alert_display_noise(str(item))
        if cleaned:
            lines.append(cleaned)
    return lines


def _strip_focus_prefix(text: str, prefix: str) -> str:
    return text[len(prefix):].strip() if text.startswith(prefix) else text.strip()


def _focus_line(lines: list[str], prefix: str, contains: str | None = None, last: bool = False) -> str:
    iterable = reversed(lines) if last else iter(lines)
    for text in iterable:
        if not text.startswith(prefix):
            continue
        if contains and contains not in text:
            continue
        return _strip_focus_prefix(text, prefix)
    return ""


def _split_focus_parts(text: str, max_items: int) -> list[str]:
    if not text:
        return []
    parts = [part.strip() for part in text.split("|") if part.strip()]
    return parts[:max_items]


def _theme_part_label(item: str) -> str:
    head, sep, _leaders = item.rpartition(" / 주도 ")
    text = head if sep else item
    for marker in (" 평균 ", " 대표 ETF ", " ETF ", " 전일 상승비율 ", " / 전일 상승비율", " 상승비율 ", " / 상승비율"):
        if marker in text:
            return text.split(marker, 1)[0].strip()
    return text.strip()


def _theme_leader_detail_lookup(items: list[str]) -> dict[str, list[str]]:
    lookup: dict[str, list[str]] = {}
    for item in items:
        theme, sep, rest = item.partition(":")
        if sep and theme.strip() and rest.strip():
            key = _short_theme_label(theme.strip().lstrip("•").strip())
            detail = _compact_theme_leader(item) if " — " in item else item.strip()
            if ":" in detail:
                detail = detail.split(":", 1)[1].strip()
            detail = _reorder_symbol_pct_price_text(detail)
            if detail:
                lookup.setdefault(key, []).append(detail)
    return lookup


def _split_leader_summaries(text: str) -> list[str]:
    return [part.strip() for part in text.split(",") if part.strip()]


def _split_theme_head(head: str) -> tuple[str, str]:
    text = head.strip()
    if " 평균 " in text:
        theme, rest = text.split(" 평균 ", 1)
        if " / 상승비율 " in rest:
            metrics = rest.split(" / 상승비율 ", 1)[1]
            return theme.strip(), f"상승비율 {metrics.strip()}"
        return theme.strip(), f"평균 {rest.strip()}"
    if " 상승비율 " in text:
        theme, metrics = text.split(" 상승비율 ", 1)
        return theme.strip(), f"상승비율 {metrics.strip()}"
    if " / 상승비율 " in text:
        theme, metrics = text.split(" / 상승비율 ", 1)
        return theme.strip(), f"상승비율 {metrics.strip()}"
    return text, ""


def _symbol_issues_from_payload(payload: dict[str, Any]) -> dict[str, str]:
    if not _symbol_issues_enabled():
        return {}
    report = _sector_report(payload)
    raw = report.get("symbol_issues")
    if not isinstance(raw, dict):
        return {}
    issues: dict[str, str] = {}
    for symbol, issue in raw.items():
        symbol_text = str(symbol or "").upper().strip()
        issue_text = str(issue or "").strip()
        issue_text = re.sub(r"\s*/\s*출처\s+[^/]+$", "", issue_text).strip()
        if symbol_text and issue_text:
            issues[symbol_text] = issue_text
    return issues


def _clean_theme_news_value(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("summary", "text", "headline", "topic"):
            if value.get(key):
                return _clean_theme_news_value(value.get(key))
        return ""
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            cleaned = _clean_theme_news_value(item)
            if cleaned and cleaned not in parts:
                parts.append(cleaned)
            if len(parts) >= 3:
                break
        return ", ".join(parts)
    text = _clean_issue_text(value, max_chars=180)
    text = re.sub(r"\s*/\s*출처\s+[^/]+$", "", text).strip()
    text = re.sub(r"^뉴스\s*[-:]\s*", "", text).strip()
    return text


def _theme_news_from_payload(payload: dict[str, Any]) -> dict[str, str]:
    if not _theme_news_enabled():
        return {}
    report = _sector_report(payload)
    raw = report.get("theme_news")
    if not isinstance(raw, dict):
        return {}
    aliases: dict[str, set[str]] = {}
    for collection in ("strong_themes", "weak_themes", "theme_baskets"):
        rows = report.get(collection)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            key = str(row.get("key") or "").strip()
            name = str(row.get("name") or row.get("parent_name") or "").strip()
            if key:
                aliases.setdefault(key, set()).add(key)
                if name:
                    aliases[key].update({name, _short_theme_label(name)})
            if name:
                aliases.setdefault(name, set()).update({name, _short_theme_label(name)})
    lookup: dict[str, str] = {}
    for key, value in raw.items():
        key_text = str(key or "").strip()
        summary = _clean_theme_news_value(value)
        if not key_text or not summary:
            continue
        keys = {key_text, _short_theme_label(key_text)}
        keys.update(aliases.get(key_text, set()))
        for alias in keys:
            if alias:
                lookup[alias] = summary
    return lookup


def _theme_news_for_label(theme_news_lookup: dict[str, str], theme_label: str) -> str:
    if not theme_news_lookup:
        return ""
    key = theme_label.strip()
    return theme_news_lookup.get(key) or theme_news_lookup.get(_short_theme_label(key)) or ""


def _limited_symbol_issue_lookup(symbol_issues: dict[str, str], limit: int | None) -> dict[str, str]:
    if limit is None:
        return symbol_issues
    if limit <= 0:
        return {}
    limited: dict[str, str] = {}
    for idx, (symbol, issue) in enumerate(symbol_issues.items()):
        if idx >= limit:
            break
        limited[symbol] = issue
    return limited


def _append_leader_issue_line(lines: list[str], leader: str, issue_lookup: dict[str, str]) -> None:
    symbol = _leading_symbol(leader)
    if not symbol:
        return
    issue = issue_lookup.get(symbol.upper())
    if issue:
        lines.append(f"      · 이슈: {issue}")


def _filter_alert_detail_text(details: str) -> str:
    text = details.strip()
    if " | " in text:
        prefix, indicator_text = text.split(" | ", 1)
        clauses = [part.strip() for part in indicator_text.split(",") if part.strip()]
        kept = [clause for clause in clauses if _is_allowed_alert_indicator_clause(clause)]
        return f"{prefix.strip()} | {', '.join(kept)}" if kept else prefix.strip()
    clauses = [part.strip() for part in text.split(",") if part.strip()]
    if len(clauses) <= 1:
        return text if _is_allowed_alert_indicator_clause(text) else ""
    kept = [clause for clause in clauses if _is_allowed_alert_indicator_clause(clause)]
    return ", ".join(kept)


def _format_leader_detail_lines(detail: str, issue_lookup: dict[str, str] | None = None) -> list[str]:
    issue_lookup = issue_lookup or {}
    text = detail.strip()
    if not text:
        return []
    if " / 거래량 " in text:
        leader, details = text.split(" / 거래량 ", 1)
        filtered_details = _filter_alert_detail_text(details.strip())
        lines = [f"    - {leader.strip()}"]
        if filtered_details:
            lines.append(f"      · 거래량 {filtered_details}")
        _append_leader_issue_line(lines, leader, issue_lookup)
        return lines
    if " | " in text:
        leader, details = text.split(" | ", 1)
        filtered_details = _filter_alert_detail_text(details.strip())
        lines = [f"    - {leader.strip()}"]
        if filtered_details:
            lines.append(f"      · {filtered_details}")
        _append_leader_issue_line(lines, leader, issue_lookup)
        return lines
    lines = [f"    - {text}"]
    _append_leader_issue_line(lines, text, issue_lookup)
    return lines


def _format_theme_lines(
    items: list[str],
    leader_details: dict[str, list[str]] | None = None,
    issue_lookup: dict[str, str] | None = None,
    theme_news_lookup: dict[str, str] | None = None,
) -> list[str]:
    leader_details = leader_details or {}
    issue_lookup = issue_lookup or {}
    theme_news_lookup = theme_news_lookup or {}
    lines: list[str] = []
    for idx, item in enumerate(items):
        if idx:
            lines.append("")
        head, sep, leaders = item.rpartition(" / 주도 ")
        if sep and head.strip() and leaders.strip():
            theme_title, theme_metrics = _split_theme_head(head)
            theme_label = _theme_part_label(item)
            lines.append(f"• {theme_title}")
            if theme_metrics:
                lines.append(f"  · {theme_metrics}")
            theme_news = _theme_news_for_label(theme_news_lookup, theme_label)
            if theme_news:
                lines.append(f"  · 뉴스: {theme_news}")
            lines.append("  · 주도주:")
            details = list(leader_details.get(_short_theme_label(theme_label), []))
            detail_symbols = _extract_pct_symbols(details)
            for summary in _split_leader_summaries(leaders):
                symbol = _leading_symbol(summary)
                if symbol and symbol not in detail_symbols:
                    details.append(summary)
            for detail in details:
                lines.extend(_format_leader_detail_lines(detail, issue_lookup))
        else:
            lines.append(f"• {item}")
    return lines


def _split_previous_day_theme_head(head: str) -> tuple[str, str]:
    text = head.strip()
    if " 전일 상승비율 " in text:
        theme, metrics = text.split(" 전일 상승비율 ", 1)
        return theme.strip(), f"전일 상승비율 {metrics.strip()}"
    if " / 전일 상승비율 " in text:
        theme, metrics = text.split(" / 전일 상승비율 ", 1)
        return theme.strip(), f"전일 상승비율 {metrics.strip()}"
    return text, ""


def _format_previous_day_theme_lines(items: list[str]) -> list[str]:
    lines: list[str] = []
    for idx, item in enumerate(items):
        if idx:
            lines.append("")
        head, sep, leaders = item.rpartition(" / 전일 주도 ")
        if sep and head.strip() and leaders.strip():
            theme_title, theme_metrics = _split_previous_day_theme_head(head)
            lines.append(f"• {theme_title}")
            if theme_metrics:
                lines.append(f"  · {theme_metrics}")
            lines.append("  · 전일 주도주:")
            leader_lines = [_reorder_previous_day_symbol_text(summary) for summary in _split_leader_summaries(leaders)]
            for summary in leader_lines:
                if summary:
                    lines.append(f"    - {summary}")
        elif item and item != "기준 해당 없음":
            lines.append(f"• {item}")
    return lines


_PCT_SYMBOL_RE = re.compile(
    r"\b([A-Z][A-Z0-9.\-]{0,9})(?:\s+[+-]?\d+(?:\.\d+)?%|\s+\$[0-9][0-9.,]*\([+-]?\d+(?:\.\d+)?%\))"
)
_LEADING_SYMBOL_RE = re.compile(r"^\s*•?\s*([A-Z][A-Z0-9.\-]{0,9})\b")
_SYMBOL_PCT_PRICE_RE = re.compile(
    r"\b([A-Z][A-Z0-9.\-]{0,9})\s+([+-]\d+(?:\.\d+)?%)\s+(?:가격\s+|\$?)([0-9][0-9.,]*)(?=\b|[,/\s|])"
)
_PREVIOUS_DAY_SYMBOL_PCT_PRICE_RE = re.compile(
    r"\b([A-Z][A-Z0-9.\-]{0,9})\s+([+-]\d+(?:\.\d+)?%)\s+/\s+전일종가\s+(\$?[0-9][0-9.,]*)(?=\b|[,/\s|])"
)
_VERBOSE_VOLUME_RE = re.compile(
    r"거래량\s+당일\s+([^/\s,]+)\s*/\s*전일\s+([^/\s,]+)(?:\s*/\s*전일대비\s+([+-]?\d+(?:\.\d+)?%))?"
)


def _extract_pct_symbols(lines: list[str]) -> set[str]:
    symbols: set[str] = set()
    for line in lines:
        symbols.update(match.group(1) for match in _PCT_SYMBOL_RE.finditer(line))
    return symbols


def _leading_symbol(text: str) -> str | None:
    match = _LEADING_SYMBOL_RE.match(text)
    return match.group(1) if match else None


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt_alert_pct(value: Any) -> str:
    numeric = _as_float(value)
    return "n/a" if numeric is None else f"{numeric:+.2f}%"


def _fmt_alert_signed(value: Any, digits: int = 2) -> str:
    numeric = _as_float(value)
    return "n/a" if numeric is None else f"{numeric:+.{digits}f}"


def _fmt_alert_price(value: Any) -> str:
    numeric = _as_float(value)
    if numeric is None:
        return ""
    text = f"{numeric:.2f}".rstrip("0").rstrip(".")
    return f"${text}"


def _fmt_alert_price_token(value: str) -> str:
    numeric = _as_float(value.replace(",", ""))
    if numeric is None:
        token = value.strip()
        return token if token.startswith("$") else f"${token}"
    return _fmt_alert_price(numeric)


def _format_alert_symbol_price_pct(symbol: str, price: str, pct: str) -> str:
    return f"{symbol} {price}({pct})"


def _reorder_symbol_pct_price_text(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        symbol, pct, price = match.groups()
        return _format_alert_symbol_price_pct(symbol, _fmt_alert_price_token(price), pct)

    return _SYMBOL_PCT_PRICE_RE.sub(repl, text)


def _reorder_previous_day_symbol_text(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        symbol, pct, price = match.groups()
        return _format_alert_symbol_price_pct(symbol, _fmt_alert_price_token(price), pct)

    return _PREVIOUS_DAY_SYMBOL_PCT_PRICE_RE.sub(repl, text).replace(" / 전일 거래량 ", " / 거래량 ")


def _compact_alert_volume_text(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        day, previous, pct = match.groups()
        pct_text = f"({pct})" if pct else ""
        return f"거래량 {day}/{previous}{pct_text}"

    return _VERBOSE_VOLUME_RE.sub(repl, text)


def _fmt_alert_volume(value: Any) -> str:
    numeric = _as_float(value)
    if numeric is None:
        return "n/a"
    if abs(numeric) >= 1_000_000_000:
        return f"{numeric / 1_000_000_000:.1f}B"
    if abs(numeric) >= 1_000_000:
        return f"{numeric / 1_000_000:.1f}M"
    if abs(numeric) >= 1_000:
        return f"{numeric / 1_000:.1f}K"
    return f"{numeric:.0f}"


def _fmt_alert_trading_value(value: Any) -> str:
    numeric = _as_float(value)
    if numeric is None:
        return "n/a"
    if abs(numeric) >= 1_000_000_000:
        return f"${numeric / 1_000_000_000:.1f}B"
    if abs(numeric) >= 1_000_000:
        return f"${numeric / 1_000_000:.1f}M"
    if abs(numeric) >= 1_000:
        return f"${numeric / 1_000:.1f}K"
    return f"${numeric:.0f}"


def _fmt_alert_delta(value: Any, digits: int = 0) -> str:
    numeric = _as_float(value)
    return "" if numeric is None else f"({numeric:+.{digits}f})"


def _alert_volume_suffix(row: dict[str, Any]) -> str:
    day_volume = _as_float(row.get("day_volume"))
    volume = _as_float(row.get("volume"))
    if day_volume in (None, 0.0) and volume not in (None, 0.0):
        day_volume = volume
    previous_volume = _as_float(row.get("previous_volume"))
    volume_vs_previous = _as_float(row.get("volume_vs_previous_pct"))
    if day_volume is None and previous_volume is None:
        return ""
    if day_volume is not None and previous_volume is not None:
        pct_text = f"({_fmt_alert_pct(volume_vs_previous)})" if volume_vs_previous is not None else ""
        return f" / 거래량 {_fmt_alert_volume(day_volume)}/{_fmt_alert_volume(previous_volume)}{pct_text}"
    if day_volume is not None:
        return f" / 거래량 {_fmt_alert_volume(day_volume)}"
    return f" / 거래량 n/a/{_fmt_alert_volume(previous_volume)}"


def _alert_trading_value_suffix(row: dict[str, Any]) -> str:
    current = _as_float(row.get("trading_value"))
    previous = _as_float(row.get("previous_day_trading_value"))
    value_vs_previous = _as_float(row.get("trading_value_vs_previous_pct"))
    if current is None and previous is None:
        return ""
    if current is not None and previous is not None:
        pct_text = f"({_fmt_alert_pct(value_vs_previous)})" if value_vs_previous is not None else ""
        return f" / 거래대금 {_fmt_alert_trading_value(current)}/{_fmt_alert_trading_value(previous)}{pct_text}"
    if current is not None:
        return f" / 거래대금 {_fmt_alert_trading_value(current)}"
    return f" / 거래대금 n/a/{_fmt_alert_trading_value(previous)}"


def _alert_indicator_parts(row: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    rsi = _as_float(row.get("rsi14"))
    if rsi is not None:
        parts.append(f"RSI {rsi:.0f}{_fmt_alert_delta(row.get('rsi14_delta'), 0)}")

    # MACD/Stochastic 계산 필드는 데이터에 유지하되 모바일 알림 본문에는 출력하지 않는다.
    show_extended_indicators = _env_flag("SECTOR_ALERT_SHOW_EXTENDED_INDICATORS", False)
    macd_line = _as_float(row.get("macd_line"))
    macd_signal = _as_float(row.get("macd_signal"))
    macd_hist = _as_float(row.get("macd_histogram"))
    if show_extended_indicators and macd_line is not None and macd_signal is not None:
        hist_text = f" h{_fmt_alert_signed(macd_hist, 2)}{_fmt_alert_delta(row.get('macd_histogram_delta'), 2)}" if macd_hist is not None else ""
        parts.append(f"MACD {_fmt_alert_price(macd_line).lstrip('$')}/{_fmt_alert_price(macd_signal).lstrip('$')}{hist_text}")

    stoch_k = _as_float(row.get("stochastic_k"))
    stoch_d = _as_float(row.get("stochastic_d"))
    if show_extended_indicators and stoch_k is not None and stoch_d is not None:
        parts.append(f"Stochastic Slow {stoch_k:.0f}/{stoch_d:.0f}{_fmt_alert_delta(row.get('stochastic_k_delta'), 0)}")

    return parts


def _format_structured_leader_detail(row: dict[str, Any]) -> str:
    symbol = str(row.get("symbol") or "").strip()
    if not symbol:
        return ""
    price = _fmt_alert_price(row.get("price"))
    pct = _fmt_alert_pct(row.get("pct_change"))
    base = _format_alert_symbol_price_pct(symbol, price, pct) if price else f"{symbol} {pct}"
    base = f"{base}{_alert_trading_value_suffix(row)}{_alert_volume_suffix(row)}"
    indicators = _alert_indicator_parts(row)
    return f"{base} | {', '.join(indicators)}" if indicators else base


def _sector_report(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    report = data.get("sector_strength") if isinstance(data, dict) else {}
    return report if isinstance(report, dict) else {}


def _structured_theme_leader_detail_lookup(payload: dict[str, Any]) -> dict[str, list[str]]:
    report = _sector_report(payload)
    lookup: dict[str, list[str]] = {}
    for collection in ("strong_themes", "weak_themes", "theme_baskets"):
        rows = report.get(collection)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            theme_name = str(row.get("name") or row.get("parent_name") or "").strip()
            if not theme_name:
                continue
            leaders = row.get("leaders")
            if not isinstance(leaders, list):
                continue
            details = [
                detail
                for detail in (_format_structured_leader_detail(leader) for leader in leaders if isinstance(leader, dict))
                if detail
            ]
            if details:
                lookup[_short_theme_label(theme_name)] = details
    return lookup


def _payload_collected_at(payload: dict[str, Any]) -> str | None:
    direct = payload.get("collected_at")
    if direct:
        return str(direct)
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    if not isinstance(data, dict):
        return None
    for key in ("sector_strength", "oil_vix", "market_regime"):
        section = data.get(key)
        if isinstance(section, dict) and section.get("collected_at"):
            return str(section.get("collected_at"))
    return None


def _alert_time_label(payload: dict[str, Any]) -> str:
    raw = _payload_collected_at(payload)
    dt: datetime | None = None
    if raw:
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            dt = None
    dt = _to_utc(dt or _now_utc())
    if ZoneInfo is None:
        return dt.strftime("%H:%M UTC")
    kst = dt.astimezone(ZoneInfo("Asia/Seoul"))
    et = dt.astimezone(ZoneInfo("America/New_York"))
    return f"{kst:%H:%M} KST / {et:%H:%M} ET"


def _sector_mood_label(text: str) -> str:
    label = text.split("/", 1)[0].strip()
    return label or "중립"


def _sector_mood_lines(focus_lines: list[str]) -> list[str]:
    benchmark = _focus_line(focus_lines, "장 분위기:", contains="NASDAQ", last=True)
    benchmark = _strip_alert_display_noise(benchmark.split(" / 기준시각", 1)[0].strip())
    lines: list[str] = []
    if benchmark:
        lines.append(f"- {benchmark}")
    return lines or ["데이터 부족"]



def _short_theme_label(name: str) -> str:
    if "우주" in name:
        return "우주"
    if "암호화" in name or "코인" in name:
        return "코인"
    if "원전" in name or "우라늄" in name or "전력" in name or "에너지" in name:
        return "원전"
    if "반도체" in name:
        return "반도체"
    if "AI" in name or "빅테크" in name or "인프라" in name:
        return "AI"
    if "양자" in name:
        return "양자"
    if "헬스" in name or "GLP" in name:
        return "헬스"
    return name.split("/", 1)[0].strip() or name.strip()


def _indicator_head(details: str, label: str) -> str:
    if label == "Stochastic Slow":
        pattern = r"(?:Stochastic|스토캐스틱) Slow\s+([^:;]+)"
    else:
        pattern = rf"{re.escape(label)}\s+([^:;]+)"
    match = re.search(pattern, details)
    return match.group(1).strip() if match else "n/a"


def _compact_theme_leader(item: str, include_indicators: bool = True) -> str:
    text = item.strip()
    if not text:
        return text
    lead, sep, details = text.partition(" — ")
    theme, colon, rest = lead.partition(":")
    if not colon:
        base = lead.strip()
        theme_label = ""
    else:
        theme_label = _short_theme_label(theme.strip())
        rest_head = rest.split(",", 1)[0].strip()
        rest_head = _reorder_symbol_pct_price_text(rest_head)
        base = f"{theme_label}: {rest_head}"
    if not sep or not include_indicators:
        return base or text
    rsi = _indicator_head(details, "RSI")
    return f"{base} | RSI {rsi}" if rsi != "n/a" else base

_BLOCKED_ALERT_INDICATOR_TOKENS = (
    "구름",
    "전환선",
    "기준선",
    "일목",
    "Ichimoku",
    "ichimoku",
    "BB ",
    "MACD",
    "macd",
    "Stochastic",
    "Stoch",
    "스토캐스틱",
)


def _normalize_alert_indicator_clause(clause: str) -> str:
    text = clause.strip()
    if text.startswith("Stoch "):
        return "Stochastic Slow " + text[len("Stoch "):]
    if text.startswith("스토캐스틱 Slow "):
        return "Stochastic Slow " + text[len("스토캐스틱 Slow "):]
    return text


def _is_allowed_alert_indicator_clause(clause: str) -> bool:
    return not any(token in clause for token in _BLOCKED_ALERT_INDICATOR_TOKENS)


def _format_mover_lines(movers: list[str], issue_lookup: dict[str, str] | None = None) -> list[str]:
    issue_lookup = issue_lookup or {}
    if not movers:
        return ["데이터 부족"]
    lines: list[str] = []
    for item in movers:
        text = item.strip()
        if not text:
            continue
        if " — " not in text:
            lines.append(f"• {text}")
            symbol = _leading_symbol(text)
            issue = issue_lookup.get(symbol.upper()) if symbol else None
            if issue:
                lines.append(f"  · 이슈: {issue}")
            continue
        lead, details = text.split(" — ", 1)
        lines.append(f"• {lead.strip()}")
        clauses = [part.strip() for part in details.split(";") if part.strip()]
        for clause in clauses:
            if not _is_allowed_alert_indicator_clause(clause):
                continue
            lines.append(f"  · {_normalize_alert_indicator_clause(clause)}")
        symbol = _leading_symbol(lead)
        issue = issue_lookup.get(symbol.upper()) if symbol else None
        if issue:
            lines.append(f"  · 이슈: {issue}")
    return lines or ["데이터 부족"]


def _format_previous_close_strength_lines(line: str, exclude_symbols: set[str] | None = None) -> list[str]:
    text = _strip_focus_prefix(line, "전일종가 대비 현재 강세:")
    if not text:
        return []
    exclude_symbols = exclude_symbols or set()
    body = text
    for marker in (" / 기준 ", " / 출처 "):
        body = body.split(marker, 1)[0].strip()
    items = [item.strip() for item in body.split(" | ") if item.strip()]
    lines = ["현재 강세"]
    for item in items[:3]:
        compact = item.replace(", 기준 전일 정규장 종가 대비 현재가", "")
        compact = compact.replace(", 출처 Yahoo chart 1m includePrePost", "")
        compact = compact.replace("/ 기준 전일 정규장 종가 대비 현재가", "")
        compact = compact.replace("/ 출처 Yahoo chart 1m includePrePost", "")
        compact = compact.replace(", 정규장", "")
        compact = compact.strip(" ,/")
        compact = _reorder_symbol_pct_price_text(compact)
        symbol = _leading_symbol(compact)
        if symbol and symbol in exclude_symbols:
            continue
        lines.append(f"• {compact}")
    return lines if len(lines) > 1 else []


def _build_sector_telegram_text(payload: dict[str, Any]) -> str:
    focus_lines = _clean_focus_lines(payload.get("focus") or [])
    strong = _split_focus_parts(_focus_line(focus_lines, "강한 테마:"), 20)
    weak = _split_focus_parts(_focus_line(focus_lines, "약한 테마:"), 20)
    previous_day_themes = [
        item
        for item in _split_focus_parts(_focus_line(focus_lines, "전날 강했던 테마:"), 20)
        if item and item != "기준 해당 없음"
    ]
    theme_leaders = _split_focus_parts(_focus_line(focus_lines, "테마별 대장주:"), 20)
    movers = _split_focus_parts(_focus_line(focus_lines, "오늘 먼저 볼 종목:"), 5)
    previous_close_strength = _focus_line(focus_lines, "전일종가 대비 현재 강세:")
    limit = min(1800, TELEGRAM_TEXT_LIMIT)
    symbol_issues = _symbol_issues_from_payload(payload)
    theme_news_lookup = _theme_news_from_payload(payload)

    def render(selected_movers: list[str], selected_theme_leaders: list[str] | None = None, issue_limit: int | None = None) -> str:
        rendered_theme_leaders = selected_theme_leaders if selected_theme_leaders is not None else theme_leaders
        leader_details = _structured_theme_leader_detail_lookup(payload)
        if rendered_theme_leaders:
            fallback_leader_details = _theme_leader_detail_lookup(rendered_theme_leaders)
            for key, details in fallback_leader_details.items():
                leader_details.setdefault(key, details)
        issue_lookup = _limited_symbol_issue_lookup(symbol_issues, issue_limit)
        lines = [
            f"[5분 테마 알림 | {_alert_time_label(payload)}]",
            "",
            "1) 시장",
        ]
        lines.extend(_sector_mood_lines(focus_lines))
        lines.extend([
            "",
            "2) 강한 테마",
        ])
        display_strong = strong
        display_weak = weak
        strong_lines = _format_theme_lines(display_strong or ["데이터 부족"], leader_details, issue_lookup, theme_news_lookup)
        weak_lines = _format_theme_lines(display_weak or ["데이터 부족"], leader_details, issue_lookup, theme_news_lookup)
        displayed_symbols = _extract_pct_symbols(strong_lines + weak_lines)
        lines.extend(strong_lines)
        lines.extend(["", "3) 약한 테마"])
        lines.extend(weak_lines)
        section_no = 4
        if not rendered_theme_leaders:
            lines.extend([
                "",
                f"{section_no}) 먼저 볼 종목",
            ])
            mover_lines = _format_mover_lines(selected_movers, issue_lookup)
            displayed_symbols.update(_extract_pct_symbols(mover_lines))
            lines.extend(mover_lines)
            section_no += 1
        previous_day_lines = _format_previous_day_theme_lines(previous_day_themes)
        if previous_day_lines:
            lines.extend(["", f"{section_no}) 전날 강했던 테마"])
            lines.extend(previous_day_lines)
            displayed_symbols.update(_extract_pct_symbols(previous_day_lines))
            section_no += 1
        strength_lines: list[str] = []
        if previous_close_strength:
            strength_lines = _format_previous_close_strength_lines(previous_close_strength, displayed_symbols)
            if strength_lines:
                lines.extend(["", f"{section_no}) 현재 강세"])
                lines.extend(strength_lines[1:] if strength_lines and strength_lines[0] == "현재 강세" else strength_lines)
        return "\n".join(lines).strip()

    initial_theme_leaders = [_compact_theme_leader(item) for item in theme_leaders[:7]] if theme_leaders else None
    issue_budget = len(symbol_issues)
    text = render([] if theme_leaders else movers, initial_theme_leaders, issue_budget)
    if len(text) <= limit:
        return text
    telegram_safe_limit = max(limit, TELEGRAM_TEXT_LIMIT - 20)
    if symbol_issues and len(text) <= telegram_safe_limit:
        return text

    while issue_budget > 0:
        issue_budget -= 1
        text = render([] if theme_leaders else movers, initial_theme_leaders, issue_budget)
        if len(text) <= telegram_safe_limit:
            return text

    if theme_leaders:
        compact_theme_leaders = [_compact_theme_leader(item) for item in theme_leaders[:7]]
        text = render([], compact_theme_leaders, 0)
        if len(text) <= limit:
            return text

    # Analysis-style mover lines are intentionally more verbose. Use this path
    # only when there is no theme-leader block; otherwise it re-expands verbose
    # leaders and can hide later sections.
    if not theme_leaders:
        for count in range(min(len(movers), 4), 0, -1):
            text = render(movers[:count], issue_limit=0)
            if len(text) <= limit:
                return text

        if movers:
            first = movers[0]
            if len(first) > 420:
                first = first[:420].rstrip()
            text = render([first], issue_limit=0)
        if len(text) <= limit:
            return text

    if theme_leaders:
        for indicator_count in (2, 1):
            ultra_compact = [
                _compact_theme_leader(item, include_indicators=(idx < indicator_count))
                for idx, item in enumerate(theme_leaders[:7])
            ]
            text = render([], ultra_compact, 0)
            if len(text) <= limit:
                return text
        for count in range(min(len(theme_leaders), 7), 0, -1):
            ultra_compact = [
                _compact_theme_leader(item, include_indicators=(idx == 0))
                for idx, item in enumerate(theme_leaders[:count])
            ]
            text = render([], ultra_compact, 0)
            if len(text) <= limit:
                return text

    return text


def build_alert_text(payload: dict[str, Any]) -> str:
    if payload.get("mode") not in ("oil_vix", "market_regime"):
        return _build_sector_telegram_text(payload)

    lines: list[str] = []
    summary = str(payload.get("summary") or "장중 섹터 강약").strip()
    if payload.get("mode") == "oil_vix":
        prefix = "[Oil/VIX Spike Alert]"
    elif payload.get("mode") == "market_regime":
        prefix = "[Market Regime Alert]"
    else:
        prefix = "[Sector Strength Alert]"
    lines.append(f"{prefix} {summary}")

    for text in _select_alert_focus_lines(payload.get("focus") or []):
        lines.append(f"- {text}")

    next_actions = payload.get("next_actions") or []
    if isinstance(next_actions, list) and next_actions:
        lines.append("[액션]")
        for item in next_actions[:3]:
            text = str(item).strip()
            if text:
                lines.append(f"- {text}")

    text = "\n".join(lines).strip()
    if len(text) > min(1800, TELEGRAM_TEXT_LIMIT):
        text = text[:1180].rstrip() + "\n[truncated]"
    return text


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def is_us_regular_market_hours(now: datetime | None = None) -> bool:
    now = _to_utc(now or _now_utc())
    if ZoneInfo is None:
        et = now.astimezone(timezone.utc)
        hour_float = et.hour + et.minute / 60
        return et.weekday() < 5 and 14.5 <= hour_float < 21.0
    et = now.astimezone(ZoneInfo("America/New_York"))
    minutes = et.hour * 60 + et.minute
    return et.weekday() < 5 and (9 * 60 + 30) <= minutes < (16 * 60)


def _load_state(state_file: str | None) -> dict[str, Any]:
    if not state_file:
        return {}
    path = Path(state_file)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state_file: str | None, state: dict[str, Any]) -> None:
    if not state_file:
        return
    path = Path(state_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _first_symbol(rows: Any) -> str:
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        return str(rows[0].get("symbol") or rows[0].get("key") or "")
    return ""


def _response_triggers(response: dict[str, Any]) -> list[str]:
    data = response.get("data") if isinstance(response.get("data"), dict) else {}
    if response.get("mode") == "oil_vix" and isinstance(data, dict):
        oil_vix = data.get("oil_vix") if isinstance(data.get("oil_vix"), dict) else {}
        alerts = oil_vix.get("alerts") if isinstance(oil_vix, dict) else []
        return [str(item) for item in alerts] if isinstance(alerts, list) else []
    return []


def build_alert_signature(response: dict[str, Any]) -> str:
    data = response.get("data") if isinstance(response.get("data"), dict) else {}
    if response.get("mode") == "oil_vix":
        oil_vix = (data or {}).get("oil_vix") if isinstance(data, dict) else {}
        if not isinstance(oil_vix, dict):
            oil_vix = {}
        alerts = oil_vix.get("alerts") or []
        if not isinstance(alerts, list):
            alerts = []
        alert_text = ",".join(str(item) for item in alerts) or "no_alert"
        vix = oil_vix.get("vix") if isinstance(oil_vix.get("vix"), dict) else {}
        oil = oil_vix.get("oil") if isinstance(oil_vix.get("oil"), dict) else {}
        return "|".join(
            str(item or "n/a")
            for item in (
                "oil_vix",
                alert_text,
                vix.get("structure") if isinstance(vix, dict) else None,
                oil.get("state") if isinstance(oil, dict) else None,
            )
        )

    report = ((response.get("data") or {}).get("sector_strength") or {}) if isinstance(response.get("data"), dict) else {}
    if not isinstance(report, dict):
        report = {}
    regime = (report.get("regime") or {}).get("label") if isinstance(report.get("regime"), dict) else None
    strong_theme = _first_symbol(report.get("strong_themes"))
    weak_theme = _first_symbol(report.get("weak_themes"))
    strong_sub_theme = _first_symbol(report.get("strong_sub_themes"))
    weak_sub_theme = _first_symbol(report.get("weak_sub_themes"))
    mover = _first_symbol(report.get("watchlist_movers"))
    if strong_theme or weak_theme or strong_sub_theme or weak_sub_theme or mover:
        return "|".join(str(item or "n/a") for item in (regime, strong_theme, weak_theme, strong_sub_theme, weak_sub_theme, mover))
    strong = _first_symbol(report.get("strong"))
    weak = _first_symbol(report.get("weak"))
    if any((regime, strong, weak)):
        return "|".join(str(item or "n/a") for item in (regime, strong, weak, mover))
    return str(response.get("summary") or "")


def _seconds_since(timestamp: str | None, now: datetime) -> float | None:
    if not timestamp:
        return None
    try:
        previous = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except Exception:
        return None
    return (_to_utc(now) - _to_utc(previous)).total_seconds()


def should_send_alert(response: dict[str, Any], state: dict[str, Any], now: datetime, change_only: bool, cooldown_seconds: int) -> tuple[bool, str, str]:
    signature = build_alert_signature(response)
    if not change_only:
        return True, "send", signature
    last_signature = str(state.get("last_signature") or "")
    elapsed = _seconds_since(state.get("last_sent_at"), now)
    cooldown = max(0, int(cooldown_seconds))
    if last_signature == signature and elapsed is not None and elapsed < cooldown:
        return False, "unchanged_cooldown", signature
    return True, "changed" if last_signature != signature else "cooldown_elapsed", signature


def _updated_state(signature: str, response: dict[str, Any], now: datetime) -> dict[str, Any]:
    return {
        "last_signature": signature,
        "last_summary": response.get("summary"),
        "last_sent_at": _to_utc(now).isoformat(),
    }


def _load_config(env_file: str | None, dry_run: bool, timeout_seconds: int) -> TelegramConfig:
    old_env_file = os.environ.get("TELEGRAM_ENV_FILE")
    old_dry_run = os.environ.get("TELEGRAM_NOTIFY_DRY_RUN")
    old_timeout = os.environ.get("TELEGRAM_NOTIFY_TIMEOUT")
    try:
        if env_file:
            os.environ["TELEGRAM_ENV_FILE"] = env_file
        if dry_run:
            os.environ["TELEGRAM_NOTIFY_DRY_RUN"] = "1"
        os.environ["TELEGRAM_NOTIFY_TIMEOUT"] = str(timeout_seconds)
        config = load_telegram_config()
    finally:
        if old_env_file is None:
            os.environ.pop("TELEGRAM_ENV_FILE", None)
        else:
            os.environ["TELEGRAM_ENV_FILE"] = old_env_file
        if old_dry_run is None:
            os.environ.pop("TELEGRAM_NOTIFY_DRY_RUN", None)
        else:
            os.environ["TELEGRAM_NOTIFY_DRY_RUN"] = old_dry_run
        if old_timeout is None:
            os.environ.pop("TELEGRAM_NOTIFY_TIMEOUT", None)
        else:
            os.environ["TELEGRAM_NOTIFY_TIMEOUT"] = old_timeout

    return replace(
        config,
        dry_run=bool(dry_run or config.dry_run),
        timeout_seconds=max(1, int(timeout_seconds)),
        env_file=env_file or config.env_file,
    )


def run_once(
    response_builder: ResponseBuilder = build_sector_response,
    sender: Sender = send_telegram_message,
    dry_run: bool = False,
    env_file: str | None = None,
    timeout_seconds: int = 15,
    market_hours_only: bool = False,
    change_only: bool = False,
    cooldown_seconds: int = 900,
    state_file: str | None = None,
    trigger_only: bool = False,
    now_provider: Callable[[], datetime] = _now_utc,
) -> dict[str, Any]:
    now = _to_utc(now_provider())
    if market_hours_only and not is_us_regular_market_hours(now):
        return {
            "status": "skipped",
            "reason": "outside_market_hours",
            "mode": "sector_strength",
            "checked_at": now.isoformat(),
        }

    response = response_builder()
    if trigger_only and not _response_triggers(response):
        return {
            "status": "skipped",
            "reason": "no_trigger",
            "mode": response.get("mode", "sector_strength"),
            "summary": response.get("summary"),
            "signature": build_alert_signature(response),
            "checked_at": now.isoformat(),
        }
    state = _load_state(state_file)
    should_send, reason, signature = should_send_alert(response, state, now, change_only=change_only, cooldown_seconds=cooldown_seconds)
    if not should_send:
        return {
            "status": "skipped",
            "reason": reason,
            "mode": response.get("mode", "sector_strength"),
            "summary": response.get("summary"),
            "signature": signature,
            "checked_at": now.isoformat(),
        }

    text = build_alert_text(response)
    config = _load_config(env_file=env_file, dry_run=dry_run, timeout_seconds=timeout_seconds)
    payload = build_telegram_payload({"message": text}, chat_id=config.chat_id, thread_id=config.thread_id)
    telegram_result = sender(payload, config)
    _save_state(state_file, _updated_state(signature, response, now))
    return {
        "status": "ok",
        "reason": reason,
        "mode": response.get("mode", "sector_strength"),
        "summary": response.get("summary"),
        "signature": signature,
        "telegram": telegram_result if dry_run else summarize_telegram_result(telegram_result),
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.interval_seconds <= 0:
        parser.error("--interval-seconds must be positive")

    while True:
        result = run_once(
            response_builder=response_builder_for_mode(args.mode),
            dry_run=args.dry_run,
            env_file=args.env_file,
            timeout_seconds=args.timeout_seconds,
            market_hours_only=args.market_hours_only,
            change_only=args.change_only,
            cooldown_seconds=args.cooldown_seconds,
            state_file=args.state_file,
            trigger_only=args.trigger_only,
        )
        print(json.dumps(result, ensure_ascii=False) if args.as_json else f"{args.mode} alert: {result.get('telegram')}", flush=True)
        if args.once:
            return 0
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
