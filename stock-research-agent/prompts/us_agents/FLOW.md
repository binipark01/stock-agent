# US stock multi-agent flow draft

미장 Discord/cron 에이전트의 목표 파이프라인 초안이다.

```text
market_regime_analyst
  ↓
technical_signal_analyst + news_catalyst_analyst
  ↓
bull_researcher ↔ bear_researcher
  ↓
research_manager
  ↓
trade_plan_builder
  ↓
quant_signal_guard
  ↓
portfolio_risk_manager
  ↓
Discord/Telegram 알림 또는 사용자 질의 응답
```

## 핵심 규칙

1. `market_regime_analyst`가 risk_off면 뒤 에이전트는 추격/비중 확대를 강하게 제한한다.
2. `technical_signal_analyst`는 신호 품질만 판단하고 주문을 말하지 않는다.
3. `news_catalyst_analyst`는 의미 없는 기사 요약을 버리고 촉매/리스크만 남긴다.
4. `bull_researcher`와 `bear_researcher`는 같은 입력을 반대로 검토한다.
5. `research_manager`는 5단계 rating을 낸다: Buy / Overweight / Hold / Underweight / Sell.
6. `trade_plan_builder`는 Buy/Hold/Sell, entry zone, invalidation, sizing guide만 낸다.
7. `quant_signal_guard`가 데이터 품질/blackout/기계적 signal 충돌을 막는다.
8. `portfolio_risk_manager`가 최종 approve/downsize/defer/reject를 낸다.
9. 어떤 단계도 실제 주문을 실행하지 않는다.

## 지금 바로 재사용 가능한 부분

- 현재 cron의 `theme_leader_reranker`는 그대로 유지.
- Discord 명령형 agent를 만들 때 `/market`, `/theme`, `/stock`, `/plan` 명령은 위 agent prompt를 조합하면 된다.
- paper/rebalance 기능은 `us-quant-trader` 쪽처럼 별도 risk gate를 둔 뒤에만 연결한다.
