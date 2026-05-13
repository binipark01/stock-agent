# Kiwoom KRX Supply-Trading Agent Architecture Plan

Goal: Kiwoom OpenAPI 기반 국장 수급/감시/리서치 에이전트를 제대로 설계한다. 기본은 read-only. 주문/신용주문은 별도 안전 설계 전까지 hard-disable.

Source references:
- docs/references/kiwoom-api-inventory.md: 국내주식 16 categories, 205 APIs
- src/kiwoom_client.py: token/env/post_tr
- src/krx_flows_kiwoom.py: current snapshot/rank/candidate implementation
- src/kiwoom_realtime.py: websocket helpers

Important wording:
- mockapi.kiwoom.com is Kiwoom 모의투자 도메인 실호출, not fake fixture.
- Always print source=kiwoom, env=mock|prod, collected_at, endpoint/TR, status, base_date if available.

## 1. Product definition

Primary question:
지금 국장에서 거래대금이 붙고 외국인/기관/프로그램/거래원/대차·공매도·신용/테마 흐름이 동시에 좋은 종목은 무엇이며, 추격할 자리인지 눌림을 기다릴 자리인지?

Non-goals:
- no auto trading
- no order placement
- no credit order placement
- no unlabelled mock/prod mixing
- no one-TR buy conclusion

## 2. Risk tiers

Tier A: market read-only, implement first
- /api/dostk/mrkcond 시세
- /api/dostk/stkinfo 종목정보
- /api/dostk/rkinfo 순위정보
- /api/dostk/frgnistt 기관/외국인
- /api/dostk/slb 대차거래
- /api/dostk/shsa 공매도
- /api/dostk/sect 업종
- /api/dostk/thme 테마
- /api/dostk/etf ETF
- /api/dostk/chart 차트
- /api/dostk/websocket 실시간시세/조건검색

Tier B: sensitive account read-only, later behind flag
- /api/dostk/acnt 계좌
- account number, cash, holdings, pnl, fills, pending orders
- mask account number, no Telegram by default, no raw log

Tier C: mutating APIs, disabled
- /api/dostk/ordr 주문
- /api/dostk/crdordr 신용주문
- catalog only; no wrappers unless separate safety plan approved

## 3. Layered architecture

Layer 1: Transport
- file: src/kiwoom_client.py
- responsibilities: env loading, mock/prod base, env-scoped token cache, post_tr, pagination, safe errors
- no domain parsing here

Layer 2: API catalog
- create: src/kiwoom_api_catalog.py
- test: tests/test_kiwoom_api_catalog.py
- registry fields: api_id, name, category, endpoint, risk_tier, default_body, row_keys, priority
- helper: get_tr(api_id), assert_tr_allowed(api_id, allow_account=False, allow_order=False)

Layer 3: Raw collectors
- create: src/kiwoom_collectors.py
- test: tests/test_kiwoom_collectors.py
- wrap client.post_tr with catalog lookup
- normalize to TRCallResult with source, env, endpoint, api_id, collected_at, return_code, return_msg, cont_yn, next_key, status

Layer 4: Domain models
- create: src/krx_models.py
- JSON-serializable dict/dataclass models:
  - KrxSymbol
  - TRCallResult
  - QuoteSnapshot
  - InvestorFlowSnapshot
  - ProgramFlowSnapshot
  - ForeignInstitutionFlow
  - ShortSaleSnapshot
  - StockLoanSnapshot
  - CreditSnapshot
  - BrokerFlowSnapshot
  - ThemeSnapshot
  - SectorSnapshot
  - RealtimeEvent
  - KrxCandidate
  - KrxAlert

Layer 5: Feature collectors
- split over time instead of growing one huge file:
  - src/krx_quotes_kiwoom.py
  - src/krx_supply_kiwoom.py
  - src/krx_rankings_kiwoom.py
  - src/krx_theme_kiwoom.py
  - src/krx_realtime_watch.py
  - src/krx_account_readonly.py later

Layer 6: Scoring/reporting
- create: src/krx_candidate_scoring.py
- keep report formatting separate from collection
- output concise Korean triage, not buy recommendation

## 4. Data domains

Price/liquidity:
- ka10001 주식기본정보
- ka10003 체결정보
- ka10004 주식호가
- ka10032 거래대금상위
- ka10023 거래량급증
- ka10080 분봉
- ka10081 일봉
- realtime 0B 주식체결
- realtime 0D 호가잔량
Signals: trade_value_top, volume_surge, price_breakout, vwap_reclaim, orderbook_bid_support, execution_strength_spike

