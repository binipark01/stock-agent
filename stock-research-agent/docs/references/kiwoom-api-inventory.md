# Kiwoom REST/OpenAPI 국내주식 API inventory

- collected_at: 2026-05-08 00:38:07 KST
- source: https://openapi.kiwoom.com/guide/apiguide
- checked with jobTpCode pages for 국내주식 categories listed in the Kiwoom guide.
- 운영 REST 도메인: https://api.kiwoom.com
- 모의투자 REST 도메인: https://mockapi.kiwoom.com (guide notes KRX only)
- WebSocket 운영: wss://api.kiwoom.com:10000/api/dostk/websocket
- WebSocket 모의: wss://mockapi.kiwoom.com:10000/api/dostk/websocket

## Summary

| jobTpCode | category | endpoint | API count |
|---:|---|---|---:|
| 08 | 계좌 | /api/dostk/acnt | 33 |
| 17 | 공매도 | /api/dostk/shsa | 1 |
| 03 | 기관/외국인 | /api/dostk/frgnistt | 4 |
| 12 | 대차거래 | /api/dostk/slb | 4 |
| 05 | 순위정보 | /api/dostk/rkinfo | 23 |
| 02 | 시세 | /api/dostk/mrkcond | 25 |
| 16 | 신용주문 | /api/dostk/crdordr | 4 |
| 14 | 실시간시세 | /api/dostk/websocket | 19 |
| 04 | 업종 | /api/dostk/sect | 6 |
| 15 | 조건검색 | /api/dostk/websocket | 4 |
| 01 | 종목정보 | /api/dostk/stkinfo | 31 |
| 13 | 주문 | /api/dostk/ordr | 8 |
| 07 | 차트 | /api/dostk/chart | 21 |
| 11 | 테마 | /api/dostk/thme | 2 |
| 06 | ELW | /api/dostk/elw | 11 |
| 10 | ETF | /api/dostk/etf | 9 |

Total domestic-stock APIs found: 205

## Practical implementation priority

1. Read-only monitoring first: 시세, 종목정보, 순위정보, 기관/외국인, 대차거래, 공매도, 업종, 테마, ETF, 차트, 실시간시세, 조건검색.
2. Account/order modules are available but should stay gated: 계좌 조회 can be useful for portfolio/risk; 주문/신용주문 should not be invoked unless explicitly requested.
3. For 수급 매매 agent, most valuable blocks are: /api/dostk/rkinfo, /api/dostk/mrkcond, /api/dostk/stkinfo, /api/dostk/frgnistt, /api/dostk/slb, /api/dostk/shsa, /api/dostk/sect, /api/dostk/thme, /api/dostk/chart, /api/dostk/websocket.

## 계좌 (08) — /api/dostk/acnt — 33 APIs

- ka00001 계좌번호조회
- ka01690 일별잔고수익률
- ka10072 일자별종목별실현손익요청_일자
- ka10073 일자별종목별실현손익요청_기간
- ka10074 일자별실현손익요청
- ka10075 미체결요청
- ka10076 체결요청
- ka10077 당일실현손익상세요청
- ka10085 계좌수익률요청
- ka10088 미체결 분할주문 상세
- ka10170 당일매매일지요청
- kt00001 예수금상세현황요청
- kt00002 일별추정예탁자산현황요청
- kt00003 추정자산조회요청
- kt00004 계좌평가현황요청
- kt00005 체결잔고요청
- kt00007 계좌별주문체결내역상세요청
- kt00008 계좌별익일결제예정내역요청
- kt00009 계좌별주문체결현황요청
- kt00010 주문인출가능금액요청
- kt00011 증거금율별주문가능수량조회요청
- kt00012 신용보증금율별주문가능수량조회요청
- kt00013 증거금세부내역조회요청
- kt00015 위탁종합거래내역요청
- kt00016 일별계좌수익률상세현황요청
- kt00017 계좌별당일현황요청
- kt00018 계좌평가잔고내역요청
- kt50020 금현물 잔고확인
- kt50021 금현물 예수금
- kt50030 금현물 주문체결전체조회
- kt50031 금현물 주문체결조회
- kt50032 금현물 거래내역조회
- kt50075 금현물 미체결조회

