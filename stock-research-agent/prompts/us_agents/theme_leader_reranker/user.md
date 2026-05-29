{
  "agent": "theme_leader_reranker",
  "task": "각 테마에서 최종 대장주를 {{MIN_LEADERS}}~{{MAX_LEADERS}}개 고르거나 재정렬해라.",
  "rules": [
    "후보에 없는 symbol은 절대 만들지 말 것",
    "테마 대표성(theme_anchor), 오늘 등락률, 거래대금, 거래대금 전일대비 증가, 거래량 증가, theme_news/issue를 함께 판단",
    "RSI가 높다는 이유만으로 감점하지 말 것",
    "SPY 대비 상대강도는 판단 기준에서 제외",
    "잡주성 급등보다 테마를 대표하면서 돈이 붙은 종목을 우선",
    "후보가 충분하면 {{MIN_LEADERS}}개 이상, 확실한 대장주가 더 있으면 {{MAX_LEADERS}}개까지 허용",
    "확신이 낮은 종목으로 억지로 {{MAX_LEADERS}}개를 채우지 말 것"
  ],
  "return_schema": {
    "themes": [
      {
        "key": "theme key",
        "leaders": ["AAA", "BBB", "CCC", "DDD"],
        "reason": "짧은 한국어 이유"
      }
    ]
  },
  "input": {{REQUEST_PAYLOAD_JSON}}
}
