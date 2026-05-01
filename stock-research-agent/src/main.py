import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .repository import (
        fetch_latest_earnings,
        fetch_latest_news,
        fetch_latest_saveticker_items,
        fetch_latest_snapshot,
        fetch_latest_toss_indices,
        fetch_latest_toss_news,
        fetch_upcoming_earnings,
        get_connection,
        insert_earnings_event,
        insert_news_item,
        insert_price_snapshot,
    )
    from .market_data import fetch_earnings_event, fetch_price_snapshot, fetch_symbol_news
    from .tossinvest_data import build_toss_market_brief, map_toss_news_item, run_toss_ingest, score_toss_news_item
    from .earnings_preview import build_earnings_preview
    from .saveticker_data import build_saveticker_brief, build_saveticker_important_breaking, map_saveticker_item, run_saveticker_ingest, score_saveticker_item
    from .threads_social import search_threads_seed_accounts
    from .yfinance_data import build_yfinance_focus_lines, fetch_yfinance_market_pack
    from .sec_filings import build_sec_focus_lines, fetch_sec_filings_pack
    from .topic_hub import build_topic_hub_focus_lines
    from .sector_strength import build_sector_strength_report, fetch_sector_strength_quotes
    from .request_modes import infer_mode
    from .technical_snapshot import build_technical_snapshot
except ImportError:  # direct script execution
    from repository import (
        fetch_latest_earnings,
        fetch_latest_news,
        fetch_latest_saveticker_items,
        fetch_latest_snapshot,
        fetch_latest_toss_indices,
        fetch_latest_toss_news,
        fetch_upcoming_earnings,
        get_connection,
        insert_earnings_event,
        insert_news_item,
        insert_price_snapshot,
    )
    from market_data import fetch_earnings_event, fetch_price_snapshot, fetch_symbol_news
    from tossinvest_data import build_toss_market_brief, map_toss_news_item, run_toss_ingest, score_toss_news_item
    from earnings_preview import build_earnings_preview
    from saveticker_data import build_saveticker_brief, build_saveticker_important_breaking, map_saveticker_item, run_saveticker_ingest, score_saveticker_item
    from threads_social import search_threads_seed_accounts
    from yfinance_data import build_yfinance_focus_lines, fetch_yfinance_market_pack
    from sec_filings import build_sec_focus_lines, fetch_sec_filings_pack
    from topic_hub import build_topic_hub_focus_lines
    from sector_strength import build_sector_strength_report, fetch_sector_strength_quotes
    from request_modes import infer_mode
    from technical_snapshot import build_technical_snapshot


