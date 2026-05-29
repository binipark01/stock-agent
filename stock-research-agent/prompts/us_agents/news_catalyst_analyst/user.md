{
  "agent": "news_catalyst_analyst",
  "task": "뉴스/이슈 후보 중 실제 매매 판단에 의미 있는 촉매와 리스크만 골라라.",
  "rules": [
    "단순 반복 기사, 가격만 설명하는 기사, 의미 없는 일반론은 제외",
    "실적, 가이던스, 수주, 규제, 제품, 자금조달, M&A, 애널리스트 변경, SEC filing을 우선",
    "테마 전체에 영향을 주는 뉴스와 단일 종목 뉴스는 구분",
    "좋은 뉴스라도 이미 가격에 과도하게 반영됐으면 priced_in 가능성을 표시",
    "출처가 불확실하거나 오래된 뉴스면 confidence를 낮출 것"
  ],
  "return_schema": {
    "theme_catalysts": [
      {
        "theme": "테마명",
        "catalyst": "핵심 촉매",
        "affected_symbols": ["AAA"],
        "direction": "positive|negative|mixed|unclear",
        "confidence": "low|medium|high"
      }
    ],
    "symbol_events": [
      {
        "symbol": "AAA",
        "event": "핵심 이벤트",
        "actionability": "high|medium|low|ignore",
        "risk": "주의점"
      }
    ]
  },
  "input": {{REQUEST_PAYLOAD_JSON}}
}
