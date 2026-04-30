# Reference repos 적용 메모

이 문서는 `/mnt/d/Agents/reference` 에 shallow clone 해 둔 공개 프로젝트들을 `stock-research-agent`에 어떻게 적용할지 정리한 메모다.

원칙:
- FinceptTerminal/OpenBB처럼 AGPL 계열은 코드 복붙 금지. UX/아키텍처만 참고한다.
- MIT/Apache/BSD 계열도 우선은 구조 참고 + 독립 구현을 기본으로 한다.
- 실전 기능 폭을 넓히는 순서: SEC/공시 → DataHub-lite topic → 분석위원회 → 포트폴리오/리스크 → 백테스트/ML.

## 1. dgunning/edgartools
- 경로: `/mnt/d/Agents/reference/edgartools`
- 라이선스: MIT
- 참고 가치: SEC/EDGAR 공시 탐색, filing/document 개념, company lookup UX.
- 현 적용:
  - `src/sec_filings.py` 를 독립 구현으로 추가.
  - SEC 공식 JSON endpoint 기반으로 CIK 해석, 최근 8-K/10-Q/10-K/S-3 등 분류, SEC filing URL 생성.
  - `--mode sec_filings` 및 공시/EDGAR 키워드 자동 라우팅 추가.
- 다음 확장:
  - accession document index/primary document 원문 fetch.
  - 8-K exhibit 99.1, press release, S-3 dilution risk 자동 라벨링.
  - 공시 이벤트를 topic hub의 `filing:sec:{SYMBOL}` live source로 연결.

## 2. FinceptTerminal
- 설치 경로: `D:\Agents\apps\FinceptTerminal`
- 참고 경로/맥락: Bloomberg/OpenBB식 desktop terminal, DataHub, agent, tools, backtesting UX.
- 라이선스 주의: AGPL-3.0 + Commercial로 확인됨. stock-agent에 코드 복사 금지.
- 현 적용:
  - DataHub 개념만 독립 재구현해서 `src/topic_hub.py` 추가.
  - `--mode topic_hub` 에서 Fincept식 topic 이름과 캐시 peek 제공.
  - 예: `market:quote:NVDA`, `news:symbol:NVDA`, `filing:sec:NVDA`, `options:chain:NVDA`, `social:threads:NVDA`, `earnings:calendar:NVDA`.
- 다음 확장:
  - topic registry를 JSON/YAML로 분리.
  - topic별 stale threshold, live fetch command, alert routing 추가.
  - Telegram/TradingView payload에서 topic 단위로 필요한 소스만 호출.

## 3. TauricResearch/TradingAgents
- 경로: `/mnt/d/Agents/reference/TradingAgents`
- 라이선스: Apache-2.0
- 참고 가치: bull/bear/researcher/trader/risk-manager 식 분석위원회 패턴.
- 적용 방향:
  - 코드 복사보다 `analysis_committee` 모듈로 독립 구현.
  - 한 종목에 대해 bullish, bearish, catalyst, risk, portfolio_guard 관점을 분리 생성.
  - 최종 출력은 “진입 후보/보류/회피 + 핵심 가격대 + 무효화 조건”으로 압축.
- 추천 우선순위: 중간. SEC/topic 기반 소스가 모인 다음 붙이면 품질이 좋아진다.

## 4. PyPortfolio/PyPortfolioOpt
- 경로: `/mnt/d/Agents/reference/PyPortfolioOpt`
- 라이선스: MIT
- 참고 가치: mean-variance, efficient frontier, expected returns, covariance shrinkage.
- 적용 방향:
  - 포트폴리오 비중 제안용 `portfolio_optimizer` 모듈.
  - 현재가/히스토리 데이터가 충분한 종목만 대상으로 risk budget, max weight, sector cap 적용.
  - 출력은 “비중 확대/축소 후보 + 변동성/상관 리스크” 중심.

## 5. dcajasn/Riskfolio-Lib
- 경로: `/mnt/d/Agents/reference/Riskfolio-Lib`
- 라이선스: BSD 계열
- 참고 가치: CVaR, drawdown, risk parity, 다양한 리스크 목적함수.
- 적용 방향:
  - PyPortfolioOpt 다음 단계로 리스크 중심 optimizer를 참고.
  - 단기 실전용으로는 CVaR/Max Drawdown guard만 먼저 구현.

## 6. microsoft/qlib
- 경로: `/mnt/d/Agents/reference/qlib`
- 라이선스: MIT
- 참고 가치: ML 리서치 파이프라인, dataset/feature/backtest/experiment 구조.
- 적용 방향:
  - 당장 통합보다 실험 구조 참고.
  - `data/raw`, `data/processed`, `experiments`, `reports` 분리.
  - 나중에 factor 연구, walk-forward 검증, feature store가 필요해질 때 사용.

## 7. pmorissette/bt
- 경로: `/mnt/d/Agents/reference/bt`
- 라이선스: MIT
- 참고 가치: 단순 전략 백테스트, allocation/rebalance 흐름.
- 적용 방향:
  - TradingView alert 후보의 사후검증용 mini-backtest에 적합.
  - `buy on alert`, `hold N days`, `stop/take profit` 같은 단순 룰부터 자체 구현.

## 8. nautechsystems/nautilus_trader
- 경로: `/mnt/d/Agents/reference/nautilus_trader`
- 라이선스: LGPL-3.0
- 참고 가치: 고성능 이벤트 기반 trading engine, order/execution/risk 모델.
- 적용 방향:
  - 현재 stock-agent에는 과함. 실거래/페이퍼 트레이딩 엔진 단계에서 참고.
  - 주문/체결 모델 구조만 참고하고 직접 import는 보류.

## 9. OpenBB-finance/OpenBB
- 경로: `/mnt/d/Agents/reference/OpenBB`
- 라이선스: AGPL-3.0
- 참고 가치: 터미널 UX, provider abstraction, financial data command taxonomy.
- 주의: AGPL이므로 코드 복붙 금지. command taxonomy/UX만 참고.
- 적용 방향:
  - `stock-agent topic -> provider -> output formatter` 형태의 명령 체계 참고.

## 현재 반영된 변경 요약
- SEC/EDGAR mode: `src/sec_filings.py`, `tests/test_sec_filings.py`, `src/main.py` wiring.
- DataHub-lite topic mode: `src/topic_hub.py`, `tests/test_topic_hub.py`, `src/main.py` wiring.
- 전체 테스트 기준: `python3 -m unittest discover -s tests -p 'test_*.py'` 통과.

## 다음 구현 후보 순서
1. `filing:sec:{SYMBOL}` topic을 live SEC fetch와 연결.
2. `analysis_committee`로 TradingAgents식 bull/bear/risk/catalyst 합의 출력.
3. `portfolio_optimizer`로 PyPortfolioOpt식 비중/리스크 제안.
4. 단순 alert backtest로 TradingView 후보 사후검증.
5. qlib류 research pipeline은 데이터가 쌓인 뒤 별도 실험 트랙으로 분리.
