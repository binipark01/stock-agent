# US multi-agent prompts

미장 에이전트별 LLM 프롬프트를 관리한다.

## 구조

```text
prompts/us_agents/<agent_name>/system.md
prompts/us_agents/<agent_name>/user.md
```

원칙:
- `system.md`: 해당 에이전트의 고정 역할, 금지사항, 출력 계약.
- `user.md`: 실행 시점 데이터와 함께 들어가는 일반 프롬프트 템플릿.
- 템플릿 변수는 `{{NAME}}` 형식으로 둔다.
- 각 에이전트는 입력에 없는 데이터/지표/뉴스를 지어내면 안 된다.
- 실제 주문 실행은 모든 에이전트에서 금지한다. 주문은 별도 권한/브로커 게이트가 있어야 한다.

## 공통 변수

- `{{REQUEST_PAYLOAD_JSON}}`: 실행 시점 입력 JSON.
- `{{MIN_LEADERS}}`, `{{MAX_LEADERS}}`: `theme_leader_reranker` 전용 대장주 개수 범위.

## 현재 에이전트

| Agent | 역할 |
|---|---|
| `theme_leader_reranker` | 미장 테마별 대장주 후보를 3~5개 재선정 |
| `market_regime_analyst` | 장세/risk-on/risk-off/제약 조건 판정 |
| `technical_signal_analyst` | 가격/추세/모멘텀/거래량 신호 요약 |
| `news_catalyst_analyst` | 뉴스 후보 중 실제 촉매/리스크만 선별 |
| `bull_researcher` | 상승 논리와 무효화 조건 구성 |
| `bear_researcher` | 하락/주의 논리와 리스크 트리거 구성 |
| `research_manager` | bull/bear/분석 결과를 5단계 rating으로 종합 |
| `trade_plan_builder` | rating을 진입/무효화/비중 가이드로 변환 |
| `portfolio_risk_manager` | 포트폴리오 한도와 장세 리스크로 최종 축소/보류/거절 판단 |
| `quant_signal_guard` | 기계적 시그널, 데이터 품질, blackout, risk cap 충돌 검사 |

## 가져온 설계 아이디어

- `D:\Agents\TradingAgents`: analyst → bull/bear debate → research manager → trader → risk/portfolio manager 흐름.
- `D:\Agents\us-quant-trader`: 데이터 품질 검사, signal scan, target weight, risk policy, blackout guard 개념.

코드는 직접 복사하지 않고, 우리 미장 알림/Discord 에이전트에 맞는 prompt 계약으로 재작성했다.
