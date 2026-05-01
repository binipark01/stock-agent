from __future__ import annotations


def infer_mode(request: str, explicit_mode: str | None = None) -> str:
    if explicit_mode:
        return explicit_mode
    lowered = request.lower()
    if any(keyword in lowered for keyword in ["topic", "topics", "list topics", "peek topic", "데이터허브", "datahub", "data hub"]):
        return "topic_hub"
    if any(keyword in lowered for keyword in ["sector strength", "sector_strength", "섹터 강약", "섹터별", "강한 섹터", "약한 섹터", "장중 섹터", "시장 레짐", "market regime"]):
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
    if any(keyword in lowered for keyword in ["reddit", "레딧"]):
        return "reddit_search"
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
