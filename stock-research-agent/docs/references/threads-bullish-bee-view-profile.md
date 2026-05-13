# @bullish_bee / 양봉업자 관점 학습 프로필

학습일: 2026-05-03
소스: `data/threads_view_bullish_bee_snapshot_2026-05-03.json`
프로필 JSON: `data/threads_view_profiles/bullish_bee_profile.json`

## 한 줄 모델

양봉업자는 반도체/메모리/AI 인프라를 주도섹터로 보고, SOXX 장기 채널 돌파와 내부 대장주 순환을 근거로 중기 bullish를 유지하되 SNDK 상승 사이클 후반부와 이격 부담 때문에 5월 중순 이후 단기 조정을 경계하는 추세추종형 트레이더다.

## 핵심 관점

- 장기: 반도체는 단순 사이클 반등이 아니라 AI 인프라 수요로 구조적 성장주/리레이팅 국면에 들어갈 수 있다.
- 중기: SOXX는 아직 숏각이 아니며 조정이 오면 1순위로 다시 볼 대상이다.
- 단기: SNDK/메모리 랠리가 30~40일 상승 패턴 후반부에 가까워져 5월 중순 이후 가격조정과 이격 부담을 경계한다.
- 현재 톤: bullish but risk-aware. 추격보다 조정/눌림 재진입 쪽으로 이동 중.

## 판단 순서

1. 섹터 자금 유입
   - SOXX/SOXL/반도체 ETF가 강하면 반도체 주도섹터 thesis를 인정한다.

2. 장기 채널 돌파
   - SOXX 장기 채널 상단 돌파를 과열/오버슈팅보다 구조적 리레이팅 가능성으로 해석한다.

3. 내부 주도주 순환
   - 브로드컴이 쉬면 메모리, 메모리가 쉬면 CPU, 장비주가 쉬면 NVDA가 받치는 식의 순환이 살아 있으면 아직 숏각이 아니라고 본다.

4. 신고가 + 흰선 필터
   - 처음 신고가 돌파와 수렴 돌파를 중요하게 본다.
   - 캔들이 자체 흰선 위에 있으면 상승 추세, 아래면 하락 추세로 분류한다.
   - 최근 흰선 위 종목으로 TSM, NVDA, SNDK, MU를 언급했다.

5. SNDK 트리거
   - SNDK를 메모리/AI 인프라 대장주로 본다.
   - SNDK 급락은 SOXX/반도체 단기 조정 트리거로 해석한다.

6. 상승 impulse 나이
   - SNDK가 보통 30~40일 상승하는 패턴이 있고 현재 후반부라 5월 중순 이후 조정을 경계한다.

## 선호 유니버스

- ETF: SOXX, SOXL
- 핵심 종목: SNDK, STX, MU, NVDA, TSM, 삼성전자, SK하이닉스
- 테마: 반도체, 메모리, DRAM, AI 인프라, 스토리지, 반도체 내부 순환

## bullish 확인 문구

- 장기 채널 상단 돌파
- 구조적 성장주
- SOXX 아직 숏각 아님
- 처음 신고가 돌파
- 흰선 위
- 주도 종목이 계속 바뀜
- 반도체에 돈이 들어오고 있다

## risk warning 문구

- 5월 중순부터 조심
- 이격 부담
- 가격조정
- 너무 취하지
- SNDK 급락
- 상승세가 길어야 2주
- 조정 재료는 만들기 나름

## agent 사용 규칙

1. `bullish_bee_semis_structural_bull`
   - SOXX/반도체 + 장기 채널/구조적/리레이팅 언급 시 `semis_structural_bullish=true`.
   - 단, 단기 매수 신호로 바로 쓰지 말고 가격 확인 필요.

2. `bullish_bee_semis_rotation_alive`
   - 주도 종목 순환, 브로드컴/메모리/CPU/장비주/NVDA 순환 언급 시 반도체 rotation alive 가중.
   - AVGO/MU/SNDK/NVDA/TSM/SOXX 상대강도 확인.

3. `bullish_bee_sndk_trigger_risk`
   - SNDK + 급락/저항/시장도 꺾임/30~40일/이격 부담 언급 시 SNDK를 SOXX 단기 리스크 트리거로 지정.

4. `bullish_bee_tone_shift_warning`
   - `더 간다/숏각 아님`에서 `조심/가격조정/이격 부담`으로 바뀌면 late-cycle warning.
   - 출력은 추격 금지 / 눌림 대기 프레임으로.

5. `bullish_bee_not_trade_advice`
   - 항상 Threads persona view로 라벨링한다.
   - 가격, 섹터 강약, 뉴스/실적, 옵션/공시와 교차검증한다.

## 강점

- 주도섹터 감각이 강함.
- 반도체 내부 대장주 순환을 봄.
- 과열을 곧바로 숏으로 연결하지 않고 breadth/rotation을 확인함.
- 월봉 장기 thesis와 일봉 단기 조정을 분리함.
- 차트를 필터링 도구로 보고 공부/확신 과정을 언급함.

## 리스크/편향

- 최근 관점이 반도체/SOXX/SNDK에 과도하게 집중.
- 강한 모멘텀 구간에서는 follower FOMO를 증폭할 수 있음.
- SOXX 600/660, 40% 추가 상승 같은 수치 목표는 별도 검증 필요.
- 하락 전환 인정 속도와 숏 판단 성능은 아직 데이터 부족.
- 차트 이미지 기반 흰선/채널 설명은 텍스트만으로 재현 불완전.

## 활용 결론

양봉업자 관점은 매수 추천이 아니라 반도체 sentiment/timing overlay로 써야 한다.
특히 bullish 성향 계정이 `조심`, `가격조정`, `이격 부담`을 말하기 시작하는 순간을 고가치 신호로 취급한다.
