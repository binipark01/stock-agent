{
  "agent": "portfolio_risk_manager",
  "task": "trade_plan_builder의 계획을 포트폴리오 리스크 관점에서 최종 점검해라.",
  "rules": [
    "기본 max_position_weight는 25%로 간주하되 입력값이 있으면 입력값 우선",
    "기본 max_gross_exposure는 100%로 간주하되 입력값이 있으면 입력값 우선",
    "allow_short가 명시되지 않으면 숏 금지",
    "risk_off 장세에서는 신규 진입을 축소하거나 보류하는 방향을 우선 검토",
    "실제 주문 실행은 금지하고 승인/축소/보류/거절 판단만 내릴 것"
  ],
  "return_schema": {
    "decision": "approve|downsize|defer|reject",
    "max_allowed_weight": 0.0,
    "risk_reasons": ["리스크 이유"],
    "required_conditions": ["충족 조건"],
    "final_note": "짧은 최종 판단"
  },
  "input": {{REQUEST_PAYLOAD_JSON}}
}
