# TradingView Webhook 연동

목표: TradingView 알림이 터지면 stock-research-agent가 자동으로 종목을 분석한다.

## 1) 서버 실행

```bash
cd /mnt/d/Agents/stock-research-agent
TRADINGVIEW_WEBHOOK_SECRET='원하는비밀키' \
python3 scripts/tradingview_webhook_server.py --host 0.0.0.0 --port 8765
```

헬스체크:

```bash
curl http://localhost:8765/health
```

## 2) TradingView Alert Webhook URL

로컬 테스트:

```text
http://localhost:8765/webhook/tradingview?secret=원하는비밀키
```

외부 TradingView에서 쓰려면 이 URL이 인터넷에서 접근 가능해야 한다.
로컬 PC/WSL이면 cloudflared 또는 ngrok 같은 터널을 붙인다.

예:

```bash
cloudflared tunnel --url http://localhost:8765
```

TradingView에는 cloudflared가 준 https URL 뒤에 `/webhook/tradingview?secret=원하는비밀키`를 붙인다.

## 3) TradingView Alert 메시지 템플릿

TradingView 알림의 Message 칸에 아래 JSON을 넣는다.

```json
{
  "source": "tradingview",
  "symbol": "{{exchange}}:{{ticker}}",
  "price": "{{close}}",
  "time": "{{time}}",
  "timenow": "{{timenow}}",
  "interval": "{{interval}}",
  "alert": "{{alert_name}}"
}
```

조건 예시:
- IREN 44 이탈
- BMNR 22 회복
- NVDA 전고 돌파
- PLTR 20EMA 이탈

## 4) 서버 응답

서버는 다음을 반환한다.

- 정규화 symbol
- trigger price/time/interval
- stock-research-agent brief 결과
- 텔레그램/알림에 바로 넣을 수 있는 message 문자열

## 5) 텔레그램 자동 전송

환경변수 `TRADINGVIEW_WEBHOOK_NOTIFY_COMMAND`를 지정하면 서버가 응답 JSON을 stdin으로 넘긴다.
현재 이 로컬 세팅은 기존 Hermes Telegram 봇 토큰을 재사용하도록 연결할 수 있다. 토큰을 stock-agent 설정에 복사하지 말고 `TELEGRAM_ENV_FILE`로 Hermes `.env`를 읽는다.

`config/tradingview_webhook.env` 예:

```bash
TRADINGVIEW_WEBHOOK_NOTIFY_TIMEOUT=60
TRADINGVIEW_WEBHOOK_NOTIFY_COMMAND='TELEGRAM_ENV_FILE=/mnt/c/Users/PSB/AppData/Local/hermes/.env TELEGRAM_FALLBACK_IPS=149.154.166.110,149.154.167.220 TELEGRAM_PREFER_FALLBACK_IPS=1 TELEGRAM_NOTIFY_TIMEOUT=10 python3 scripts/send_telegram_from_json.py'
```

동작:
- `src/telegram_notify.py`가 webhook response JSON의 `message`를 Telegram `sendMessage`로 전송한다.
- `TELEGRAM_CHAT_ID`가 없으면 Hermes `.env`의 `TELEGRAM_ALLOWED_USERS` 첫 번째 값을 DM chat_id로 사용한다.
- 테스트만 할 때는 `TELEGRAM_NOTIFY_DRY_RUN=1`을 붙이면 실제 전송 없이 payload만 출력한다.
- WSL에서 `api.telegram.org`가 IPv6를 먼저 잡아 `Network is unreachable`이 나면 `TELEGRAM_FALLBACK_IPS`의 IPv4 direct TLS 경로로 재시도한다.
- `TELEGRAM_PREFER_FALLBACK_IPS=1`은 이 WSL 환경처럼 기본 DNS/HTTPS 경로가 느리거나 timeout 나는 경우 IPv4 direct TLS를 먼저 시도해 알림 지연을 줄인다.
- `TRADINGVIEW_WEBHOOK_NOTIFY_TIMEOUT`은 서버가 notify command를 기다리는 시간이다. Telegram fallback이 몇 초 걸릴 수 있으므로 60초 정도로 둔다.

Dry-run 예:

```bash
echo '{"message":"TradingView alert: NVDA"}' | \
TELEGRAM_NOTIFY_DRY_RUN=1 TELEGRAM_CHAT_ID=12345 python3 scripts/send_telegram_from_json.py
```

## 6) 주의

- 이 webhook은 TradingView 현재가 API가 아니다. TradingView 알림 이벤트를 받는 receiver다.
- 현재가/옵션/뉴스/공시는 stock-research-agent가 별도 소스로 확인한다.
- TradingView webhook URL은 HTTPS 공개 URL이어야 실제 TradingView 알림이 도달한다.
- 비밀키는 반드시 설정한다.
