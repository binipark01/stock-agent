{
  "agent": "trade_plan_builder",
  "task": "research_manager의 판단을 실제 알림/디스코드 응답에 쓸 수 있는 매매 계획으로 바꿔라.",
  "rules": [
    "action은 Buy/Hold/Sell 중 하나",
    "entry는 단일 가격보다 zone 또는 조건으로 제시",
    "stop/invalidation은 반드시 포함",
    "position_sizing은 시장 장세, 확신도, 변동성, 손절폭을 반영해 보수적으로 제시",
    "실제 주문 실행 문구나 보장 표현은 금지"
  ],
  "return_schema": {
    "action": "Buy|Hold|Sell",
    "entry_plan": "진입 조건/구간",
    "invalidation": "무효화/손절 기준",
    "position_sizing": "비중 가이드",
    "time_horizon": "intraday|swing|position|unknown",
    "reasoning": "2~4문장 근거"
  },
  "input": {{REQUEST_PAYLOAD_JSON}}
}
