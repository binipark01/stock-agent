# Threads 관점 학습 후보 — 2026-05-04

소스:
- `config/threads_seed_accounts_classified.json`
- public Threads/Jina profile reconnaissance: `/tmp/threads_candidates`
- 후보 JSON: `data/threads_view_candidates_2026-05-04.json`

## 1순위: @trader_jsb / 트레이더 범

역할: risk-process trend trader

관찰:
- 기술적 분석 위주
- 추세추종 매매 위주
- 손절가 -10%
- 비중 최대 20%
- 손익비 관점 강조
- “결론보다 과정 공유” 성향

왜 학습해야 하나:
- 양봉업자가 섹터/모멘텀/과열 경고라면, 트레이더 범은 손절·비중·손익비 룰을 학습하기 좋다.
- stock-agent의 진입/손절/비중 프레임에 바로 쓸 수 있음.

학습 포인트:
- 손절선 언급 방식
- 비중 관리
- 손익비 기반 셋업
- 틀릴 수 있음을 전제로 한 관점 업데이트

## 2순위: @trader_chan_ / Chan

역할: macro → sector → stock top-down swing trader

관찰:
- 매크로 기반 스윙 트레이더
- Chasing Strength / 강세 모멘텀 전략
- Macro → Sector → Stock 탑다운 매매
- 절대수익/알파 추구
- 확률적 사고와 절제

왜 학습해야 하나:
- 양봉업자 프레임을 다른 섹터에 일반화하기 가장 좋은 후보.
- 매크로 → 섹터 → 종목 순서가 명확함.

학습 포인트:
- 매크로 레짐 판단
- 섹터 선택
- 강세 모멘텀 추격/눌림 구분
- 스윙 시간축

## 3순위: @model_qqqq / 미국주식ㅣ모델Q

역할: US stock news mapping / AI ecosystem mapper

관찰:
- CFA Charterholder
- 엔비디아 파트너십 정리 포스트 확인
- AI 팩토리, 자율주행, 양자, 제약, 슈퍼컴, 보안, 로봇, 6G 등 테마-기업 매핑
- 장중/전일 뉴스 요약

왜 학습해야 하나:
- 가격 트레이더보다는 catalyst/map 소스.
- stock-agent의 “뉴스 → 관련 종목/테마 매핑” 품질 개선에 유용.

학습 포인트:
- AI ecosystem map
- 파트너십/뉴스 연결
- 테마별 관련주 분류

## 4순위: @bullstory1 / 미국주식 불스토리

역할: US stock story/deep-dive + crowd thermometer

관찰:
- 팔로워 66K
- 미국주식의 모든 것
- POET 같은 AI 광학 회사 급등락/주문 취소 이슈를 story 형태로 설명
- 팔로워가 많아 FOMO 증폭 가능성도 큼

왜 학습해야 하나:
- 개별주 스토리와 crowd 반응을 동시에 보기 좋음.
- 단, 추천 신뢰도보다 군중심리/스토리 확산 감지로 써야 함.

학습 포인트:
- 개별주 catalyst story
- 급등락 이벤트
- rumor/confirmed 분리
- crowd/FOMO 탐지

## 5순위: @us_stock_info / 미국주식가이드

역할: US stock sector/theme idea source

관찰:
- AI, Tech, Health, Investment
- 최근 의료/바이오 관련 장문 포스트 확인
- 반도체 이외 섹터 아이디어 보완용

왜 학습해야 하나:
- 반도체 편중을 줄이고 헬스케어/바이오/AI테크 쪽 관점을 보완.

학습 포인트:
- 헬스케어/바이오
- AI/테크
- 섹터 아이디어 발굴

## 6순위: @developmong / 디벨롭몽

역할: crypto/stock risk-cycle + FOMO thermometer

관찰:
- 주식·코인 유튜브 15만
- 자산 급증/FOMO 포스트와 동시에 버핏 현금비중, 강세장 후반 불안 언급
- QLD 같은 레버리지 군중심리도 포착 가능

왜 학습해야 하나:
- 코인/고베타 risk-on/off 온도계로 쓸 수 있음.
- 다만 신뢰도 높은 분석보다 crowd sentiment bucket으로 분리.

학습 포인트:
- 코인/고베타 FOMO
- 강세장 후반 경계
- 레버리지 ETF crowding

## 7순위: @nyu_trader / 뉴욕대 투자자

역할: Nasdaq trade-result / risk management source

관찰:
- 나스닥, 경제 이야기
- 타점 결과/수익률 인증형 포스트가 많음
- 오라클, URA, XBI, 메타, 넷플, MU 등의 결과 언급

왜 학습해야 하나:
- outcome tracking 실험 대상으로 좋음.
- 다만 성과 과시형 포스트는 반드시 검증 필요.

학습 포인트:
- 타점 기록
- 결과 검증
- 나스닥/성장주 판단
- 리스크 관리

## 후순위/별도 bucket

- @god_chart: 차트/시장 브리핑 계정. 공개 포스트 확보 부족. 수동 URL 확보 후 재평가.
- @king_gyul23: 국내주식/교육형. 한국주식 감각용 후보.
- @futuresnow_news: 오선의 미국 증시. SaveTicker/오선 API와 중복되므로 news source로 유지.
- @irendebate: IREN 특화 후보. IREN 요청 시 우선 수동 검증.
- @jjang_news: 뉴스 요약 source. persona보다는 뉴스 큐레이션 bucket.

## 추천 학습 순서

1. trader_jsb
2. trader_chan_
3. model_qqqq
4. bullstory1
5. us_stock_info
6. developmong
7. nyu_trader

## 기능적으로 나누면

- 리스크/손절/비중: trader_jsb
- 탑다운 섹터 로테이션: trader_chan_
- AI/미국주식 catalyst map: model_qqqq
- 개별주 스토리/FOMO: bullstory1
- 비반도체 섹터 아이디어: us_stock_info
- 코인/고베타 crowd: developmong
- 타점/outcome 검증: nyu_trader
