# @us_stock_info / 미국주식가이드 관점 학습 프로필

학습일: 2026-05-05
소스: `data/threads_view_us_stock_info_snapshot_2026-05-05.json`
프로필 JSON: `data/threads_view_profiles/us_stock_info_profile.json`

## 한 줄 모델

미국주식가이드는 순수 차트 트레이더라기보다 Threads/Reddit/공시성 이벤트에서 미국주식 테마를 빠르게 발굴하고, 헬스케어·바이오·AI/테크·양자 같은 고베타 스토리를 시나리오와 리스크 분석으로 거르는 `theme-story discovery persona`다.

## 핵심 관점

- 큰 테마: Health, AI, Tech, Investment, 양자, 코인/고베타 리스크온.
- 강한 축: 헬스케어/바이오, 특히 고령화·치매·의료비 방어성 narrative.
- 아이디어 발굴 방식: Threads/Reddit 경제·금융 글을 틈틈이 계속 읽고 정리하면서 괜찮은 아이디어를 필터링.
- 트레이딩 태도: 본인 시나리오와 리스크 분석 후 진입, 무지성 롱/숏 금지, 시장 변화에 대응.
- 주의점: 고베타 바이오/양자에서 티커 미공개·몇 배 수익·우리끼리 먹자 식 FOMO 문구가 섞이므로 그대로 매매 신호로 쓰면 안 됨.

## 관찰된 구체 테마/종목

### CGTX / 코그니션 테라퓨틱스

- 관점: bullish story.
- 논리:
  - 경기가 좋든 나쁘든 의료비 지출은 끊기 어렵다.
  - 금리인하가 다가오고 있고, 메디케어/셧다운 이슈가 있다.
  - 전 세계 고령화, 스마트폰/스트레스, 치매 문제를 큰 구조 변화로 본다.
  - CGTX가 치매에 대한 새로운 대안 접근을 가진 회사로 해석된다.
  - 중소형 바이오주 역사적 붐 가능성을 기대한다.
- 체크 필요:
  - 임상 단계/결과
  - cash runway
  - 추가 증자/희석 가능성
  - SEC filings
  - 실제 catalyst timeline
  - claim 시점 이후 1D/5D/20D 가격 반응

### XNDU / 양자 / Xanadu 관련

- 관점: high-beta event watch.
- 관찰 문구:
  - 양자섹터: XNDU
  - 총 2억 9,365만 주 매각 승인 결정
  - 2,750만 주 PIPE 물량 제한 해제
  - 핵심은 거래량
  - 저점 대비 +23.75%
  - 시장에 풀리는 물량 참고
- 해석:
  - 이건 단순 bullish가 아니라 수급/오버행/거래량 이벤트로 봐야 한다.
  - stock-agent에서는 공시 확인 전 `event_watch / supply_risk`로 분류.

### 지수/ETF

- 언급: TQQQ, SPY, VOO, QQQ, SOXL.
- 성격: 교육/가이드성 언급에 가깝다.
- 주의: TQQQ/SOXL은 장기 보유 시 경로의존성/변동성 손실 설명을 붙여야 한다.

## 판단 순서

1. 테마 먼저
   - 헬스케어, AI/Tech, 양자, 코인/리스크온 등 큰 narrative를 본다.

2. 테마 안의 고베타 후보 발굴
   - 대형주보다 중소형 바이오/테마주 같은 급등 후보를 잘 포착하려는 성향.

3. 소셜 리서치 필터
   - Threads/Reddit 글을 많이 읽고 정리해서 아이디어 후보를 필터링.

4. 시나리오 수립
   - 본인만의 시나리오를 갖고 접근.

5. 리스크 분석
   - 충분히 리스크를 보고 들어간다고 명시.

6. 대응
   - 시장은 바뀔 수 있으니 항상 긴장하고 대응해야 한다는 태도.

7. FOMO 필터
   - 티커 미공개, 우리끼리 먹자, 이미 2~3배, 4~5배 기대 문구는 downrank.

## bullish 문구

- 세계적인 유망한 바이오 회사
- 전고점을 향하여
- 이제 출발할 것
- 중소형 바이오주 역사적 붐
- 좋은 기업은 배신하지 않는다
- 핵심: 거래량
- 저점 대비 +N%

## risk/process 문구

- 리스크 분석은 충분히 하고 들어가서 플레이
- 본인만의 시나리오
- 무지성 롱, 숏 믿지 않음
- 시장 상황이 어떻게 바뀔지 모름
- 항상 긴장
- 대응은 항상 하는게 맞음
- 바이오는 위험하니깐
- 시장에 풀리는 물량
- PIPE / 매각 승인 / 제한 해제

