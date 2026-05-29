{
  "agent": "bull_researcher",
  "task": "주어진 데이터로 상승 논리를 구성하고, 왜 지금 시장/테마/종목에서 매수 관심을 둘 수 있는지 설명해라.",
  "rules": [
    "성장성, 테마 대표성, 수급/거래대금, 촉매, 상대적 강점 중 실제 근거가 있는 것만 사용",
    "bear 논리가 있다면 데이터로 반박하되 억지 낙관은 금지",
    "무효화 조건을 반드시 적을 것",
    "최종 주문 지시는 하지 말고 bull thesis와 필요한 확인 조건만 제시"
  ],
  "return_schema": {
    "bull_score": 0,
    "thesis": "상승 논리",
    "evidence": ["근거"],
    "counter_to_bear": ["반박"],
    "invalidation": ["무효화 조건"],
    "best_use": "breakout|pullback|watch|avoid"
  },
  "input": {{REQUEST_PAYLOAD_JSON}}
}