Investor/foreign/institution:
- ka10063 장중투자자별매매
- ka10066 장마감후투자자별매매
- ka10065 장중투자자별매매상위
- ka90009 외국인기관매매상위
- ka10008 주식외국인종목별매매동향
- ka10009 주식기관
- ka10131 기관외국인연속매매현황
- ka10059 종목별투자자기관별
- ka10061 종목별투자자기관별합계
- ka10060 종목별투자자기관별차트
- ka10064 장중투자자별매매차트
Signals: foreign_net_buy_top, institution_net_buy_top, double_buy, buy_streak, retail_sell_absorption, flow_acceleration
Rule: ka90009 buckets must stay separate: foreign buy/sell, institution buy/sell.

Program trading:
- ka90003 프로그램순매수상위50
- ka90004 종목별프로그램매매현황
- ka90008 종목시간별프로그램매매추이
- ka90013 종목일별프로그램매매추이
- realtime 0w 종목프로그램매매
Signals: program_net_buy_top, program_buy_acceleration, program_reversal_to_buy, program_sell_pressure

Short/loan/credit:
- ka10014 공매도추이
- /api/dostk/slb 대차거래 TRs from inventory
- ka10013 신용매매동향
- ka10033 신용비율상위
- kt20016/kt20017 신용융자 가능종목/문의
Signals: short_cover_candidate, stock_loan_balance_drop/spike, credit_ratio_high_risk, credit_unwind_risk
Rule: modifies risk/squeeze probability; not standalone buy signal.

Broker/dealer:
- ka10002 주식거래원
- ka10043 거래원매물대분석
- ka10052 거래원순간거래량
- ka10078 증권사별종목매매동향
- ka10042 순매수거래원순위
- realtime 0F 주식당일거래원
Signals: broker_net_buy_concentration, dealer_momentum_spike

Theme/sector/ETF:
- ka90001 테마그룹별
- ka90002 테마구성종목
- ka10010 업종프로그램
- ka10051 업종별투자자순매수
- ka20001/2/3 업종현재가/주가/전업종지수
- ETF ka40001~ka40010
Signals: theme_leader, theme_breadth_positive, sector_investor_net_buy, sector_program_buy, etf_confirming

Realtime:
- 0B 주식체결
- 0D 주식호가잔량
- 0w 종목프로그램매매
- 0F 주식당일거래원
- 1h VI발동/해제
- 0H 예상체결
Use only after REST scan narrows candidates.

## 5. Candidate scoring v2

Total 0-100.

Liquidity/price 25:
- 거래대금 상위 +8
- 거래량 급증 +5
- 분봉 돌파/VWAP 회복 +5
- 체결강도 상승 +4
- 호가 매수잔량 우위 +3

Investor sponsorship 25:
- 외국인 순매수 상위 +7
- 기관 순매수 상위 +7
- 외국인+기관 동시 순매수 +6
- 연속 순매수 +3
- 개인 매도 물량 흡수 +2

Program/broker 15:
- 프로그램 순매수 상위 +6
- 프로그램 매수 가속 +4
- 거래원 순매수 집중 +3
- 당일거래원 실시간 확인 +2

Theme/sector 15:
- 테마 리더 +5
- 테마 breadth 양호 +4
- 업종 투자자 순매수 +3
- 업종 프로그램 양호 +2
- 관련 ETF 강세 +1

Pressure/risk -20 to +10:
- 대차잔고 급감 + 공매도 감소 +5
- 숏커버 후보 +5
- 대차잔고 급증 -5
- 공매도 급증 -5
- 신용비율 과열 -5
- VI/급등 과열 -5

Buckets:
- >=75 주도수급
- 60-74 눌림대기
- 45-59 수급확인
- 30-44 관찰
- risk-dominant 위험제외
- missing core data 데이터부족

Allowed judgments:
- 추격 금지, 눌림 대기
- 돌파 재확인 시 관심
- 수급은 좋지만 과열
- 거래대금만 있고 수급 약함
- 외인/기관 확인 전 관찰
- 공매도/대차 리스크로 제외

## 6. User-facing modes

krx_market_scan:
- broad market scan
- output: 수집정보, 장 분위기, 거래대금/거래량, 외인/기관/프로그램, 대차/공매도/신용, 후보

krx_symbol_snapshot:
- one stock deep dive
- output: price, orderbook, investor, program, broker, short/loan/credit, chart, theme/sector, conclusion

krx_flow_rank_scan:
- current mode, extend with volume surge, orderbook surge, foreign streak, credit risk, short/loan summary, theme overlay

krx_theme_scan:
- theme group/components + sector flow + ETF confirmation + candidates

krx_realtime_watch:
- REST scan every 5 min, subscribe top candidates to 0B/0D/0w/1h/0F, debounce alerts

