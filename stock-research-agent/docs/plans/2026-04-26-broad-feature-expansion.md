# Stock Research Agent Broad Feature Expansion Plan

> For Hermes: 기능 디테일 polish보다, 현재 확보한 소스들을 최대한 넓게 활용하는 방향으로 빠르게 확장한다.

Goal: Toss / SaveTicker / DB / watchlist / portfolio 기반 실전 기능을 최대한 많이 붙여서 브리핑, 감시, 추적, 후속질문 대응 범위를 넓힌다.

Architecture:
- 기존 brief/watchlist/portfolio 중심 구조는 유지한다.
- 새 기능은 "작은 묶음(bundle)" 단위로 붙인다.
- 각 bundle은 테스트 추가 -> 최소 구현 -> CLI 검증 순서로 간다.

Available sources to exploit now:
- Toss index snapshots
- Toss news feed
- SaveTicker breaking/news items
- local DB history
- watchlist.json
- portfolio symbols
- existing technical_snapshot
- earnings storage/fetch

Priority rule:
1. 기능 폭 확장
2. 실전 의사결정 도움
3. 기존 출력 구조 재사용
4. 디테일 polish는 뒤로

---

## Bundle A — Watchlist / Portfolio 실전 기능

1. portfolio-only brief
- 보유종목만 따로 요약
- 포지션 경고/신선도/관련 뉴스 우선

2. watchlist movers ranking
- watchlist 중 오늘 가장 볼 종목 3~5개 자동 선정
- 기준: freshness + related news + earnings proximity + technical alert

3. portfolio thesis break monitor
- 기존 포지션 경고를 확장해서
  "왜 위험한지"를 1줄 reason으로 표시

4. symbol priority score output
- 각 종목에 우선순위 점수 부여
- brief 상단에 "오늘 먼저 볼 종목" 생성

5. no-news symbol surfacing
- watchlist 내 뉴스 공백 종목 표시
- "오늘 정보 부족"도 의사결정 정보로 활용

## Bundle B — News / Signal 기능

1. catalyst board
- 상승/하락/루머/매크로/실적 카테고리별 핵심 뉴스 묶음

2. duplicate/echo collapse
- 같은 이슈를 여러 headline이 반복하면 하나로 합치기

3. rumor board
- 루머만 따로 모아서 보여주기
- 검증 필요 항목 빠르게 확인 가능

4. source mix summary
- Toss 중심인지 SaveTicker 중심인지
- 통신 위주인지 혼합인지 요약

5. stale source ranking
- 어떤 소스가 가장 오래됐는지 순서화

## Bundle C — Earnings / Event 기능

1. earnings-nearby alert
- 7일 이내 실적 종목만 상단 별도 노출

2. post-earnings follow-up
- 실적 직후 체크리스트 자동 생성

3. event calendar brief
- 실적/속보/포지션경고를 한 블록으로 묶음

4. earnings-first mode
- "이번주 실적 뭐 보지" 요청에 특화 모드

## Bundle D — Question Modes

1. why-this-symbol mode
- "왜 NVDA 봐야 해?"에
  뉴스/차트/실적/포지션 relevance로 대답

2. compare mode
- "NVDA vs AMD 뭐 먼저 볼까"

3. what-changed mode
- DB 기준 마지막 브리핑 이후 달라진 점 요약

4. overnight recap mode
- 장후~장전 사이 변화만 요약

## Bundle E — 운영 편의 기능

1. saved presets
- morning brief
- after close brief
- portfolio guard
- earnings check

2. mode auto-routing 강화
- 요청 문구만으로 compare / why / earnings-first / overnight 감지

3. compact trader view
- 초단문 5줄 브리핑

4. deep view
- 지금 구조 유지한 상세 브리핑

---

## Recommended next implementation order

Phase 1 (즉시 효율 큼)
- watchlist movers ranking
- portfolio-only brief
- catalyst board
- earnings-nearby alert

Phase 2 (실전 사용성 큼)
- compare mode
- what-changed mode
- overnight recap mode
- rumor board

Phase 3 (후속 확장)
- duplicate collapse
- thesis break reason
- saved presets
- compact trader view

## Immediate next bundle to build

Bundle next:
1. watchlist movers ranking
2. portfolio-only brief
3. catalyst board
4. earnings-nearby alert

Expected impact:
- 사용자가 "오늘 뭐 봐야 함"에 바로 답 가능
- 보유종목/관심종목/실적/속보를 분리해서 보여줄 수 있음
- 현재 소스만으로도 기능 폭이 크게 넓어짐

## Verification rule

For every feature:
- targeted unittest
- full unittest discover
- one real CLI run

## Non-goal for now

- 세밀한 문구 polish 반복
- technical indicator 정교화
- 외부 신규 소스 연동
- TradingView 실연동
