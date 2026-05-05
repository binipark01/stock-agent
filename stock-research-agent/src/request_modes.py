from __future__ import annotations


def infer_mode(request: str, explicit_mode: str | None = None) -> str:
    if explicit_mode:
        return explicit_mode
    lowered = request.lower()
    if any(keyword in lowered for keyword in ["topic", "topics", "list topics", "peek topic", "데이터허브", "datahub", "data hub"]):
        return "topic_hub"
    if any(keyword in lowered for keyword in ["관심종목 옵션", "워치리스트 옵션", "watchlist options", "options sweep", "옵션 스윕", "옵션스윕"]):
        return "options_sweep"
    if any(keyword in lowered for keyword in ["watchlist", "watch list", "관심종목", "워치리스트", "관심 종목", "훑어봐", "스캔"]):
        return "watchlist_scan"
    if any(keyword in lowered for keyword in ["옵션", "옵션판", "콜월", "풋월", "option", "options", "call wall", "put wall", "max pain"]):
        return "options_flow"
    if any(keyword in lowered for keyword in ["데이마켓", "데이장", "주간거래", "주간장", "주간 거래", "지금 열려있는 장", "토스 가격"]):
        return "day_market"
    if any(keyword in lowered for keyword in ["유가", "vix", "wti", "brent", "브렌트", "오일", "oil", "변동성"]):
        return "oil_vix"
    if any(keyword in lowered for keyword in ["market regime", "시장 레짐", "장 레짐", "risk-on", "risk off", "risk-off", "리스크온", "리스크오프"]):
        return "market_regime"
    if any(keyword in lowered for keyword in ["sector strength", "sector_strength", "섹터 강약", "섹터별", "강한 섹터", "약한 섹터", "장중 섹터", "주도섹터", "주도 섹터", "주도 테마", "테마 랭킹"]):
        return "sector_strength"
    if any(keyword in lowered for keyword in ["yfinance", "yf pack", "yf팩", "야후팩"]):
        return "yfinance_pack"
    if any(keyword in lowered for keyword in ["sec", "edgar", "공시", "filing", "filings", "8-k", "10-q", "10-k", "s-3"]):
        return "sec_filings"
    if any(keyword in lowered for keyword in ["수집", "ingest", "sync"]):
        return "ingest"
    if any(keyword in lowered for keyword in ["세이브티커", "saveticker", "save"]):
        if any(keyword in lowered for keyword in ["중요", "속보", "딱딱", "alert", "breaking"]):
            return "saveticker_breaking"
        return "saveticker_sync"
    if any(keyword in lowered for keyword in ["토스", "toss", "지수 뉴스", "tossinvest"]):
        return "toss_sync"
    if any(keyword in lowered for keyword in ["실적 프리뷰", "earnings preview", "preview pack", "프리뷰"]):
        return "earnings_preview"
    if any(keyword in lowered for keyword in ["실적", "earnings", "어닝"]):
        return "earnings"
    if any(keyword in lowered for keyword in ["threads", "스레드", "팔로잉", "social"]):
        return "social_search"
    if any(keyword in lowered for keyword in ["왜", "why ", "봐야 해", "체크해야 해"]):
        return "why_symbol"
    if any(keyword in lowered for keyword in ["overnight", "야간", "night recap", "overnight recap"]):
        return "overnight_recap"
    if any(keyword in lowered for keyword in ["뭐가 달라", "무슨 변화", "변화", "changed", "what changed"]):
        return "what_changed"
    if any(keyword in lowered for keyword in ["비교", " vs ", "뭐 먼저", "which first"]):
        return "compare"
    if any(keyword in lowered for keyword in ["차트", "기술적", "technical", "setup", "rsi", "macd"]):
        return "technical_snapshot"
    if any(keyword in lowered for keyword in ["브리핑", "장전", "장후", "brief"]):
        return "brief"
    if any(keyword in lowered for keyword in ["포트폴리오", "보유", "리스크", "guard"]):
        return "portfolio_guard"
    if any(keyword in lowered for keyword in ["소식", "정보", "업데이트", "알려줘"]):
        return "brief"
    return "symbol_review"
