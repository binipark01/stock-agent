# Kiwoom KRX data map for stock-research-agent

Purpose: 국장 에이전트가 Kiwoom OpenAPI REST/WebSocket으로 얻을 수 있는 정보와 우선 구현 TR을 정리한다.

## Connection

- REST 운영: `https://api.kiwoom.com`
- REST 모의: `https://mockapi.kiwoom.com` (KRX 지원)
- OAuth: `POST /oauth2/token`
  - body: `grant_type=client_credentials`, `appkey`, `secretkey`
  - response: `token_type`, `token`, `expires_dt`
- REST TR header:
  - `authorization: Bearer {token}`
  - `api-id: {TR_ID}`
  - `cont-yn`, `next-key` for continuation
- WebSocket 운영: `wss://api.kiwoom.com:10000/api/dostk/websocket`
- WebSocket 모의: `wss://mockapi.kiwoom.com:10000/api/dostk/websocket`

## Agent-useful REST TRs

| Area | Endpoint | TR | What the agent can use |
|---|---|---:|---|
| 기본/현재가 | `/api/dostk/stkinfo` | `ka10001` | 종목명, 현재가, 기준가, 전일대비, 등락률, 시총, PER/EPS/ROE/PBR 등 기본 스냅샷 |
| 호가 | `/api/dostk/mrkcond` | `ka10004` | 10호가 매도/매수 가격·잔량, 호가 기준시각 |
| 체결강도 | `/api/dostk/mrkcond` | `ka10046` | 시간별 현재가, 거래량, 누적거래량/거래대금, 체결강도/5분/20분/60분 강도 |
| 체결강도 일별 | `/api/dostk/mrkcond` | `ka10047` | 일별 체결강도 추이 |
| 거래대금 랭킹 | `/api/dostk/rkinfo` | `ka10032` | 거래대금 상위, 현재/이전 순위, 가격, 등락률, 거래량, 거래대금 |
| 장중 투자자별 | `/api/dostk/mrkcond` | `ka10063` | 시장/투자자별 장중 순매수 금액·수량, 매수/매도 금액·수량 |
| 장마감 투자자별 | `/api/dostk/mrkcond` | `ka10066` | 개인, 외국인, 기관, 투신, 보험, 연기금, 국가, 기타법인 등 매매 흐름 |
| 투자자별 일별 종목 | `/api/dostk/stkinfo` | `ka10058` | 특정 종목의 투자자별 일별 매매 추이 |
| 외국인 종목별 | `/api/dostk/frgnistt` | `ka10008` | 외국인 종목별 매매 동향 |
| 기관 종목별 | `/api/dostk/frgnistt` | `ka10009` | 기관 종목별 매매 동향 |
| 기관/외국인 연속 | `/api/dostk/frgnistt` | `ka10131` | 기관/외국인 연속 매수·매도 후보 |
| 프로그램 순매수 랭킹 | `/api/dostk/stkinfo` | `ka90003` | 프로그램 순매수 상위 50, 매도/매수/순매수 금액 |
| 종목별 프로그램 현황 | `/api/dostk/stkinfo` | `ka90004` | 날짜/시장별 프로그램 매수·매도·순매수 현황 |
| 프로그램 시간대별 | `/api/dostk/mrkcond` | `ka90005` | 시장 프로그램 매매 시간대별 추이 |
| 종목 프로그램 시간별 | `/api/dostk/mrkcond` | `ka90008` | 개별종목 시간별 프로그램 매수/매도/순매수 금액·수량 |
| 프로그램 일자별 | `/api/dostk/mrkcond` | `ka90010` | 시장 프로그램 일별 추이 |
| 종목 프로그램 일별 | `/api/dostk/mrkcond` | `ka90013` | 개별종목 일별 프로그램 추이 |
| 업종 현재가 | `/api/dostk/sect` | `ka20001` | 업종/지수 현재가 |
| 업종 일별 | `/api/dostk/sect` | `ka20009` | 업종/지수 일별 흐름 |
| 업종 프로그램 | `/api/dostk/sect` | `ka10010` | 업종 프로그램 매매 |

## Realtime WebSocket types

Registration body:

```json
{
  "trnm": "REG",
  "grp_no": "1",
  "refresh": "1",
  "data": [
    {"item": ["005930", "000660"], "type": ["0B", "0D", "0w"]}
  ]
}
```

| Type | Name | Agent use |
|---|---|---|
| `0B` | 주식체결 | 현재가, 전일대비, 등락률, 거래량, 누적거래량, 누적거래대금, 체결강도, 순간거래대금, 순매수체결량 |
| `0D` | 주식호가잔량 | 10호가, 매도/매수 총잔량, 순매수잔량, 매수비율, 순매도잔량, 매도비율 |
| `0w` | 종목프로그램매매 | 프로그램 매도/매수 수량·금액, 순매수 수량·금액, 증감 |
| `0J` | 업종지수 | 업종/지수 실시간 흐름 |
| `0U` | 업종등락 | 업종 등락 상황 |
| `1h` | VI발동/해제 | 변동성완화장치 이벤트 |

## Output rules for the agent

- Always include `source=kiwoom`, TR/type, and `collected_at`.
- If a row has trade date/time/base time, include it separately from collection time.
- Do not overclaim investor-class data as tick-real-time unless the TR/WebSocket actually provides tick updates.
- Prefer Kiwoom for official KRX monitoring; use Toss/Naver only as fallback/validation and label them as such.
- Keep order/trading APIs out of scope for now; current implementation is read-only monitoring.
