from __future__ import annotations

from pathlib import Path

try:
    from .repository import get_connection, fetch_latest_news, fetch_latest_snapshot, fetch_latest_earnings
except ImportError:
    from repository import get_connection, fetch_latest_news, fetch_latest_snapshot, fetch_latest_earnings


PREVIEW_TEMPLATES = {
    "NVDA": {
        "what_matters": [
            "data center revenue 성장률이 기대치를 상회하는지",
            "hyperscaler capex 수요가 유지되는지",
            "Blackwell/H200 등 AI 제품 램프 타이밍이 흔들리지 않는지",
        ],
        "bull_case": [
            "데이터센터 매출 성장률이 예상보다 강하게 유지된다",
            "가이던스가 상향되거나 AI 수요 표현이 강화된다",
            "gross margin 방어가 확인된다",
        ],
        "bear_case": [
            "고객 capex 둔화 시그널이 나온다",
            "margin 압박이나 공급 병목 이슈가 커진다",
            "중국/규제 영향이 확대된다",
        ],
        "key_metrics": [
            "data center revenue growth",
            "gross margin",
            "guidance",
            "inventory / supply constraints",
            "hyperscaler demand commentary",
        ],
        "questions_for_call": [
            "Hyperscaler demand가 다음 분기에도 유지되나?",
            "Blackwell ramp timing이 계획대로 진행 중인가?",
            "pricing power와 margin 압박 중 어느 쪽이 더 큰가?",
            "중국/수출 규제가 수요에 미치는 영향은 무엇인가?",
            "AI 고객 집중도가 높아지는 것이 리스크인가?",
        ],
    },
    "MSFT": {
        "what_matters": [
            "Azure 성장률과 AI monetization의 연결 강도",
            "Copilot 수익화가 실제 숫자로 보이는지",
            "AI 관련 capex 부담이 margin에 미치는 영향",
        ],
        "bull_case": [
            "Azure 성장률이 시장 기대를 상회한다",
            "Copilot/AI monetization 코멘트가 구체적이다",
            "capex 확대에도 마진 방어가 확인된다",
        ],
        "bear_case": [
            "AI capex 부담만 커지고 수익화 코멘트는 약하다",
            "클라우드 성장 둔화 신호가 나온다",
            "가이던스가 보수적으로 제시된다",
        ],
        "key_metrics": [
            "Azure growth",
            "operating margin",
            "capex / infrastructure spend",
            "AI monetization commentary",
            "guidance",
        ],
        "questions_for_call": [
            "Azure 성장의 핵심 드라이버가 AI인가 기존 워크로드인가?",
            "Copilot이 실제 매출/ARPU에 얼마나 기여했나?",
            "AI infra capex 피크아웃 시점은 언제로 보나?",
            "클라우드 마진 방어가 가능한가?",
            "다음 분기 가이던스에서 AI 효과가 더 커지나?",
        ],
    },
    "AMZN": {
        "what_matters": [
            "AWS 성장 회복과 생성형 AI 수요 연결",
            "리테일 마진과 광고 사업 방어력",
            "가이던스의 보수성 여부",
        ],
        "bull_case": [
            "AWS 성장률이 재가속한다",
            "광고와 리테일 마진이 예상보다 견조하다",
            "AI 관련 수요 코멘트가 강화된다",
        ],
        "bear_case": [
            "AWS 성장률이 기대 이하로 둔화된다",
            "리테일 비용 압박이 확대된다",
            "가이던스가 시장 기대보다 약하다",
        ],
        "key_metrics": [
            "AWS revenue growth",
            "retail operating margin",
            "advertising growth",
            "FCF",
            "guidance",
        ],
        "questions_for_call": [
            "AWS 수요 회복이 broad-based인가 특정 고객군 중심인가?",
            "AI 서비스가 AWS 성장에 얼마나 기여했나?",
            "리테일 fulfillment 효율 개선이 유지되나?",
            "광고 성장 둔화 가능성은 없나?",
            "다음 분기 가이던스에서 비용 압박 요인은 무엇인가?",
        ],
    },
}


def _default_template(symbol: str) -> dict:
    return {
        "what_matters": [
            f"{symbol} 이번 분기 핵심 성장/수익성 포인트 확인",
            "가이던스가 강화되는지 약화되는지 확인",
            "thesis를 바꾸는 새 리스크가 나오는지 확인",
        ],
        "bull_case": [
            "실적과 가이던스가 시장 기대를 상회한다",
            "핵심 사업부 성장률이 유지된다",
            "마진 방어가 확인된다",
        ],
        "bear_case": [
            "가이던스가 약하거나 수요 둔화 표현이 나온다",
            "수익성 압박이 커진다",
            "핵심 사업부 성장률이 둔화된다",
        ],
        "key_metrics": [
            "revenue growth",
            "operating margin",
            "FCF",
            "guidance",
            "management commentary",
        ],
        "questions_for_call": [
            "이번 분기에서 가장 중요한 성장 동력은 무엇인가?",
            "가이던스의 핵심 가정은 무엇인가?",
            "마진 압박 요인은 무엇인가?",
            "다음 분기 리스크는 무엇인가?",
            "thesis를 강화하거나 약화시키는 포인트는 무엇인가?",
        ],
    }


def build_earnings_context(symbol: str, db_path: str | Path):
    conn = get_connection(db_path)
    snapshot = fetch_latest_snapshot(conn, symbol)
    news_rows = fetch_latest_news(conn, symbol, limit=3)
    earnings_row = fetch_latest_earnings(conn, symbol)
    conn.close()
    return {
        "snapshot": snapshot,
        "news_rows": news_rows,
        "earnings_row": earnings_row,
    }


def build_earnings_preview(symbol: str, db_path: str | Path):
    context = build_earnings_context(symbol, db_path)
    template = PREVIEW_TEMPLATES.get(symbol, _default_template(symbol))
    snapshot = context["snapshot"]
    news_rows = context["news_rows"]
    earnings_row = context["earnings_row"]

    if earnings_row:
        session_map = {"after_close": "장마감 후", "before_open": "장시작 전", "unknown": "시간 미정"}
        earnings_session = session_map.get(earnings_row["session"], "시간 미정")
        earnings_date = earnings_row["earnings_date"]
    else:
        earnings_session = "시간 미정"
        earnings_date = "미정"

    recent_price = None
    if snapshot:
        recent_price = f"현재가 {snapshot['price']:.2f}, 변동률 {snapshot['pct_change']:+.2f}%"

    recent_news = [row["headline"] for row in news_rows] if news_rows else ["최근 저장된 뉴스 없음"]

    return {
        "symbol": symbol,
        "earnings_date": earnings_date,
        "session": earnings_session,
        "recent_price": recent_price,
        "recent_news": recent_news,
        "what_matters": template["what_matters"],
        "bull_case": template["bull_case"],
        "bear_case": template["bear_case"],
        "key_metrics": template["key_metrics"],
        "questions_for_call": template["questions_for_call"],
    }