## downrank / 경고 문구

- 티커 언급 금지
- 우리끼리 맛있게 먹자
- 4-5배 보고 있음
- 이미 2배/3배 성과 과시만 있고 근거 부족
- 군함 피격 같은 확인 전 지정학 루머
- 타인 repost나 댓글 칭찬만 있는 경우

## agent 규칙

1. `us_stock_info_theme_discovery_not_signal`
   - 이 계정의 종목 언급은 매수/매도 신호가 아니라 theme idea candidate로 저장한다.

2. `us_stock_info_biotech_validation_gate`
   - 바이오/헬스케어 후보는 임상 단계, cash runway, dilution, SEC/news catalyst, 가격·거래량 확인 전 actionable alert로 승격하지 않는다.

3. `us_stock_info_supply_event_gate`
   - PIPE, 주식 매각 승인, lockup 제한 해제, 시장에 풀리는 물량 언급은 official filing/float data와 대조한다.
   - 공급 이벤트는 bullish가 아니라 risk/event-watch로 분류한다.

4. `us_stock_info_teaser_downrank`
   - 티커 미공개, 우리끼리 먹자, 몇 배 수익 claim, follower praise는 FOMO/teaser로 낮춘다.

5. `us_stock_info_scenario_required`
   - 이 계정 관점을 출력할 때는 반드시 author scenario, risk caveat, invalidation/response need를 같이 표시한다.

6. `us_stock_info_social_source_separation`
   - Threads/Reddit에서 읽고 필터링했다는 과정은 아이디어 발굴 경로로만 사용하고, 사실·공시·가격 데이터와 분리한다.

7. `us_stock_info_repost_not_direct_claim`
   - reposts의 타인 글은 직접 관점으로 저장하지 말고 crowd/context로만 태그한다.

## 강점

- 반도체 외 헬스케어/바이오/AI/테크/양자 같은 비주류 고베타 아이디어 발굴에 유용.
- 사회 구조 narrative와 종목 스토리 연결이 빠름.
- Threads/Reddit 소셜 리서치를 실제 아이디어 필터로 사용한다고 명시.
- 리스크 분석, 무지성 롱/숏 금지, 대응 필요성을 언급해 완전한 무지성 펌핑 계정보다는 process language가 있음.
- CGTX처럼 사후 검증 가능한 구체 ticker claim이 남아 outcome tracking에 적합.

## 리스크/편향

- 고베타 소형 바이오/양자 테마는 희석·락업·임상 실패·급등락 리스크가 큼.
- 일부 글은 티커 미공개/우리끼리 먹자/몇 배 수익식 FOMO 문구가 있어 그대로 쓰면 위험.
- 공개 페이지에서 이미지 속 세부 데이터가 빠져 있을 수 있음.
- fundamental evidence보다 narrative가 강하게 보이는 구간이 있음.
- 성과 claim은 매입가·매도·기간 검증 전 신뢰점수에 직접 반영하면 안 됨.

## 기존 persona와 조합

- `@bullish_bee` / 양봉업자:
  - 반도체/AI 인프라 주도섹터와 모멘텀 온도계.
  - 어디가 주도이고 과열인지 보는 용도.

- `@trader_jsb` / 트레이더 범:
  - entry/risk wrapper.
  - 어디서 들어가고, 손절/비중/금리 조건을 어떻게 둘지 보는 용도.

- `@us_stock_info` / 미국주식가이드:
  - 반도체 외 다음 테마 후보 발굴.
  - 헬스케어/바이오/양자/AI 테마 story source.

최종 사용 순서:

1. us_stock_info가 아이디어 후보를 던짐.
2. stock-agent가 공시/뉴스/가격/거래량/옵션/임상 catalyst 검증.
3. trader_jsb식으로 진입가·손절·비중 wrapper를 붙임.
4. bullish_bee식으로 해당 테마가 실제 시장 주도/과열인지 확인.
5. 그 다음에만 stock-agent 결론으로 승격.

## 활용 결론

미국주식가이드는 “매수 추천자”가 아니라 “비주류 고베타 테마 발굴 레이더”로 쓰는 게 맞다. 특히 헬스케어/바이오/양자 쪽에서 아이디어 후보를 빨리 잡는 데 유용하지만, stock-agent는 항상 공시·가격·거래량·희석·임상·뉴스 검증을 붙여야 한다.