## 공매도 (17) — /api/dostk/shsa — 1 APIs

- ka10014 공매도추이요청

## 기관/외국인 (03) — /api/dostk/frgnistt — 4 APIs

- ka10008 주식외국인종목별매매동향
- ka10009 주식기관요청
- ka10131 기관외국인연속매매현황요청
- ka52301 금현물투자자현황

## 대차거래 (12) — /api/dostk/slb — 4 APIs

- ka10068 대차거래추이요청
- ka10069 대차거래상위10종목요청
- ka20068 대차거래추이요청(종목별)
- ka90012 대차거래내역요청

## 순위정보 (05) — /api/dostk/rkinfo — 23 APIs

- ka10020 호가잔량상위요청
- ka10021 호가잔량급증요청
- ka10022 잔량율급증요청
- ka10023 거래량급증요청
- ka10027 전일대비등락률상위요청
- ka10029 예상체결등락률상위요청
- ka10030 당일거래량상위요청
- ka10031 전일거래량상위요청
- ka10032 거래대금상위요청
- ka10033 신용비율상위요청
- ka10034 외인기간별매매상위요청
- ka10035 외인연속순매매상위요청
- ka10036 외인한도소진율증가상위
- ka10037 외국계창구매매상위요청
- ka10038 종목별증권사순위요청
- ka10039 증권사별매매상위요청
- ka10040 당일주요거래원요청
- ka10042 순매수거래원순위요청
- ka10053 당일상위이탈원요청
- ka10062 동일순매매순위요청
- ka10065 장중투자자별매매상위요청
- ka10098 시간외단일가등락율순위요청
- ka90009 외국인기관매매상위요청

## 시세 (02) — /api/dostk/mrkcond — 25 APIs

- ka10004 주식호가요청
- ka10005 주식일주월시분요청
- ka10006 주식시분요청
- ka10007 시세표성정보요청
- ka10011 신주인수권전체시세요청
- ka10044 일별기관매매종목요청
- ka10045 종목별기관매매추이요청
- ka10046 체결강도추이시간별요청
- ka10047 체결강도추이일별요청
- ka10063 장중투자자별매매요청
- ka10066 장마감후투자자별매매요청
- ka10078 증권사별종목매매동향요청
- ka10086 일별주가요청
- ka10087 시간외단일가요청
- ka50010 금현물체결추이
- ka50012 금현물일별추이
- ka50087 금현물예상체결
- ka50100 금현물 시세정보
- ka50101 금현물 호가
- ka90005 프로그램매매추이요청 시간대별
- ka90006 프로그램매매차익잔고추이요청
- ka90007 프로그램매매누적추이요청
- ka90008 종목시간별프로그램매매추이요청
- ka90010 프로그램매매추이요청 일자별
- ka90013 종목일별프로그램매매추이요청

## 신용주문 (16) — /api/dostk/crdordr — 4 APIs

- kt10006 신용 매수주문
- kt10007 신용 매도주문
- kt10008 신용 정정주문
- kt10009 신용 취소주문

## 실시간시세 (14) — /api/dostk/websocket — 19 APIs

- 00 주문체결
- 04 잔고
- 0A 주식기세
- 0B 주식체결
- 0C 주식우선호가
- 0D 주식호가잔량
- 0E 주식시간외호가
- 0F 주식당일거래원
- 0G ETF NAV
- 0H 주식예상체결
- 0I 국제금환산가격
- 0J 업종지수
- 0U 업종등락
- 0g 주식종목정보
- 0m ELW 이론가
- 0s 장시작시간
- 0u ELW 지표
- 0w 종목프로그램매매
- 1h VI발동/해제

## 업종 (04) — /api/dostk/sect — 6 APIs

- ka10010 업종프로그램요청
- ka10051 업종별투자자순매수요청
- ka20001 업종현재가요청
- ka20002 업종별주가요청
- ka20003 전업종지수요청
- ka20009 업종현재가일별요청

