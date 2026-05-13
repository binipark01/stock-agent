from __future__ import annotations


def infer_mode(request: str, explicit_mode: str | None = None) -> str:
    if explicit_mode:
        return explicit_mode
    lowered = request.lower()
    if any(keyword in lowered for keyword in ["주도테마", "주도 테마", "테마에 돈", "돈 들어오", "대장주", "테마 대장", "어느 테마", "어떤 테마"]):
        if any(keyword in lowered for keyword in ["국장", "한국장", "코스피", "코스닥", "krx"]):
            return "krx_theme_leader_scan"
    if any(keyword in lowered for keyword in ["검색식", "조건검색", "조건 검색", "condition scan", "조건식"]):
        if any(keyword in lowered for keyword in ["국장", "한국장", "코스피", "코스닥", "krx", "만쥬", "종가배팅", "수급", "테마", "대장", "부대장", "continuation", "컨티뉴에이션"]):
            return "krx_condition_scan"
    if any(keyword in lowered for keyword in ["주요종목 수급", "주요 종목 수급", "고정 수급", "고정감시", "고정 감시", "랭킹 누락", "대형주 수급", "주요종목 감시", "주요 종목 감시"]):
        if any(keyword in lowered for keyword in ["국장", "한국장", "krx", "수급", "프로그램", "외인", "기관", "순매수", "감시", "모니터"]):
            return "krx_major_flow_watch"
    if any(keyword in lowered for keyword in ["nxt", "nxt장", "nxt 장", "종가 이후", "장끝나고", "장 끝나고", "시간외", "시간 외", "세션 수급"]):
        if any(keyword in lowered for keyword in ["수급", "변화", "감시", "모니터", "프로그램", "외인", "외국인", "기관", "순매수", "순매도"]):
            return "krx_session_flow_watch"
    if any(keyword in lowered for keyword in ["5분마다", "몇분마다", "몇 분마다", "실시간", "모니터", "watch", "감시"]):
        if any(keyword in lowered for keyword in ["수급 랭킹", "수급 상위", "매매 상위", "순매수 상위", "거래대금 상위", "프로그램 상위", "랭킹"]):
            return "krx_flow_rank_watch"
    if any(keyword in lowered for keyword in ["5분마다", "몇분마다", "몇 분마다", "실시간", "모니터", "watch"]):
        if any(keyword in lowered for keyword in ["수급", "프로그램", "외인", "기관", "순매수", "순매도", "체결강도", "호가"]):
            return "krx_flow_watch"
    if any(keyword in lowered for keyword in ["수급 상위", "수급 랭킹", "매매 상위", "순매수 상위", "순매도 상위", "거래대금 상위", "프로그램 상위", "프로그램 순매수 상위", "외국인 기관 매매 상위", "외인 기관 매매 상위"]):
        if any(keyword in lowered for keyword in ["국장", "한국장", "코스피", "코스닥", "krx", "수급", "프로그램", "외국인", "외인", "기관", "거래대금"]):
            return "krx_flow_rank_scan"
    krx_symbol_terms = ["삼성", "삼성전자", "하이닉스", "현대차", "현대자동차", "현대모비스", "기아", "005930", "000660", "005380", "012330", "000270"]
    if any(keyword in lowered for keyword in ["어때", "뉴스", "소식", "이슈", "템플릿"]):
        if any(keyword in lowered for keyword in krx_symbol_terms):
            return "krx_symbol_brief"
    if any(keyword in lowered for keyword in ["오늘 기관", "기관은", "기관 샀", "기관 팔", "프로그램쪽", "프로그램 쪽", "개별 수급", "종목 수급", "외국인", "외인", "수급"]):
        if any(keyword in lowered for keyword in krx_symbol_terms):
            return "krx_symbol_flow_v2"
    if any(keyword in lowered for keyword in ["수급", "프로그램 순매수", "프로그램 순매도", "프로그램 매매", "외인 기관", "외국인 기관", "기관 순매수", "외인 순매수", "외국인 순매수", "순매수 확인"]):
        if any(keyword in lowered for keyword in ["국장", "한국장", "삼성", "하이닉스", "005930", "000660", "코스피", "코스닥", "krx"]):
            return "krx_flow_snapshot"
    if any(keyword in lowered for keyword in ["topic", "topics", "list topics", "peek topic", "데이터허브", "datahub", "data hub"]):
        return "topic_hub"
    if any(keyword in lowered for keyword in ["관심종목 옵션", "워치리스트 옵션", "watchlist options", "options sweep", "옵션 스윕", "옵션스윕"]):
        return "options_sweep"
    if any(keyword in lowered for keyword in ["watchlist", "watch list", "관심종목", "워치리스트", "관심 종목", "훑어봐", "스캔", "국장 테마", "국장테마", "한국장 테마", "주식크루 국장"]):
        return "watchlist_scan"
    if any(keyword in lowered for keyword in ["옵션", "옵션판", "콜월", "풋월", "option", "options", "call wall", "put wall", "max pain"]):
        return "options_flow"
    if any(keyword in lowered for keyword in ["데이마켓", "데이장", "주간거래", "주간장", "주간 거래", "지금 열려있는 장", "토스 가격", "토스 정보", "토스 주가", "토스 스냅샷", "토스나"]):
        return "day_market"
    if any(keyword in lowered for keyword in ["유가", "vix", "wti", "brent", "브렌트", "오일", "oil", "변동성"]):
        return "oil_vix"
    if any(keyword in lowered for keyword in ["market regime", "시장 레짐", "장 레짐", "risk-on", "risk off", "risk-off", "리스크온", "리스크오프"]):
        return "market_regime"
    if any(keyword in lowered for keyword in ["마감 복기", "장마감 복기", "장 후 복기", "장후 복기", "closing review", "closing_review"]):
        return "closing_review"
    if any(keyword in lowered for keyword in ["프리장 플랜", "프리마켓 플랜", "장전 플랜", "premarket plan", "premarket_plan"]):
        return "premarket_plan"
    if any(keyword in lowered for keyword in ["주도섹터 인텔리전스", "주도 섹터 인텔리전스", "섹터 인텔리전스", "sector intelligence", "sector_intelligence", "주도 지속성", "테마 지속성", "주도섹터 지속성"]):
        return "sector_intelligence"
    if any(keyword in lowered for keyword in ["sector strength", "sector_strength", "섹터 강약", "섹터별", "강한 섹터", "약한 섹터", "장중 섹터", "주도섹터", "주도 섹터", "주도 테마", "테마 랭킹"]):
        return "sector_strength"
    if any(keyword in lowered for keyword in ["openbb", "open bb", "오픈비비", "오픈 bb"]):
        if any(keyword in lowered for keyword in ["history", "historical", "hist", "과거", "가격 이력", "ohlcv"]):
            return "openbb_history"
        if any(keyword in lowered for keyword in ["profile", "프로필", "회사", "기업개요", "기업 개요"]):
            return "openbb_profile"
        return "openbb_quote"
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
    if any(keyword in lowered for keyword in ["스레더 분석", "스레더들", "threads view", "threads_view", "threads scan", "threads_scan", "소셜 컨센서스"]):
        return "threads_view_scan"
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