krx_condition_scan:
- Kiwoom condition list/general/realtime condition search, then enrich hits with scoring

krx_account_snapshot:
- later only, read-only, masked, no order

## 7. Watcher design

Files:
- scripts/run_krx_supply_watch.py
- src/krx_watch_state.py
- tests/test_krx_watch_state.py

State:
- data/krx_supply_watch_state.json

Loop:
- broad REST scan every 5 minutes during market hours
- top 20 candidates go to realtime subscription
- alert only on score crossing, new candidate, signal strengthening, risk flip, or 눌림 도달
- debounce same symbol/trigger for 15 minutes
- after close produce wrap-up with 장마감후 investor flow

## 8. Data quality contract

Every section has:
- source
- env
- endpoint
- api_id
- collected_at
- base_date if available
- status
- return_msg on failure/unavailable

Never:
- say 오늘/실시간 without returned date/cadence
- hide empty/error section
- score missing data as zero without marking missing
- collapse foreign/institution buckets
- print secrets/account/token

## 9. Implementation phases

Phase 0: Catalog and safety foundation
- src/kiwoom_api_catalog.py
- tests/test_kiwoom_api_catalog.py
- category registry for 16 categories
- P0/P1 TR registry
- risk-tier gate

Phase 1: Collector abstraction
- src/kiwoom_collectors.py
- tests/test_kiwoom_collectors.py
- TRCallResult normalization
- safe failure handling
- pagination support

Phase 2: Rank scanner v2
- src/krx_rankings_kiwoom.py
- tests/test_krx_rankings_kiwoom.py
- preserve compatibility in src/krx_flows_kiwoom.py
- add 거래량급증, 호가잔량급증, 외인연속, 신용비율 risk, theme overlay

Phase 3: Symbol snapshot v2
- src/krx_symbol_snapshot.py
- tests/test_krx_symbol_snapshot.py
- combine quote / orderbook / investor / program / broker / short / loan / credit / chart / theme

Phase 4: Theme/sector engine
- src/krx_theme_kiwoom.py
- tests/test_krx_theme_kiwoom.py
- theme group/component, sector investor/program, ETF confirmation

Phase 5: Scoring engine v2
- src/krx_candidate_scoring.py
- tests/test_krx_candidate_scoring.py
- 0-100 score, buckets, risk adjustment, chase-vs-wait

Phase 6: Realtime watch
- src/krx_realtime_watch.py
- scripts/run_krx_supply_watch.py
- tests/test_krx_realtime_watch.py
- rolling features, debounce, state

Phase 7: Account read-only
- src/krx_account_readonly.py
- tests/test_krx_account_readonly.py
- gated, masked account, no mutation

## 10. P0 TRs

Ranking:
- ka10032 거래대금상위
- ka10023 거래량급증
- ka10065 장중투자자별매매상위
- ka90009 외국인기관매매상위
- ka90003 프로그램순매수상위50

Symbol snapshot:
- ka10001 주식기본정보
- ka10004 주식호가
- ka10046 체결강도추이시간별
- ka10063 장중투자자별매매
- ka10008 주식외국인종목별매매동향
- ka10009 주식기관
- ka90008 종목시간별프로그램매매추이
- ka90004 종목별프로그램매매현황
- ka10014 공매도추이
- ka10013 신용매매동향
- 대차거래 P0 TRs from inventory

Theme/sector:
- ka90001 테마그룹별
- ka90002 테마구성종목
- ka10051 업종별투자자순매수
- ka10010 업종프로그램
- ka20003 전업종지수
- ka40004 ETF전체시세
- ka40002 ETF종목정보

Realtime:
- 0B 주식체결
- 0D 호가잔량
- 0w 종목프로그램매매
- 1h VI발동/해제

## 11. Verification commands

Focused:
python3 -m unittest tests.test_kiwoom_api_catalog tests.test_kiwoom_collectors tests.test_krx_rankings_kiwoom tests.test_krx_candidate_scoring

Broad:
python3 -m py_compile src/kiwoom_client.py src/kiwoom_api_catalog.py src/kiwoom_collectors.py src/krx_rankings_kiwoom.py src/krx_candidate_scoring.py src/main.py src/request_modes.py
python3 -m unittest discover -s tests -p 'test_*.py'

Live smoke:
- sanitized only: env, endpoint, api_id, return_code, return_msg, row_count, top code/name
- no token/appkey/secret/account

## 12. Design decision

Build this as a layered Kiwoom-backed KRX intelligence engine:
1. catalog/risk-tier APIs
2. normalize every TR with metadata
3. expand read-only market/supply data first
4. score only multi-source confirmations
5. use realtime only after REST narrows candidates
6. add account read-only later
7. keep orders disabled
