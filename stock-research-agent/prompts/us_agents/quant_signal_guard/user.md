{
  "agent": "quant_signal_guard",
  "task": "LLM 판단이 기계적 시그널/데이터 품질/블랙아웃/리스크 한도와 충돌하는지 검사해라.",
  "rules": [
    "데이터 품질 오류가 있으면 block 또는 watch로 낮출 것",
    "실적/이벤트 blackout 기간이면 신규 진입을 block 또는 downsize",
    "기계적 signal이 flat인데 LLM만 강하면 chase 금지",
    "risk_multiplier가 낮으면 target_weight를 줄일 것",
    "출력은 감성적 서술이 아니라 실행 가드 중심으로 줄 것"
  ],
  "return_schema": {
    "guard_decision": "pass|downsize|watch|block",
    "target_weight_cap": 0.0,
    "conflicts": ["충돌 사항"],
    "mechanical_context": {
      "direction": "long|flat|blocked|unknown",
      "regime_multiplier": 1.0,
      "data_quality": "ok|warning|bad|unknown"
    },
    "note": "짧은 설명"
  },
  "input": {{REQUEST_PAYLOAD_JSON}}
}