DEFAULT_SYMBOLS = ["NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "META", "GOOGL", "AMD"]
DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "stock_agent.db"
DEFAULT_WATCHLIST_PATH = Path(__file__).resolve().parents[1] / "config" / "watchlist.json"


def load_watchlist(path: str | Path | None = None) -> dict[str, list[str]]:
    watchlist_path = Path(path or DEFAULT_WATCHLIST_PATH)
    if not watchlist_path.exists():
        return {"watchlist": DEFAULT_SYMBOLS[:3], "portfolio": []}
    try:
        data = json.loads(watchlist_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"watchlist": DEFAULT_SYMBOLS[:3], "portfolio": []}
    if not isinstance(data, dict):
        return {"watchlist": DEFAULT_SYMBOLS[:3], "portfolio": []}
    watchlist = data.get("watchlist") or DEFAULT_SYMBOLS[:3]
    portfolio = data.get("portfolio") or []
    return {
        "watchlist": [str(item) for item in watchlist],
        "portfolio": [str(item) for item in portfolio],
    }


def parse_request_payload(raw_request: str) -> dict[str, Any]:
    text = raw_request.strip()
    if text.startswith("{"):
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    return {"request": text}



def infer_symbols(request: str, provided_symbols: list[str] | None = None, watchlist_path: str | Path | None = None) -> list[str]:
    if provided_symbols:
        return provided_symbols
    lowered = request.lower()
    matched: list[str] = []
    aliases = {
        "NVDA": ["nvda", "nvidia", "엔비디아"],
        "TSLA": ["tsla", "tesla", "테슬라"],
        "AAPL": ["aapl", "apple", "애플"],
        "MSFT": ["msft", "microsoft", "마이크로소프트"],
        "AMZN": ["amzn", "amazon", "아마존"],
        "META": ["meta", "facebook", "메타"],
        "GOOGL": ["googl", "google", "alphabet", "구글"],
        "AMD": ["amd"],
        "AVGO": ["avgo", "broadcom", "브로드컴"],
        "TSM": ["tsm", "tsmc"],
        "PLTR": ["pltr", "palantir", "팔란티어"],
        "BMNR": ["bmnr", "bitmine", "비트마인"],
        "QQQ": ["qqq", "나스닥 etf"],
        "SPY": ["spy", "s&p etf", "sp500 etf"],
        "SOXX": ["soxx", "반도체 etf"],
        "005930.KS": ["005930", "삼성전자", "samsung electronics", "samsung"],
        "000660.KS": ["000660", "sk hynix", "hynix", "하이닉스"],
    }
    for ticker, keywords in aliases.items():
        if any(keyword.lower() in lowered for keyword in keywords):
            matched.append(ticker)
    if matched:
        return matched
    return load_watchlist(watchlist_path)["watchlist"]


def extract_social_search_query(request_text: str, provided_symbols: list[str] | None = None) -> str:
    if provided_symbols:
        return provided_symbols[0]
    query = request_text
    for token in ["스레드", "threads", "threads에서", "찾아줘", "검색", "social", "팔로잉", "목록에서", "알려줘"]:
        query = query.replace(token, " ")
    query = re.sub(r"\s+", " ", query).strip()
    return query or request_text.strip() or "NVDA"


def build_social_search_payload(request_text: str, symbols: list[str], recent_days: int = 14) -> tuple[str, list[str], list[str]]:
    query = extract_social_search_query(request_text, provided_symbols=symbols)
    hits = search_threads_seed_accounts(query, recent_days=recent_days)
    focus = [f"최근 Threads 반응: seed 계정 기준 최근 {recent_days}일 검색 / query={query}"]
    if not hits:
        focus.append(f"최근 Threads 반응: 최근 {recent_days}일 기준 seed 계정 언급 없음")
        next_actions = [
            "검색어를 ticker / 한글 종목명 / 회사명으로 바꿔서 다시 조회",
            "최근 1~2주 언급이 없으면 뉴스/공시 쪽을 먼저 확인",
            "필요하면 코인/미국주식 계정군만 별도로 좁혀서 재검색",
        ]
        summary = f"seed 계정 기준 Threads 최근 반응을 찾았지만 {query} 언급은 없었습니다."
        return summary, focus, next_actions

    for item in hits[:5]:
        focus.append(f"@{item['handle']} / {item['days_ago']}일 전 / {item['text']}")
    next_actions = [
        "가장 최근 언급 계정부터 원문 맥락 확인",
        "같은 종목이 뉴스/공시에도 같이 나오는지 교차검증",
        "최근 1~2주 언급 수가 적으면 모멘텀 약함으로 해석",
    ]
    summary = f"seed 계정 기준 Threads 최근 반응을 정리했습니다: {query}"
    return summary, focus, next_actions


def build_social_signal_line(symbols: list[str], recent_days: int = 14) -> str | None:
    if not symbols:
        return None
    query = symbols[0]
    try:
        hits = search_threads_seed_accounts(query, recent_days=recent_days)
    except Exception:
        return f"Social Signal: seed 계정 검색 실패 / {query} / 공개 Threads 접근 제한"
    if not hits:
        return f"Social Signal: seed 계정 최근 {recent_days}일 {query} 언급 없음"
    top = hits[0]
    return f"Social Signal: @{top['handle']} {top['days_ago']}일 전 / {top['text']}"


def should_include_social_signal(request_text: str, mode: str) -> bool:
    if mode != "brief":
        return False
    lowered = request_text.lower()
    return any(keyword in lowered for keyword in ["소식", "정보", "업데이트", "찾아줘", "알려줘"])


def build_symbol_summary(symbol: str, portfolio: set[str], db_path: Path = DEFAULT_DB_PATH) -> dict[str, Any]:
    conn = get_connection(db_path)
    snapshot = fetch_latest_snapshot(conn, symbol)
    news_rows = fetch_latest_news(conn, symbol, limit=1)
    earnings_row = fetch_latest_earnings(conn, symbol)
    conn.close()

    if snapshot:
        bullish = f"현재가 {snapshot['price']:.2f}, 변동률 {snapshot['pct_change']:+.2f}% 흐름 체크"
        bearish = snapshot["note"] or "최근 수급/실적 기대 과열 여부 확인 필요"
        catalyst = "최근 저장된 뉴스와 이벤트 재확인"
    else:
        fallback = {
            "NVDA": ("AI 인프라 수요와 데이터센터 투자 기대가 강하다.", "실적 기대 과열과 capex 둔화 기사에 민감하다.", "실적 발표와 가이던스가 가장 큰 촉매다."),
            "TSLA": ("에너지·자율주행 서사가 다시 붙으면 변동성이 커진다.", "마진 압박과 판매 둔화 논리가 반복된다.", "월간 판매 데이터와 마진 코멘트가 중요하다."),
            "AAPL": ("서비스 매출과 자사주 매입 서사가 방어력을 준다.", "중국 판매 둔화와 밸류에이션 부담이 남아 있다.", "실적 발표와 신제품 사이클 체크가 필요하다."),
            "MSFT": ("AI·클라우드 투자와 Copilot 확장이 핵심 강세 논리다.", "대규모 capex 부담과 성장 둔화 우려를 같이 봐야 한다.", "Azure 성장률과 AI monetization이 핵심 촉매다."),
            "AMZN": ("AWS 성장 회복과 광고 사업 확장이 방어력을 준다.", "리테일 마진 변동성과 클라우드 경쟁 심화가 부담이다.", "AWS 실적과 가이던스가 핵심 촉매다."),
            "META": ("광고 회복과 AI 추천 효율 개선이 강세 포인트다.", "AI 투자비 증가와 규제 리스크가 남아 있다.", "광고 단가와 AI capex 코멘트가 중요하다."),
            "GOOGL": ("검색·클라우드 이익 체력이 여전히 강하다.", "AI 경쟁 격화와 규제/독점 이슈가 부담이다.", "클라우드 수익성과 검색 AI 전략이 촉매다."),
            "AMD": ("서버 CPU/GPU 점유율 확대 기대가 있다.", "엔비디아 대비 AI 모멘텀 약세가 리스크다.", "데이터센터 매출 성장률이 핵심이다."),
            "AVGO": ("AI 네트워킹·커스텀 칩 수혜가 강세 포인트다.", "고평가 부담과 대형 고객 의존도를 봐야 한다.", "AI 매출 비중 업데이트가 중요하다."),
            "TSM": ("첨단 공정 수요와 AI 반도체 위탁생산 모멘텀이 강하다.", "지정학 리스크와 고객 집중도가 부담이다.", "가동률과 가이던스가 핵심 촉매다."),
            "PLTR": ("정부·기업 AI 도입 수혜 기대가 크다.", "밸류에이션 과열과 기대 선반영이 부담이다.", "상업 부문 성장률과 수주가 중요하다."),
            "QQQ": ("대형 기술주 강세를 가장 직접적으로 반영한다.", "빅테크 집중 리스크가 높다.", "금리와 대형 기술주 실적이 촉매다."),
            "SPY": ("미국 대형주 전체 흐름을 보기 좋다.", "매크로와 금리 충격을 그대로 받는다.", "고용·물가·FOMC가 핵심이다."),
            "SOXX": ("AI 반도체 사이클을 압축해서 본다.", "반도체 밸류체인 변동성이 크다.", "엔비디아·TSM·ASML 이벤트가 중요하다."),
            "005930.KS": ("메모리 업황 회복과 HBM 수요 기대가 핵심이다.", "반도체 업황 회복 속도 지연 리스크를 봐야 한다.", "메모리 가격 반등과 실적 코멘트가 중요하다."),
            "000660.KS": ("HBM 공급 우위와 서버 메모리 수요가 촉매다.", "HBM 기대는 크지만 업황 변동성도 같이 크다.", "HBM 고객사 수요와 실적 발표가 핵심이다."),
        }
        bullish, bearish, catalyst = fallback.get(symbol, ("핵심 수요 서사가 살아 있는지 확인 필요.", "기대치 과열 여부를 먼저 체크해야 한다.", "실적/뉴스 이벤트 체크 필요."))

    news_headline = news_rows[0]["headline"] if news_rows else "저장된 뉴스 없음"
    earnings_text = "저장된 실적 일정 없음"
    if earnings_row:
        session_map = {"after_close": "장마감 후", "before_open": "장시작 전", "unknown": "시간 미정"}
        session_label = session_map.get(earnings_row["session"], "시간 미정")
        earnings_text = f"{earnings_row['earnings_date']} / {session_label}"
    risk_level = "high" if symbol in portfolio else "medium"
    return {
        "symbol": symbol,
        "bullish": bullish,
        "bearish": bearish,
        "catalyst": catalyst,
        "risk": "보유 종목이라 우선 감시" if symbol in portfolio else "워치리스트 기준 관찰",
        "risk_level": risk_level,
        "headline": news_headline,
        "earnings": earnings_text,
    }


def run_ingest(symbols: list[str], db_path: Path = DEFAULT_DB_PATH) -> dict[str, Any]:
    conn = get_connection(db_path)
    stored_prices = 0
    stored_news = 0
    stored_earnings = 0

    for symbol in symbols:
        snapshot = fetch_price_snapshot(symbol)
        insert_price_snapshot(conn, **snapshot)
        stored_prices += 1
        for news in fetch_symbol_news(symbol):
            insert_news_item(conn, **news)
            stored_news += 1
        earnings_event = fetch_earnings_event(symbol)
        insert_earnings_event(conn, **earnings_event)
        stored_earnings += 1

    conn.commit()
    conn.close()
    return {
        "symbols": len(symbols),
        "prices": len(symbols),
        "stored_prices": stored_prices,
        "stored_news": stored_news,
        "stored_earnings": stored_earnings,
        "db_path": str(db_path),
    }



def _infer_brief_phase(request_text: str) -> str:
    lowered = request_text.lower()
    if "장후" in request_text or "after market" in lowered or "after close" in lowered:
        return "after_close"
    return "pre_market"


def _parse_freshness_minutes(published_text: str | None) -> int:
    text = (published_text or "").strip().lower()
    minute_match = re.search(r"(\d+)\s*분", text)
    if minute_match:
        return int(minute_match.group(1))
    hour_match = re.search(r"(\d+)\s*시간", text)
    if hour_match:
        return int(hour_match.group(1)) * 60
    if "방금" in text or "just" in text:
        return 1
    absolute_match = re.search(r"(\d{4})\.\s*(\d{2})\.\s*(\d{2})\.\s*(\d{2}):(\d{2})", text)
    if absolute_match:
        published_at = datetime(
            int(absolute_match.group(1)),
            int(absolute_match.group(2)),
            int(absolute_match.group(3)),
            int(absolute_match.group(4)),
            int(absolute_match.group(5)),
            tzinfo=timezone.utc,
        )
        delta_minutes = int((datetime.now(timezone.utc) - published_at).total_seconds() // 60)
        return max(delta_minutes, 1)
    return 24 * 60


def _normalize_published_text(published_text: str | None) -> str:
    raw_text = (published_text or "").strip()
    if not raw_text:
        return "시간 정보 없음"
    absolute_match = re.search(r"(\d{4})\.\s*(\d{2})\.\s*(\d{2})\.\s*(\d{2}):(\d{2})", raw_text)
    if not absolute_match:
        return raw_text
    minutes = _parse_freshness_minutes(raw_text)
    if minutes < 60:
        return f"{minutes}분 전"
    if minutes < 24 * 60:
        return f"{minutes // 60}시간 전"
    return f"{minutes // (24 * 60)}일 전"


def _freshness_score(published_text: str | None) -> int:
    minutes = _parse_freshness_minutes(published_text)
    if minutes <= 10:
        return 5
    if minutes <= 30:
        return 4
    if minutes <= 120:
        return 3
    if minutes <= 360:
        return 2
    return 1


def _freshness_label(published_text: str | None) -> str:
    minutes = _parse_freshness_minutes(published_text)
    if minutes <= 10:
        return "초신속"
    if minutes <= 30:
        return "신속"
    if minutes <= 120:
        return "단기"
    if minutes <= 360:
        return "지연"
    return "오래됨"


def _source_reliability_score(source_name: str | None, source: str | None = None) -> int:
    name = (source_name or source or "").lower()
    if any(token in name for token in ["reuters", "로이터", "ap", "bloomberg", "블룸버그"]):
        return 3
    if any(token in name for token in ["연합", "뉴스", "infomax", "이데일리"]):
        return 2
    return 1


def _source_reliability_label(source_name: str | None, source: str | None = None) -> str:
    score = _source_reliability_score(source_name, source)
    if score >= 3:
        return "높음"
    if score == 2:
        return "보통"
    return "낮음"


def _headline_priority_score(item: dict, portfolio: set[str], watchlist: set[str]) -> int:
    item_symbols = set(item.get("mapped_symbols") or item.get("tickers") or [])
    base = 0
    if portfolio and item_symbols.intersection(portfolio):
        base += 50
    elif watchlist and item_symbols.intersection(watchlist):
        base += 30
    base += _freshness_score(item.get("published_text")) * 10
    base += _source_reliability_score(item.get("source_name"), item.get("source"))
    if item.get("kind") == "속보":
        base += 5
    if item.get("is_rumor"):
        base -= 8
    return base


def _load_breaking_candidates(db_path: Path, portfolio: set[str], watchlist: set[str]) -> list[dict]:
    conn = get_connection(db_path)
    toss_rows = fetch_latest_toss_news(conn, limit=5)
    saveticker_rows = fetch_latest_saveticker_items(conn, limit=5)
    conn.close()

    candidates: list[dict] = []
    for row in toss_rows:
        mapped = map_toss_news_item(dict(row))
        mapped["_priority_score"] = _headline_priority_score(mapped, portfolio, watchlist)
        candidates.append(mapped)
    for row in saveticker_rows:
        mapped = map_saveticker_item(
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
        mapped["_priority_score"] = _headline_priority_score(mapped, portfolio, watchlist)
        candidates.append(mapped)
    return candidates


def _pick_top_breaking_candidate(db_path: Path, portfolio: set[str], watchlist: set[str], min_freshness_score: int = 4) -> dict | None:
    candidates = _load_breaking_candidates(db_path, portfolio, watchlist)
    if not candidates:
        return None
    candidates.sort(key=lambda item: (-_freshness_score(item.get("published_text")), -item.get("_priority_score", 0)))
    top = candidates[0]
    if _freshness_score(top.get("published_text")) < min_freshness_score:
        return None
    return top


def build_watchlist_movers(symbols: list[str], summaries: list[dict[str, Any]], portfolio: set[str], db_path: Path = DEFAULT_DB_PATH, watchlist: set[str] | None = None) -> str | None:
    if not symbols:
        return None
    watchlist = watchlist or set(symbols)
    top_breaking = _pick_top_breaking_candidate(db_path, portfolio, watchlist, min_freshness_score=1)
    breaking_symbols = set(top_breaking.get("mapped_symbols") or top_breaking.get("tickers") or []) if top_breaking else set()

    ranked: list[tuple[int, str, str]] = []
    for item in summaries:
        symbol = item["symbol"]
        score = 0
        reason = "관찰"
        if symbol in portfolio:
            score += 100
            reason = "보유"
        elif symbol in breaking_symbols:
            score += 60
            reason = "속보"
        if item.get("earnings") and item["earnings"] != "저장된 실적 일정 없음":
            score += 15
            if reason == "관찰":
                reason = "실적"
        if item.get("headline") and item["headline"] != "저장된 뉴스 없음":
            score += 10
            if reason == "관찰":
                reason = "뉴스"
        ranked.append((score, symbol, reason))

    ranked.sort(key=lambda entry: (-entry[0], symbols.index(entry[1])))
    top_parts = [f"{symbol}({reason})" for _, symbol, reason in ranked[:3]]
    return f"오늘 먼저 볼 종목: {', '.join(top_parts)}"


def build_portfolio_brief(symbols: list[str], summaries: list[dict[str, Any]], portfolio: set[str]) -> str | None:
    portfolio_items = [item for item in summaries if item["symbol"] in portfolio]
    if not portfolio_items:
        return None
    top_parts = [f"{item['symbol']} / {item['headline']} / {item['bearish']}" for item in portfolio_items[:3]]
    return f"보유종목 브리핑: {' ; '.join(top_parts)}"


def build_catalyst_board(db_path: Path = DEFAULT_DB_PATH, portfolio: set[str] | None = None, watchlist: set[str] | None = None) -> str | None:
    portfolio = portfolio or set()
    watchlist = watchlist or set()
    candidates = _load_breaking_candidates(db_path, portfolio, watchlist)
    if not candidates:
        return None

    rising = next((item for item in sorted(candidates, key=lambda item: -int(item.get("_priority_score", 0))) if not item.get("is_rumor")), None)
    rumor = next((item for item in candidates if item.get("is_rumor")), None)
    macro = next((item for item in candidates if "macro" in (item.get("mapped_themes") or [])), None)

    parts = []
    if rising:
        parts.append(f"상승 {rising['headline']}")
    if rumor:
        parts.append(f"루머 {rumor['headline']}")
    if macro:
        parts.append(f"매크로 {macro['headline']}")
    if not parts:
        return None
    return f"Catalyst Board: {' / '.join(parts)}"


def build_earnings_nearby_alert(summaries: list[dict[str, Any]]) -> str | None:
    nearby = [item for item in summaries if item.get("earnings") and item["earnings"] != "저장된 실적 일정 없음"]
    if not nearby:
        return None
    top_parts = [f"{item['symbol']} {item['earnings']}" for item in nearby[:3]]
    return f"실적 임박: {', '.join(top_parts)}"


def _compare_symbol_score(summary: dict[str, Any], technical: dict[str, Any], portfolio: set[str]) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    symbol = summary["symbol"]
    if symbol in portfolio:
        score += 25
        reasons.append("보유종목")
    if summary.get("earnings") and summary["earnings"] != "저장된 실적 일정 없음":
        score += 15
        reasons.append("실적 일정")
    if summary.get("headline") and summary["headline"] != "저장된 뉴스 없음":
        score += 10
        reasons.append("저장 뉴스")
    if technical.get("trend") == "상승 추세":
        score += 12
        reasons.append("상승 추세")
    elif technical.get("trend") == "박스권/혼조":
        score += 5
    if technical.get("action_bias") == "매수 관점":
        score += 8
        reasons.append("차트 우위")
    elif technical.get("action_bias") == "손절 경계":
        score -= 3
    return score, reasons


def build_compare_payload(symbols: list[str], summaries: list[dict[str, Any]], portfolio: set[str]) -> tuple[list[str], list[str]]:
    if len(symbols) < 2:
        single = symbols[0] if symbols else "비교 대상 없음"
        return [f"우선순위: {single} 단독 검토", f"비교 결론: 비교 대상이 2개 미만이라 단독 체크로 전환"], ["비교할 종목 2개를 지정해서 다시 요청"]

    compared = []
    for item in summaries[:2]:
        technical = build_technical_snapshot(item["symbol"])
        score, reasons = _compare_symbol_score(item, technical, portfolio)
        compared.append({
            "symbol": item["symbol"],
            "summary": item,
            "technical": technical,
            "score": score,
            "reasons": reasons or ["기본 관찰"],
        })

    compared.sort(key=lambda item: -int(item["score"]))
    winner = compared[0]
    loser = compared[1]
    winner_reason = ", ".join(winner["reasons"][:3])
    focus = [
        f"우선순위: {winner['symbol']} 먼저 / 점수 {winner['score']} vs {loser['score']} / 이유: {winner_reason}",
        f"{winner['symbol']} 비교: 뉴스={winner['summary']['headline']} / 실적={winner['summary']['earnings']} / 차트={winner['technical']['trend']} / 액션={winner['technical']['action_bias']}",
        f"{loser['symbol']} 비교: 뉴스={loser['summary']['headline']} / 실적={loser['summary']['earnings']} / 차트={loser['technical']['trend']} / 액션={loser['technical']['action_bias']}",
        f"비교 결론: 지금은 {winner['symbol']} 먼저 보고, {loser['symbol']}는 그 다음 체크",
    ]
    next_actions = [
        f"{winner['symbol']} 먼저: 최신 뉴스/실적/차트 한 줄을 우선 확인",
        f"{loser['symbol']} 다음: 같은 기준으로 2순위 점검",
        "둘 다 강하면 뉴스 freshness와 실적 일정이 더 가까운 쪽 우선",
    ]
    return focus, next_actions


def build_what_changed_payload(symbols: list[str], summaries: list[dict[str, Any]], portfolio: set[str], db_path: Path = DEFAULT_DB_PATH) -> tuple[list[str], list[str]]:
    conn = get_connection(db_path)
    index_rows = fetch_latest_toss_indices(conn, limit=3)
    conn.close()

    market_line = "시장 변화: 저장된 지수 데이터 없음"
    if index_rows:
        top_index = index_rows[0]
        market_line = f"시장 변화: {top_index['index_name']} {top_index['change_pct']:+.2f}% / 현재 {top_index['close']:.2f}"

    symbol_parts = []
    for item in summaries[:2]:
        symbol_parts.append(f"{item['symbol']} 뉴스={item['headline']} / 실적={item['earnings']}")
    symbol_line = f"종목 변화: {' ; '.join(symbol_parts)}" if symbol_parts else "종목 변화: 저장된 종목 데이터 없음"

    top_breaking = _pick_top_breaking_candidate(db_path, portfolio, set(symbols), min_freshness_score=1)
    if top_breaking:
        breaking_symbols = ",".join(top_breaking.get("mapped_symbols") or top_breaking.get("tickers") or []) or "관련종목 없음"
        breaking_line = f"속보 변화: {top_breaking['headline']} / {breaking_symbols} / {_normalize_published_text(top_breaking.get('published_text'))}"
        conclusion = f"변화 결론: 지금은 {breaking_symbols.split(',')[0]} 관련 변화부터 먼저 확인" if breaking_symbols != "관련종목 없음" else "변화 결론: 시장 전체 뉴스 변화부터 먼저 확인"
    else:
        breaking_line = "속보 변화: 저장된 속보 없음"
        conclusion = "변화 결론: 속보보다 종목/지수 저장 데이터 변화부터 확인"

    focus = [market_line, symbol_line, breaking_line, conclusion]
    next_actions = [
        "시장 변화 먼저: 지수 방향과 매크로 headline 확인",
        "종목 변화 다음: 내 watchlist/portfolio 관련 headline 재확인",
        "속보 변화가 종목과 직접 연결되면 그 종목부터 우선 점검",
    ]
    return focus, next_actions


def build_overnight_recap_payload(symbols: list[str], summaries: list[dict[str, Any]], portfolio: set[str], db_path: Path = DEFAULT_DB_PATH) -> tuple[list[str], list[str]]:
    conn = get_connection(db_path)
    index_rows = fetch_latest_toss_indices(conn, limit=3)
    conn.close()

    market_line = "야간 시장: 저장된 야간 지수 데이터 없음"
    if index_rows:
        top_index = index_rows[0]
        market_line = f"야간 시장: {top_index['index_name']} {top_index['change_pct']:+.2f}% / 현재 {top_index['close']:.2f}"

    top_breaking = _pick_top_breaking_candidate(db_path, portfolio, set(symbols), min_freshness_score=1)
    if top_breaking:
        related = ",".join(top_breaking.get("mapped_symbols") or top_breaking.get("tickers") or []) or "관련종목 없음"
        breaking_line = f"야간 속보: {top_breaking['headline']} / {related} / {_normalize_published_text(top_breaking.get('published_text'))}"
    else:
        breaking_line = "야간 속보: 저장된 속보 없음"

    premarket_targets = []
    for item in summaries[:3]:
        if item.get("earnings") and item["earnings"] != "저장된 실적 일정 없음":
            premarket_targets.append(f"{item['symbol']} 실적={item['earnings']}")
        elif item.get("headline") and item["headline"] != "저장된 뉴스 없음":
            premarket_targets.append(f"{item['symbol']} 뉴스={item['headline']}")
    premarket_line = f"장전 체크: {' ; '.join(premarket_targets[:3])}" if premarket_targets else "장전 체크: 저장된 체크포인트 없음"

    conclusion = f"야간 결론: {symbols[0]}부터 장전 확인" if symbols else "야간 결론: watchlist 상단 종목부터 장전 확인"
    focus = [market_line, breaking_line, premarket_line, conclusion]
    next_actions = [
        "야간 시장 먼저: 지수와 매크로 headline 한 번 더 확인",
        "야간 속보 다음: 직접 관련 종목이 있으면 그 종목 우선",
        "장전 체크는 실적 일정과 최신 headline이 있는 종목부터 순서대로 확인",
    ]
    return focus, next_actions


def build_why_symbol_payload(symbols: list[str], summaries: list[dict[str, Any]], portfolio: set[str]) -> tuple[list[str], list[str]]:
    if not summaries:
        return ["핵심 이유: 저장된 종목 요약이 없습니다"], ["종목을 지정해서 다시 요청"]
    item = summaries[0]
    technical = build_technical_snapshot(item["symbol"])
    reasons = [item["bullish"]]
    if item["symbol"] in portfolio:
        reasons.append("보유종목이라 우선 감시 대상")
    if item.get("earnings") and item["earnings"] != "저장된 실적 일정 없음":
        reasons.append("실적 일정이 잡혀 있음")
    if item.get("headline") and item["headline"] != "저장된 뉴스 없음":
        reasons.append("저장된 뉴스가 있음")

    focus = [
        f"핵심 이유: {item['symbol']} / {reasons[0]}",
        f"뉴스 이유: {item['headline']}",
        f"실적 이유: {item['earnings']}",
        f"차트 이유: {technical['trend']} / {technical['action_bias']} / RSI {technical['rsi14']:.2f}",
        f"한줄 결론: 지금 {item['symbol']}는 {' / '.join(reasons[:3])} 때문에 체크할 가치가 있습니다.",
    ]
    next_actions = [
        f"{item['symbol']} 먼저: 뉴스 headline과 실적 일정부터 확인",
        f"{item['symbol']} 다음: 차트 한줄과 손절 기준 같이 확인",
        "판단은 가격보다 이유가 유지되는지 먼저 체크",
    ]
    return focus, next_actions


def build_thesis_break_reason(summaries: list[dict[str, Any]], portfolio: set[str], db_path: Path = DEFAULT_DB_PATH) -> str | None:
    portfolio_items = [item for item in summaries if item["symbol"] in portfolio]
    if not portfolio_items:
        return None
    item = portfolio_items[0]
    top_breaking = _pick_top_breaking_candidate(db_path, portfolio, set(item["symbol"] for item in summaries), min_freshness_score=1)
    breaking_symbols = set(top_breaking.get("mapped_symbols") or top_breaking.get("tickers") or []) if top_breaking else set()
    headline_part = f" / 최근 이슈: {top_breaking['headline']}" if top_breaking and item["symbol"] in breaking_symbols else ""
    return f"thesis break 이유: {item['symbol']} / {item['bearish']}{headline_part}"


def build_compare_view(symbols: list[str], summaries: list[dict[str, Any]], portfolio: set[str], db_path: Path = DEFAULT_DB_PATH, watchlist: set[str] | None = None) -> tuple[list[str], str]:
    watchlist = watchlist or set(symbols)
    top_breaking = _pick_top_breaking_candidate(db_path, portfolio, watchlist, min_freshness_score=1)
    breaking_symbols = set(top_breaking.get("mapped_symbols") or top_breaking.get("tickers") or []) if top_breaking else set()

    ranked: list[tuple[int, dict[str, Any], str]] = []
    for item in summaries:
        score = 0
        reasons: list[str] = []
        if item["symbol"] in portfolio:
            score += 100
            reasons.append("보유")
        if item["symbol"] in breaking_symbols:
            score += 60
            reasons.append("속보")
        if item.get("earnings") and item["earnings"] != "저장된 실적 일정 없음":
            score += 20
            reasons.append("실적")
        if item.get("headline") and item["headline"] != "저장된 뉴스 없음":
            score += 10
            reasons.append("뉴스")
        if "AI" in item.get("bullish", "") or "ai" in item.get("bullish", "").lower():
            score += 5
        ranked.append((score, item, ", ".join(reasons) if reasons else "기본 체력"))

    ranked.sort(key=lambda entry: (-entry[0], symbols.index(entry[1]["symbol"])))
    top_symbol = ranked[0][1]["symbol"]
    other_symbol = ranked[1][1]["symbol"] if len(ranked) > 1 else ranked[0][1]["symbol"]
    focus = [
        f"우선순위: {' > '.join(item['symbol'] for _, item, _ in ranked)}",
    ]
    for score, item, reason in ranked[:2]:
        focus.append(f"{item['symbol']} 비교: 점수 {score} / 이유 {reason} / 강세 {item['bullish']} / 리스크 {item['bearish']} / 실적 {item['earnings']}")
    focus.append(f"비교 결론: 지금은 {top_symbol}를 {other_symbol}보다 먼저 보는 쪽이 낫습니다.")
    summary = f"비교 관점에서 {', '.join(symbols)} 우선순위를 정리했습니다."
    return focus, summary


def build_market_summary(
    db_path: Path = DEFAULT_DB_PATH,
    portfolio: set[str] | None = None,
    watchlist: set[str] | None = None,
    phase: str = "pre_market",
) -> str:
    portfolio = portfolio or set()
    watchlist = watchlist or set()
    conn = get_connection(db_path)
    index_rows = fetch_latest_toss_indices(conn, limit=2)
    toss_rows = fetch_latest_toss_news(conn, limit=3)
    saveticker_rows = fetch_latest_saveticker_items(conn, limit=3)
    conn.close()

    index_parts = [f"{row['index_name']} {row['change_pct']:+.2f}%" for row in index_rows]
    avg_change = sum(float(row["change_pct"]) for row in index_rows) / len(index_rows) if index_rows else 0.0
    if avg_change >= 0.2:
        tone_text = "강세 흐름입니다"
    elif avg_change <= -0.2:
        tone_text = "약세 압력이 우세합니다"
    else:
        tone_text = "혼조 흐름입니다"

    ranked_toss = sorted(
        (map_toss_news_item(dict(row)) for row in toss_rows),
        key=lambda item: (-score_toss_news_item(item, portfolio), item.get("published_text", "")),
    )
    ranked_saveticker = sorted(
        (
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
            for row in saveticker_rows
        ),
        key=lambda item: (-score_saveticker_item(item, portfolio), item.get("published_text", "")),
    )
    headline_ranked_toss = sorted(
        ranked_toss,
        key=lambda item: (-_headline_priority_score(item, portfolio, watchlist), _parse_freshness_minutes(item.get("published_text"))),
    )
    headline_ranked_saveticker = sorted(
        ranked_saveticker,
        key=lambda item: (-_headline_priority_score(item, portfolio, watchlist), _parse_freshness_minutes(item.get("published_text"))),
    )

    theme_label_map = {
        "ai": "AI",
        "ai_infra": "AI 인프라",
        "semis": "반도체",
        "software": "소프트웨어",
        "macro": "매크로",
        "earnings": "실적",
        "security": "보안",
        "power": "전력",
        "defense": "국방",
    }

    headline_candidates: list[dict[str, int | str | None]] = []
    theme_counts: dict[str, int] = {}
    theme_order: list[str] = []
    rumor_detected = False
    if headline_ranked_toss:
        top_toss = headline_ranked_toss[0]
        headline_candidates.append(
            {
                "priority": _headline_priority_score(top_toss, portfolio, watchlist),
                "headline": top_toss["headline"],
                "published_text": top_toss.get("published_text"),
                "reliability": _source_reliability_score(top_toss.get("source_name"), top_toss.get("source")),
            }
        )
        rumor_detected = bool(any(item.get("is_rumor") for item in ranked_toss[:3]))
    if headline_ranked_saveticker:
        top_saveticker = headline_ranked_saveticker[0]
        headline_candidates.append(
            {
                "priority": _headline_priority_score(top_saveticker, portfolio, watchlist),
                "headline": top_saveticker["headline"],
                "published_text": top_saveticker.get("published_text"),
                "reliability": _source_reliability_score(top_saveticker.get("source_name"), top_saveticker.get("source")),
            }
        )
        rumor_detected = bool(any(item.get("is_rumor") for item in ranked_saveticker[:3])) or rumor_detected
    headline_candidates = sorted(headline_candidates, key=lambda item: -int(item["priority"]))
    headline_parts = [str(item["headline"]) for item in headline_candidates]

    for item in ranked_toss[:3] + ranked_saveticker[:3]:
        item_symbols = set(item.get("mapped_symbols") or item.get("tickers") or [])
        if portfolio and item_symbols.intersection(portfolio):
            theme_weight = 5
        elif watchlist and item_symbols.intersection(watchlist):
            theme_weight = 3
        else:
            theme_weight = 1
        for theme in item.get("mapped_themes", []):
            if theme not in theme_counts:
                theme_counts[theme] = 0
                theme_order.append(theme)
            theme_counts[theme] += theme_weight

    sorted_themes = sorted(theme_counts, key=lambda theme: (-theme_counts[theme], theme_order.index(theme)))
    theme_parts = []
    total_theme_weight = sum(theme_counts.values()) or 1
    min_confidence = 0.25
    for theme in sorted_themes[:3]:
        label = theme_label_map.get(theme, theme)
        scope = "general"
        for item in ranked_toss[:3] + ranked_saveticker[:3]:
            item_symbols = set(item.get("mapped_symbols") or item.get("tickers") or [])
            if theme not in item.get("mapped_themes", []):
                continue
            if portfolio and item_symbols.intersection(portfolio):
                scope = "portfolio"
                break
            if watchlist and item_symbols.intersection(watchlist):
                scope = "watchlist"
        confidence = theme_counts[theme] / total_theme_weight
        if confidence < min_confidence:
            continue
        theme_parts.append(f"{label}({scope}, {confidence:.2f})")

    source_count = len(index_rows) + len(headline_parts)
    index_text = ", ".join(index_parts) if index_parts else "지수 데이터 없음"
    theme_text = ", ".join(theme_parts) if theme_parts else "뚜렷한 테마 없음"
    headline_text = " / ".join(headline_parts) if headline_parts else "저장된 헤드라인 없음"
    headline_reliabilities = [int(item["reliability"]) for item in headline_candidates if item.get("reliability") is not None]
    if headline_reliabilities and all(score >= 3 for score in headline_reliabilities):
        source_note = " 주요 통신 기준입니다."
    elif headline_reliabilities and any(score <= 1 for score in headline_reliabilities):
        source_note = " 혼합 소스 기준입니다."
    elif headline_reliabilities:
        source_note = " 주요 뉴스 기준입니다."
    else:
        source_note = ""
    rumor_note = " 검증 필요 루머가 포함돼 있습니다." if rumor_detected else ""
    evidence_note = f" 근거 {source_count}건 기준입니다."
    if phase == "after_close":
        return f"장후 Market Summary: 미국장은 {tone_text} 마감했습니다. 주요 지수는 {index_text} 기준이고, 오늘 테마는 {theme_text}였습니다. 핵심 뉴스는 {headline_text} 입니다.{source_note} 마감 이후 체크가 필요합니다.{rumor_note}{evidence_note}"
    return f"Market Summary: 미국장은 {tone_text} 주요 지수는 {index_text} 기준입니다. 오늘 테마는 {theme_text}이고, 핵심 뉴스는 {headline_text} 입니다.{source_note}{rumor_note}{evidence_note}"


def build_breaking_line(db_path: Path = DEFAULT_DB_PATH, portfolio: set[str] | None = None, watchlist: set[str] | None = None) -> str | None:
    portfolio = portfolio or set()
    watchlist = watchlist or set()
    top = _pick_top_breaking_candidate(db_path, portfolio, watchlist)
    if not top:
        return None
    item_symbols = set(top.get("mapped_symbols") or top.get("tickers") or [])
    scope_text = ""
    if portfolio and item_symbols.intersection(portfolio):
        scope_text = "[portfolio 관련]"
    elif watchlist and item_symbols.intersection(watchlist):
        scope_text = "[watchlist 관련]"
    published_text = top.get("published_text") or "시간 정보 없음"
    freshness_label = _freshness_label(published_text)
    reliability_label = _source_reliability_label(top.get("source_name"), top.get("source"))
    rumor_tag = "[루머 주의]" if top.get("is_rumor") else ""
    tag_prefix = f"{scope_text}[{freshness_label}][신뢰도:{reliability_label}]{rumor_tag}" if scope_text else f"[{freshness_label}][신뢰도:{reliability_label}]{rumor_tag}"
    return f"속보 우선: {tag_prefix} {top['headline']} / {published_text}"


def build_staleness_warning(db_path: Path = DEFAULT_DB_PATH) -> str | None:
    conn = get_connection(db_path)
    toss_rows = fetch_latest_toss_news(conn, limit=1)
    saveticker_rows = fetch_latest_saveticker_items(conn, limit=1)
    conn.close()

    toss_published = toss_rows[0]["published_text"] if toss_rows else None
    saveticker_published = saveticker_rows[0]["published_text"] if saveticker_rows else None
    if not toss_published and not saveticker_published:
        return "최신성 경고: 저장된 속보가 없습니다"

    source_parts = []
    stale_detected = False
    if toss_published:
        source_parts.append(f"Toss {_normalize_published_text(toss_published)}")
        stale_detected = stale_detected or _parse_freshness_minutes(toss_published) >= 180
    if saveticker_published:
        source_parts.append(f"SaveTicker {_normalize_published_text(saveticker_published)}")
        stale_detected = stale_detected or _parse_freshness_minutes(saveticker_published) >= 120

    if stale_detected:
        return f"최신성 경고: {' / '.join(source_parts)}"
    return None


def build_position_alert(db_path: Path = DEFAULT_DB_PATH, portfolio: set[str] | None = None) -> str | None:
    portfolio = portfolio or set()
    if not portfolio:
        return None
    conn = get_connection(db_path)
    toss_rows = fetch_latest_toss_news(conn, limit=5)
    saveticker_rows = fetch_latest_saveticker_items(conn, limit=5)
    conn.close()

    candidates: list[dict] = []
    for row in toss_rows:
        mapped = map_toss_news_item(dict(row))
        if set(mapped.get("mapped_symbols") or []).intersection(portfolio):
            mapped["_priority_score"] = _headline_priority_score(mapped, portfolio, set())
            candidates.append(mapped)
    for row in saveticker_rows:
        mapped = map_saveticker_item(
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
        if set(mapped.get("tickers") or []).intersection(portfolio):
            mapped["_priority_score"] = _headline_priority_score(mapped, portfolio, set())
            candidates.append(mapped)

    if not candidates:
        return None
    candidates.sort(key=lambda item: (-_freshness_score(item.get("published_text")), -item.get("_priority_score", 0)))
    top = candidates[0]
    related = ",".join(sorted(set(top.get("mapped_symbols") or top.get("tickers") or []).intersection(portfolio)))
    published_text = top.get("published_text") or "시간 정보 없음"
    freshness_label = _freshness_label(published_text)
    reliability_label = _source_reliability_label(top.get("source_name"), top.get("source"))
    return f"포지션 경고: [{freshness_label}][신뢰도:{reliability_label}] {related} / {top['headline']} / {published_text}"


def build_brief_from_db(symbols: list[str], db_path: Path = DEFAULT_DB_PATH, portfolio: set[str] | None = None) -> str:
    portfolio = portfolio or set()
    summaries = [build_symbol_summary(symbol, portfolio, db_path=db_path) for symbol in symbols]
    conn = get_connection(db_path)
    upcoming = fetch_upcoming_earnings(conn, limit=5)
    conn.close()

    lines = ["[시장 브리핑]", "[Market Summary]", f"- {build_market_summary(db_path=db_path, portfolio=portfolio, watchlist=set(symbols), phase='pre_market')}"]
    watchlist_movers = build_watchlist_movers(symbols, summaries, portfolio, db_path=db_path, watchlist=set(symbols))
    if watchlist_movers:
        lines.append(f"- {watchlist_movers}")
    portfolio_brief = build_portfolio_brief(symbols, summaries, portfolio)
    if portfolio_brief:
        lines.append(f"- {portfolio_brief}")
    catalyst_board = build_catalyst_board(db_path=db_path, portfolio=portfolio, watchlist=set(symbols))
    if catalyst_board:
        lines.append(f"- {catalyst_board}")
    earnings_alert = build_earnings_nearby_alert(summaries)
    if earnings_alert:
        lines.append(f"- {earnings_alert}")
    position_alert = build_position_alert(db_path=db_path, portfolio=portfolio)
    if position_alert:
        lines.append(f"- {position_alert}")
    thesis_break_reason = build_thesis_break_reason(summaries, portfolio, db_path=db_path)
    if thesis_break_reason:
        lines.append(f"- {thesis_break_reason}")
    staleness_warning = build_staleness_warning(db_path=db_path)
    if staleness_warning:
        lines.append(f"- {staleness_warning}")
    breaking_line = build_breaking_line(db_path=db_path, portfolio=portfolio, watchlist=set(symbols))
    if breaking_line:
        lines.append(f"- {breaking_line}")
    for item in summaries:
        lines.append(f"- {item['symbol']}: {item['bullish']}")
        lines.append(f"  리스크: {item['bearish']}")
        lines.append(f"  뉴스: {item['headline']}")
        lines.append(f"  실적: {item['earnings']}")

    if upcoming:
        lines.append("[가까운 실적 일정]")
        for row in upcoming:
            session_map = {"after_close": "장마감 후", "before_open": "장시작 전", "unknown": "시간 미정"}
            session_label = session_map.get(row["session"], "시간 미정")
            lines.append(f"- {row['symbol']}: {row['earnings_date']} / {session_label}")

    lines.append(build_toss_market_brief(db_path, portfolio_symbols=portfolio))
    lines.append(build_saveticker_brief(db_path, portfolio_symbols=portfolio))
    return "\n".join(lines)


def build_response(request: str, runtime_context: dict | None = None, explicit_mode: str | None = None) -> dict[str, Any]:
    runtime_context = runtime_context or {}
    payload = parse_request_payload(request)
    request_text = str(payload.get("request") or request).strip() or "오늘 시장 체크포인트 정리해줘"
    mode = infer_mode(request_text, explicit_mode=explicit_mode or payload.get("mode"))
    watchlist_path = payload.get("watchlist_path") or runtime_context.get("watchlist_path") or DEFAULT_WATCHLIST_PATH
    symbols = infer_symbols(request_text, provided_symbols=payload.get("symbols"), watchlist_path=watchlist_path)
    watchlist_data = load_watchlist(watchlist_path)
    if payload.get("watchlist") is not None:
        watchlist = set(payload.get("watchlist") or [])
    else:
        watchlist = set(watchlist_data["watchlist"])
    if payload.get("portfolio") is not None:
        portfolio = set(payload.get("portfolio") or [])
    else:
        portfolio = set(runtime_context.get("portfolio") or watchlist_data["portfolio"])
    db_path = Path(payload.get("db_path") or runtime_context.get("db_path") or DEFAULT_DB_PATH)

    if mode == "sector_strength":
        sector_quotes = payload.get("sector_quotes") or runtime_context.get("sector_quotes")
        if not sector_quotes:
            sector_quotes = fetch_sector_strength_quotes()
        report = build_sector_strength_report(
            sector_quotes,
            collected_at=payload.get("collected_at") or runtime_context.get("collected_at"),
        )
        features = list(dict.fromkeys([*runtime_context.get("features", []), "sector_strength", "market_regime"]))
        return {
            "agent": "stock-research-agent",
            "mode": mode,
            "summary": report["summary"],
            "symbols": symbols,
            "focus": report["focus_lines"],
            "next_actions": report["next_actions"],
            "features": features,
            "data": {"sector_strength": report},
        }

    if mode == "yfinance_pack":
        focus: list[str] = []
        packs = []
        for symbol in symbols[:3]:
            pack = fetch_yfinance_market_pack(symbol)
            packs.append(pack)
            focus.extend(build_yfinance_focus_lines(pack, max_lines=8))
        return {
            "agent": "stock-research-agent",
            "mode": mode,
            "summary": f"yfinance optional pack을 정리했습니다: {', '.join(symbols[:3])}",
            "symbols": symbols,
            "focus": focus,
            "next_actions": [
                "현재가는 YF Quote source/timestamp 한계가 있으니 실매매 전 별도 현재가와 대조",
                "옵션 OI/volume은 최근 만기 중심으로 콜/풋 쏠림만 빠르게 확인",
                "뉴스/캘린더/홀더 데이터가 비면 yfinance 호출 제한 또는 Yahoo 쪽 누락으로 간주",
            ],
            "features": runtime_context.get("features", []) + ["yfinance_optional_pack"],
            "data": {"yfinance_packs": packs},
        }

    if mode == "sec_filings":
        focus: list[str] = []
        packs = []
        for symbol in symbols[:3]:
            pack = fetch_sec_filings_pack(symbol)
            packs.append(pack)
            focus.extend(build_sec_focus_lines(pack, max_lines=5))
        return {
            "agent": "stock-research-agent",
            "mode": mode,
            "summary": f"SEC/EDGAR 최근 공시를 정리했습니다: {', '.join(symbols[:3])}",
            "symbols": symbols,
            "focus": focus,
            "next_actions": [
                "8-K는 form8-k 본문보다 ex99-1/exhibit 원문에 실제 숫자와 headline이 있는지 확인",
                "S-3/S-1은 primary issuance인지 selling-stockholder resale인지 구분",
                "10-Q/10-K는 MD&A, liquidity, risk factor 변화만 먼저 확인",
            ],
            "features": runtime_context.get("features", []) + ["sec_filings_pack"],
            "data": {"sec_filings_packs": packs},
        }

    if mode == "topic_hub":
        focus = build_topic_hub_focus_lines(symbols, db_path=db_path)
        return {
            "agent": "stock-research-agent",
            "mode": mode,
            "summary": f"DataHub-lite topic 목록과 캐시 peek를 정리했습니다: {', '.join(symbols[:3])}",
            "symbols": symbols,
            "focus": focus,
            "next_actions": [
                "topic 이름을 기준으로 quote/news/filing/options/social 소스를 분리해서 붙이기",
                "peek age_ms가 큰 항목은 ingest 또는 live fetch를 먼저 실행",
                "알림 모드에서는 필요한 topic만 좁혀 payload를 짧게 유지",
            ],
            "features": runtime_context.get("features", []) + ["topic_hub"],
        }

    if mode == "ingest":
        ingest_result = run_ingest(symbols, db_path=db_path)
        return {
            "agent": "stock-research-agent",
            "mode": mode,
            "summary": f"미국주식 메인 워치리스트 기준으로 {', '.join(symbols)} 데이터 수집을 완료했습니다.",
            "symbols": symbols,
            "focus": [
                f"가격 저장: {ingest_result['stored_prices']}건",
                f"뉴스 저장: {ingest_result['stored_news']}건",
                f"실적 일정 저장: {ingest_result['stored_earnings']}건",
                f"DB: {ingest_result['db_path']}",
            ],
            "next_actions": [
                "미국장 장전 브리핑으로 저장 데이터 확인",
                "포트폴리오 보유 미국주 종목 우선순위 반영",
                "미국 실적 일정/소셜 시그널 저장 계층 추가",
            ],
            "features": runtime_context.get("features", []),
        }

    if mode == "saveticker_sync":
        saveticker_result = run_saveticker_ingest(db_path)
        return {
            "agent": "stock-research-agent",
            "mode": mode,
            "summary": "SaveTicker 미국주 속보 수집을 완료했습니다.",
            "symbols": symbols,
            "focus": [
                f"SaveTicker 뉴스 저장: {saveticker_result['saveticker_items']}건",
                f"DB: {saveticker_result['db_path']}",
            ],
            "next_actions": [
                "brief 모드에서 SaveTicker 속보 섹션 확인",
                "포트폴리오 종목과 직접 매핑되는 속보 우선 검토",
                "rumor 태그가 붙은 뉴스는 추가 검증 후 판단",
            ],
            "features": runtime_context.get("features", []),
        }

    if mode == "saveticker_breaking":
        important_text = build_saveticker_important_breaking(
            db_path,
            portfolio_symbols=portfolio,
            watchlist_symbols=watchlist.union(set(symbols)),
            limit=int(payload.get("limit") or runtime_context.get("limit") or 5),
        )
        focus = [line[2:] if line.startswith("- ") else line for line in important_text.splitlines()[1:]]
        return {
            "agent": "stock-research-agent",
            "mode": mode,
            "summary": "SaveTicker 중요 속보만 선별했습니다.",
            "symbols": symbols,
            "focus": focus,
            "next_actions": [
                "루머/카더라 라벨은 검증 전 포지션 확대 금지",
                "보유/관심종목 관련 속보는 가격 반응과 공식 공시를 바로 대조",
                "중요 속보가 비어 있으면 먼저 saveticker_sync로 최신 뉴스 수집",
            ],
            "features": runtime_context.get("features", []) + ["saveticker_important_breaking"],
        }

    if mode == "toss_sync":
        toss_result = run_toss_ingest(db_path)
        return {
            "agent": "stock-research-agent",
            "mode": mode,
            "summary": "토스증권 공개 미국지수/뉴스 수집을 완료했습니다.",
            "symbols": symbols,
            "focus": [
                f"토스 미국지수 저장: {toss_result['toss_indices']}건",
                f"토스 뉴스 저장: {toss_result['toss_news']}건",
                f"DB: {toss_result['db_path']}",
            ],
            "next_actions": [
                "brief 모드에서 토스 보조지표 섹션 확인",
                "토스 뉴스와 Yahoo 뉴스 시각 차이 비교",
                "미국지수/뉴스를 장전 브리핑 우선순위에 반영",
            ],
            "features": runtime_context.get("features", []),
        }

    if mode == "earnings_preview":
        previews = [build_earnings_preview(symbol, db_path=db_path) for symbol in symbols]
        focus = []
        for preview in previews:
            focus.append(f"{preview['symbol']} Setup: {preview['earnings_date']} / {preview['session']} / {preview['recent_price'] or '가격 데이터 없음'}")
            focus.append(f"{preview['symbol']} Bull case: {preview['bull_case'][0]}")
            focus.append(f"{preview['symbol']} Bear case: {preview['bear_case'][0]}")
            focus.append(f"{preview['symbol']} Key metrics: {', '.join(preview['key_metrics'][:3])}")
            focus.append(f"{preview['symbol']} Questions: {preview['questions_for_call'][0]}")
        return {
            "agent": "stock-research-agent",
            "mode": mode,
            "summary": f"미국주 실적 프리뷰 팩을 준비했습니다: {', '.join(symbols)}",
            "symbols": symbols,
            "focus": focus,
            "next_actions": [
                "실적 전 1~3일 동안 최근 뉴스와 가이던스 변화를 다시 확인",
                "bull / bear 해석이 갈리는 KPI를 따로 체크",
                "콜에서 답을 꼭 들어야 하는 질문 5개를 미리 적어둘 것",
            ],
            "features": runtime_context.get("features", []),
        }

    if mode == "earnings":
        conn = get_connection(db_path)
        upcoming = [row for row in fetch_upcoming_earnings(conn, limit=10) if row["symbol"] in symbols]
        if not upcoming:
            upcoming = fetch_upcoming_earnings(conn, limit=5)
        conn.close()
        focus = []
        for row in upcoming:
            session_map = {"after_close": "장마감 후", "before_open": "장시작 전", "unknown": "시간 미정"}
            session_label = session_map.get(row["session"], "시간 미정")
            focus.append(f"{row['symbol']} 실적 예정: {row['earnings_date']} / {session_label} / {row['note']}")
        if not focus:
            focus = ["저장된 실적 일정이 없어서 ingest를 먼저 돌려야 함"]
        return {
            "agent": "stock-research-agent",
            "mode": mode,
            "summary": f"미국주 메인 워치리스트 기준으로 실적 일정을 정리했습니다.",
            "symbols": symbols,
            "focus": focus,
            "next_actions": [
                "실적 2일 전 장전 브리핑에 우선 표시",
                "보유 종목이면 thesis_note와 가이던스 변수 같이 점검",
                "earnings 뒤 가격반응보다 가이던스/콜 내용을 먼저 확인",
            ],
            "features": runtime_context.get("features", []),
        }

    if mode == "technical_snapshot":
        snapshots = [build_technical_snapshot(symbol) for symbol in symbols]
        focus = []
        for snap in snapshots:
            focus.append(f"{snap['symbol']} 추세: {snap['trend']} / 현재가 {snap['latest']:.2f} / 20일선 {snap['sma20']:.2f} / 50일선 {snap['sma50']:.2f} / 200일선 {snap['sma200']:.2f}")
            focus.append(f"{snap['symbol']} RSI: {snap['rsi14']:.2f} / 모멘텀: {snap['momentum']}")
            focus.append(f"{snap['symbol']} MACD: {snap['macd']:+.2f} / Signal: {snap['signal']:+.2f} / Histogram: {snap['hist']:+.2f}")
            focus.append(f"{snap['symbol']} 지지/저항: 지지 {snap['support']:.2f} / 저항 {snap['resistance']:.2f}")
            focus.append(f"{snap['symbol']} 손절 기준 가격: {snap['stop_price']:.2f}")
            focus.append(f"{snap['symbol']} 손절 거리: {snap['stop_distance_pct']:+.2f}%")
            focus.append(f"{snap['symbol']} 해석: {snap['interpretation']}")
            focus.append(f"{snap['symbol']} action bias: {snap['action_bias']}")
            if snap['event_tags']:
                focus.append(f"{snap['symbol']} 이벤트 태그: {', '.join(snap['event_tags'])}")
        return {
            "agent": "stock-research-agent",
            "mode": mode,
            "summary": f"TradingView 느낌의 technical snapshot을 준비했습니다: {', '.join(symbols)}",
            "symbols": symbols,
            "focus": focus,
            "next_actions": [
                "TradingView 느낌으로 보면 20일선/50일선 위아래 위치를 먼저 확인",
                "RSI가 70 이상이면 추격보다 눌림 확인, 30 이하면 반등 강도 체크",
                "MACD histogram 방향이 다음 캔들에서 유지되는지 확인",
            ],
            "features": runtime_context.get("features", []),
        }

    if mode == "social_search":
        summary, focus, next_actions = build_social_search_payload(request_text, symbols)
        return {
            "agent": "stock-research-agent",
            "mode": mode,
            "summary": summary,
            "symbols": symbols,
            "focus": focus,
            "next_actions": next_actions,
            "features": runtime_context.get("features", []),
        }

    summaries = [build_symbol_summary(symbol, portfolio, db_path=db_path) for symbol in symbols]
    focus: list[str] = []
    next_actions: list[str] = []

    if mode == "compare":
        summary = f"비교 관점에서 {', '.join(symbols[:2])} 우선순위를 정리했습니다."
        focus, next_actions = build_compare_payload(symbols, summaries, portfolio)
    elif mode == "what_changed":
        summary = f"최근 저장 기준으로 {', '.join(symbols[:2])} 변화 포인트를 정리했습니다."
        focus, next_actions = build_what_changed_payload(symbols, summaries, portfolio, db_path=db_path)
    elif mode == "overnight_recap":
        summary = f"장후~장전 기준으로 {', '.join(symbols[:2])} 야간 변화 포인트를 정리했습니다."
        focus, next_actions = build_overnight_recap_payload(symbols, summaries, portfolio, db_path=db_path)
    elif mode == "why_symbol":
        summary = f"왜 지금 {symbols[0]}를 봐야 하는지 핵심 이유를 정리했습니다." if symbols else "왜 이 종목을 봐야 하는지 핵심 이유를 정리했습니다."
        focus, next_actions = build_why_symbol_payload(symbols, summaries, portfolio)
    elif mode == "brief":
        brief_phase = _infer_brief_phase(request_text)
        summary_prefix = "장후 브리핑" if brief_phase == "after_close" else "장전 브리핑"
        summary = f"{summary_prefix} 관점에서 {', '.join(symbols)} 체크포인트를 정리했습니다."
        market_summary = build_market_summary(db_path=db_path, portfolio=portfolio, watchlist=watchlist, phase=brief_phase)
        watchlist_movers = build_watchlist_movers(symbols, summaries, portfolio, db_path=db_path, watchlist=watchlist)
        portfolio_brief = build_portfolio_brief(symbols, summaries, portfolio)
        catalyst_board = build_catalyst_board(db_path=db_path, portfolio=portfolio, watchlist=watchlist)
        earnings_alert = build_earnings_nearby_alert(summaries)
        position_alert = build_position_alert(db_path=db_path, portfolio=portfolio)
        thesis_break_reason = build_thesis_break_reason(summaries, portfolio, db_path=db_path)
        staleness_warning = build_staleness_warning(db_path=db_path)
        breaking_line = build_breaking_line(db_path=db_path, portfolio=portfolio, watchlist=watchlist)
        social_signal_line = build_social_signal_line(symbols) if should_include_social_signal(request_text, mode) else None
        yfinance_lines = []
        if any(keyword in request_text.lower() for keyword in ["yfinance", "yf", "야후", "옵션"]):
            for symbol in symbols[:2]:
                yfinance_lines.extend(build_yfinance_focus_lines(fetch_yfinance_market_pack(symbol), max_lines=4))
        technical_snapshots = [build_technical_snapshot(symbol) for symbol in symbols[:2]]
        technical_lines = [snap["brief_line"] for snap in technical_snapshots]
        toss_brief_lines = [line[2:] if line.startswith('- ') else line for line in build_toss_market_brief(db_path, portfolio_symbols=portfolio).splitlines()[1:]]
        saveticker_brief_lines = [line[2:] if line.startswith('- ') else line for line in build_saveticker_brief(db_path, portfolio_symbols=portfolio).splitlines()[1:]]
        if "[토스증권 주요 뉴스]" in toss_brief_lines:
            split_idx = toss_brief_lines.index("[토스증권 주요 뉴스]")
            toss_index_lines = toss_brief_lines[:split_idx]
            toss_news_lines = toss_brief_lines[split_idx + 1 : split_idx + 4]
        else:
            toss_index_lines = toss_brief_lines[:3]
            toss_news_lines = []
        saveticker_news_lines = saveticker_brief_lines[1:4] if len(saveticker_brief_lines) > 1 else []
        focus = [
            market_summary,
        ] + ([watchlist_movers] if watchlist_movers else []) + ([portfolio_brief] if portfolio_brief else []) + ([catalyst_board] if catalyst_board else []) + ([earnings_alert] if earnings_alert else []) + ([position_alert] if position_alert else []) + ([thesis_break_reason] if thesis_break_reason else []) + ([staleness_warning] if staleness_warning else []) + ([social_signal_line] if social_signal_line else []) + yfinance_lines + ([breaking_line] if breaking_line else []) + technical_lines + [
            f"{item['symbol']} 강세: {item['bullish']}" for item in summaries[:2]
        ] + [
            f"{item['symbol']} 뉴스: {item['headline']}" for item in summaries[:2]
        ] + [
            f"{item['symbol']} 실적: {item['earnings']}" for item in summaries[:2]
        ] + toss_index_lines + toss_news_lines + saveticker_news_lines
        next_actions = [
            "장전 체크: 개장 전 실적 일정과 주요 뉴스만 다시 확인",
            "보유 미국주 종목이면 thesis와 충돌하는 이벤트가 있는지 체크",
            "급등락 시 가격보다 이유와 매크로 변수부터 기록",
        ] if brief_phase == "pre_market" else [
            "장후 체크: 애프터마켓 가격반응과 가이던스 문구를 먼저 확인",
            "마감 이후 나온 실적/뉴스가 내일 시가에 미칠 영향 정리",
            "보유 종목은 마감 후 thesis 변화 여부를 짧게 메모",
        ]
    elif mode == "portfolio_guard":
        summary = f"포트폴리오 가드 관점에서 {', '.join(symbols)} 재점검 포인트를 정리했습니다."
        focus = [f"{item['symbol']} 위험도={item['risk_level']} / {item['risk']} / {item['bearish']} / 뉴스={item['headline']} / 실적={item['earnings']}" for item in summaries]
        next_actions = [
            "보유 미국주 thesis_note와 최근 악재 뉴스 충돌 여부 확인",
            "실적 발표 2일 전 알림 우선순위 높이기",
            "소셜 시그널은 참고만 하고 뉴스/실적/가이던스로 교차검증",
        ]
    elif mode == "compare":
        focus, summary = build_compare_view(symbols, summaries, portfolio, db_path=db_path, watchlist=watchlist)
        next_actions = [
            "1등 종목부터 뉴스/실적/차트 순서로 다시 확인",
            "두 종목 모두 좋으면 먼저 볼 종목과 나중에 볼 종목만 분리",
            "비교 결과는 최신 속보가 들어오면 바로 바뀔 수 있으니 재실행",
        ]
    else:
        summary = f"종목 리뷰 관점에서 {', '.join(symbols)} 핵심 포인트를 정리했습니다."
        focus = [f"{item['symbol']} 촉매: {item['catalyst']} / 리스크: {item['bearish']} / 뉴스: {item['headline']} / 실적: {item['earnings']}" for item in summaries]
        next_actions = [
            "강세 논리와 약세 논리를 1:1로 적어보기",
            "미국장 기준 가장 가까운 이벤트 일정 확인",
            "실제 매매보다 판단 근거 업데이트를 우선",
        ]

    return {
        "agent": "stock-research-agent",
        "mode": mode,
        "summary": summary,
        "symbols": symbols,
        "focus": focus,
        "next_actions": next_actions,
        "features": runtime_context.get("features", []),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="stock research agent")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--context-json", default="{}")
    parser.add_argument("--mode", choices=["ingest", "saveticker_sync", "saveticker_breaking", "toss_sync", "earnings_preview", "earnings", "sec_filings", "topic_hub", "sector_strength", "compare", "what_changed", "overnight_recap", "why_symbol", "social_search", "technical_snapshot", "yfinance_pack", "brief", "portfolio_guard", "symbol_review"], default=None)
    parser.add_argument("request", nargs="*")
    args = parser.parse_args()

    request = " ".join(args.request).strip() or "오늘 시장 체크포인트 정리해줘"
    runtime_context = json.loads(args.context_json)
    payload = build_response(request, runtime_context=runtime_context, explicit_mode=args.mode)

    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(payload["summary"])
        print("핵심 포인트:")
        for item in payload["focus"]:
            print(f"- {item}")
        print("다음 액션:")
        for item in payload["next_actions"]:
            print(f"- {item}")


if __name__ == "__main__":
    main()
