"""US core brief/review helper functions.

Extracted from main.py while keeping main.py as the public orchestrator and
legacy import surface.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from ..repository import (
        fetch_latest_earnings,
        fetch_latest_news,
        fetch_latest_saveticker_items,
        fetch_latest_snapshot,
        fetch_latest_toss_indices,
        fetch_latest_toss_news,
        fetch_upcoming_earnings,
        get_connection,
    )
    from ..tossinvest_data import build_toss_market_brief, map_toss_news_item, score_toss_news_item
    from ..saveticker_data import build_saveticker_brief, map_saveticker_item, score_saveticker_item
    from .technical.snapshot import build_technical_snapshot
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
    )
    from tossinvest_data import build_toss_market_brief, map_toss_news_item, score_toss_news_item
    from saveticker_data import build_saveticker_brief, map_saveticker_item, score_saveticker_item
    from us.technical.snapshot import build_technical_snapshot


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = REPO_ROOT / "data" / "stock_agent.db"


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