## 조건검색 (15) — /api/dostk/websocket — 4 APIs

- ka10171 조건검색 목록조회
- ka10172 조건검색 요청 일반
- ka10173 조건검색 요청 실시간
- ka10174 조건검색 실시간 해제

## 종목정보 (01) — /api/dostk/stkinfo — 31 APIs

- ka00198 실시간종목조회순위
- ka10001 주식기본정보요청
- ka10002 주식거래원요청
- ka10003 체결정보요청
- ka10013 신용매매동향요청
- ka10015 일별거래상세요청
- ka10016 신고저가요청
- ka10017 상하한가요청
- ka10018 고저가근접요청
- ka10019 가격급등락요청
- ka10024 거래량갱신요청
- ka10025 매물대집중요청
- ka10026 고저PER요청
- ka10028 시가대비등락률요청
- ka10043 거래원매물대분석요청
- ka10052 거래원순간거래량요청
- ka10054 변동성완화장치발동종목요청
- ka10055 당일전일체결량요청
- ka10058 투자자별일별매매종목요청
- ka10059 종목별투자자기관별요청
- ka10061 종목별투자자기관별합계요청
- ka10084 당일전일체결요청
- ka10095 관심종목정보요청
- ka10099 종목정보 리스트
- ka10100 종목정보 조회
- ka10101 업종코드 리스트
- ka10102 회원사 리스트
- ka90003 프로그램순매수상위50요청
- ka90004 종목별프로그램매매현황요청
- kt20016 신용융자 가능종목요청
- kt20017 신용융자 가능문의

## 주문 (13) — /api/dostk/ordr — 8 APIs

- kt10000 주식 매수주문
- kt10001 주식 매도주문
- kt10002 주식 정정주문
- kt10003 주식 취소주문
- kt50000 금현물 매수주문
- kt50001 금현물 매도주문
- kt50002 금현물 정정주문
- kt50003 금현물 취소주문

## 차트 (07) — /api/dostk/chart — 21 APIs

- ka10060 종목별투자자기관별차트요청
- ka10064 장중투자자별매매차트요청
- ka10079 주식틱차트조회요청
- ka10080 주식분봉차트조회요청
- ka10081 주식일봉차트조회요청
- ka10082 주식주봉차트조회요청
- ka10083 주식월봉차트조회요청
- ka10094 주식년봉차트조회요청
- ka20004 업종틱차트조회요청
- ka20005 업종분봉조회요청
- ka20006 업종일봉조회요청
- ka20007 업종주봉조회요청
- ka20008 업종월봉조회요청
- ka20019 업종년봉조회요청
- ka50079 금현물틱차트조회요청
- ka50080 금현물분봉차트조회요청
- ka50081 금현물일봉차트조회요청
- ka50082 금현물주봉차트조회요청
- ka50083 금현물월봉차트조회요청
- ka50091 금현물당일틱차트조회요청
- ka50092 금현물당일분봉차트조회요청

## 테마 (11) — /api/dostk/thme — 2 APIs

- ka90001 테마그룹별요청
- ka90002 테마구성종목요청

## ELW (06) — /api/dostk/elw — 11 APIs

- ka10048 ELW일별민감도지표요청
- ka10050 ELW민감도지표요청
- ka30001 ELW가격급등락요청
- ka30002 거래원별ELW순매매상위요청
- ka30003 ELWLP보유일별추이요청
- ka30004 ELW괴리율요청
- ka30005 ELW조건검색요청
- ka30009 ELW등락율순위요청
- ka30010 ELW잔량순위요청
- ka30011 ELW근접율요청
- ka30012 ELW종목상세정보요청

## ETF (10) — /api/dostk/etf — 9 APIs

- ka40001 ETF수익율요청
- ka40002 ETF종목정보요청
- ka40003 ETF일별추이요청
- ka40004 ETF전체시세요청
- ka40006 ETF시간대별추이요청
- ka40007 ETF시간대별체결요청
- ka40008 ETF일자별체결요청
- ka40009 ETF시간대별체결요청
- ka40010 ETF시간대별추이요청
