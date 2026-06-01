from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModeRule:
    mode: str
    keywords: tuple[str, ...]
    required: tuple[str, ...] = ()


def _has_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _match_rule(text: str, rule: ModeRule) -> bool:
    if not _has_any(text, rule.keywords):
        return False
    return not rule.required or _has_any(text, rule.required)


def _infer_from_rules(text: str, rules: tuple[ModeRule, ...]) -> str | None:
    for rule in rules:
        if _match_rule(text, rule):
            return rule.mode
    return None


US_MODE_RULES: tuple[ModeRule, ...] = (
    ModeRule("topic_hub", ("topic", "topics", "list topics", "peek topic", "데이터허브", "datahub", "data hub")),
    ModeRule("options_sweep", ("관심종목 옵션", "워치리스트 옵션", "watchlist options", "options sweep", "옵션 스윕", "옵션스윕")),
    ModeRule("watchlist_scan", ("watchlist", "watch list", "관심종목", "워치리스트", "관심 종목", "훑어봐", "스캔", "국장 테마", "국장테마", "한국장 테마", "주식크루 국장")),
    ModeRule("options_flow", ("옵션", "옵션판", "콜월", "풋월", "option", "options", "call wall", "put wall", "max pain")),
    ModeRule("day_market", ("데이마켓", "데이장", "주간거래", "주간장", "주간 거래", "지금 열려있는 장", "토스 가격", "토스 정보", "토스 주가", "토스 스냅샷", "토스나")),
    ModeRule("oil_vix", ("유가", "vix", "wti", "brent", "브렌트", "오일", "oil", "변동성")),
    ModeRule("market_regime", ("market regime", "시장 레짐", "장 레짐", "risk-on", "risk off", "risk-off", "리스크온", "리스크오프")),
    ModeRule("closing_review", ("마감 복기", "장마감 복기", "장 후 복기", "장후 복기", "closing review", "closing_review")),
    ModeRule("premarket_plan", ("프리장 플랜", "프리마켓 플랜", "장전 플랜", "premarket plan", "premarket_plan")),
    ModeRule("sector_intelligence", ("주도섹터 인텔리전스", "주도 섹터 인텔리전스", "섹터 인텔리전스", "sector intelligence", "sector_intelligence", "주도 지속성", "테마 지속성", "주도섹터 지속성")),
    ModeRule("sector_strength", ("sector strength", "sector_strength", "섹터 강약", "섹터별", "강한 섹터", "약한 섹터", "장중 섹터", "주도섹터", "주도 섹터", "주도 테마", "테마 랭킹")),
    ModeRule("openbb_history", ("openbb", "open bb", "오픈비비", "오픈 bb"), ("history", "historical", "hist", "과거", "가격 이력", "ohlcv")),
    ModeRule("openbb_profile", ("openbb", "open bb", "오픈비비", "오픈 bb"), ("profile", "프로필", "회사", "기업개요", "기업 개요")),
    ModeRule("openbb_quote", ("openbb", "open bb", "오픈비비", "오픈 bb")),
    ModeRule("yfinance_pack", ("yfinance", "yf pack", "yf팩", "야후팩")),
    ModeRule("sec_filings", ("sec", "edgar", "공시", "filing", "filings", "8-k", "10-q", "10-k", "s-3")),
    ModeRule("ingest", ("수집", "ingest", "sync")),
    ModeRule("saveticker_breaking", ("세이브티커", "saveticker", "save"), ("중요", "속보", "딱딱", "alert", "breaking")),
    ModeRule("saveticker_sync", ("세이브티커", "saveticker", "save")),
    ModeRule("toss_sync", ("토스", "toss", "지수 뉴스", "tossinvest")),
    ModeRule("earnings_preview", ("실적 프리뷰", "earnings preview", "preview pack", "프리뷰")),
    ModeRule("earnings", ("실적", "earnings", "어닝")),
    ModeRule("threads_view_scan", ("스레더 분석", "스레더들", "threads view", "threads_view", "threads scan", "threads_scan", "소셜 컨센서스")),
    ModeRule("social_search", ("threads", "스레드", "팔로잉", "social")),
    ModeRule("why_symbol", ("왜", "why ", "봐야 해", "체크해야 해")),
    ModeRule("overnight_recap", ("overnight", "야간", "night recap", "overnight recap")),
    ModeRule("what_changed", ("뭐가 달라", "무슨 변화", "변화", "changed", "what changed")),
    ModeRule("compare", ("비교", " vs ", "뭐 먼저", "which first")),
    ModeRule("technical_snapshot", ("차트", "기술적", "technical", "setup", "rsi", "macd")),
    ModeRule("brief", ("브리핑", "장전", "장후", "brief")),
    ModeRule("portfolio_guard", ("포트폴리오", "보유", "리스크", "guard")),
    ModeRule("brief", ("소식", "정보", "업데이트", "알려줘")),
)


def infer_mode(request: str, explicit_mode: str | None = None) -> str:
    if explicit_mode:
        return explicit_mode
    lowered = request.lower()
    return _infer_from_rules(lowered, US_MODE_RULES) or "symbol_review"
