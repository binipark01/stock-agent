# stock-research-agent / 주식 리서치 에이전트

> US-stock-first local research and alert agent for market briefings, sector/theme strength, filings, news, technical snapshots, and Telegram/TradingView workflows.
>
> 미국주식 중심의 로컬 리서치/알림 에이전트입니다. 시장 브리핑, 섹터/테마 강도, 공시, 뉴스, 기술적 스냅샷, Telegram/TradingView 연동을 지원합니다.

## Overview / 개요

`stock-research-agent` turns stock-market requests into structured research payloads and concise trader-style summaries. It is built for local execution, testability, and practical decision support rather than black-box trading automation.

`stock-research-agent`는 주식/시장 관련 요청을 구조화된 리서치 결과와 실전형 요약으로 바꿔주는 로컬 실행 에이전트입니다. 자동매매 블랙박스가 아니라, 판단 보조와 검증 가능한 리서치 워크플로우를 목표로 합니다.

## Features / 기능

- US-stock watchlist briefing and symbol review.
- 미국주식 워치리스트 브리핑 및 종목 리뷰.
- Sector, ETF, custom theme, and sub-theme strength reports.
- 섹터, ETF, 사용자 정의 테마, 서브테마 강도 리포트.
- Internal rotation alerts when strong and weak sub-themes diverge.
- 같은 상위 테마 안에서 강한 서브테마와 약한 서브테마가 갈릴 때 내부 로테이션 알림.
- Yahoo chart/yfinance quote and history helpers.
- Yahoo chart/yfinance 기반 현재가 및 히스토리 보조 수집.
- Technical snapshot: trend, RSI, MACD, support/resistance, stop level, action bias.
- 기술적 스냅샷: 추세, RSI, MACD, 지지/저항, 손절 기준, action bias.
- SEC/EDGAR filing summaries for 8-K, 10-Q, 10-K, S-3 and related forms.
- SEC/EDGAR 공시 요약: 8-K, 10-Q, 10-K, S-3 등.
- TopicHub/DataHub-lite cache view for quote/news/filing/options/social/earnings topics.
- quote/news/filing/options/social/earnings 토픽을 보는 TopicHub/DataHub-lite 캐시 뷰.
- SaveTicker breaking-news ingestion and rumor/ticker classification.
- SaveTicker 속보 수집 및 루머/티커 분류.
- TossInvest public US index/news ingestion.
- 토스증권 공개 미국지수/미국뉴스 수집.
- TradingView webhook server and Telegram notification helpers.
- TradingView webhook 서버 및 Telegram 알림 보조 기능.

## Quick start / 빠른 시작

```bash
cd /mnt/d/Agents/stock-research-agent
python3 -m pip install --user -r requirements.txt
python3 src/main.py "NVDA랑 TSLA 오늘 체크포인트 정리해줘"
```

If your Python environment is externally managed in WSL, use:

WSL에서 Python 환경이 externally managed라면:

```bash
python3 -m pip install --user --break-system-packages -r requirements.txt
```

## Use from another computer or Hermes / 다른 컴퓨터·Hermes에서 사용

Clone this repository on the target computer and enter the agent folder:

대상 컴퓨터에서 저장소를 clone한 뒤 에이전트 폴더로 들어갑니다:

```bash
mkdir -p ~/Agents
cd ~/Agents
git clone https://github.com/binipark01/stock-agent.git
cd stock-agent/stock-research-agent
python3 -m pip install --user -r requirements.txt
python3 src/main.py --mode brief "오늘 뭐 봐야 해?"
```

WSL with D: drive:

D 드라이브를 쓰는 WSL:

```bash
mkdir -p /mnt/d/Agents
cd /mnt/d/Agents
git clone https://github.com/binipark01/stock-agent.git
cd stock-agent/stock-research-agent
python3 -m pip install --user -r requirements.txt
python3 src/main.py --mode sector_strength "장중 섹터별 강한 섹터 약한 섹터 알려줘"
```

Windows PowerShell:

```powershell
cd D:\Agents
git clone https://github.com/binipark01/stock-agent.git
cd stock-agent\stock-research-agent
python -m pip install -r requirements.txt
python src\main.py --mode technical_snapshot "NVDA 차트 기술적 스냅샷 보여줘"
```

To make another Hermes use this agent, tell it once:

다른 Hermes가 이 에이전트를 쓰게 하려면 한 번 이렇게 알려주면 됩니다:

```text
Use the local stock-research-agent for stock requests.
Preferred paths:
- WSL: /mnt/d/Agents/stock-agent/stock-research-agent
- Linux/macOS fallback: ~/Agents/stock-agent/stock-research-agent
- Windows: D:\Agents\stock-agent\stock-research-agent
Commands:
- Brief: python3 src/main.py --mode brief "<request>"
- Sector/theme: python3 src/main.py --mode sector_strength "<request>"
- Chart: python3 src/main.py --mode technical_snapshot "<request>"
- Filings: python3 src/main.py --mode sec_filings "<request>"
```

```text
앞으로 주식 요청은 로컬 stock-research-agent를 우선 사용해.
우선 경로:
- WSL: /mnt/d/Agents/stock-agent/stock-research-agent
- Linux/macOS 대체: ~/Agents/stock-agent/stock-research-agent
- Windows: D:\Agents\stock-agent\stock-research-agent
명령:
- 브리핑: python3 src/main.py --mode brief "<요청>"
- 섹터/테마: python3 src/main.py --mode sector_strength "<요청>"
- 차트: python3 src/main.py --mode technical_snapshot "<요청>"
- 공시: python3 src/main.py --mode sec_filings "<요청>"
```

Ask that Hermes to save the rule to memory or as a skill if you want it to reuse this automatically.

이 규칙을 계속 재사용하려면 해당 Hermes에게 memory 또는 skill로 저장하라고 요청하세요.

Telegram/TradingView secrets are not committed. Create a local env file only on the target machine:

Telegram/TradingView secret은 커밋하지 않습니다. 대상 컴퓨터에서만 로컬 env 파일을 만드세요:

```bash
cp config/tradingview_webhook.env.example config/tradingview_webhook.env
```

Then fill in local values such as webhook secret, Telegram bot token, and chat id.

이후 webhook secret, Telegram bot token, chat id 같은 로컬 값을 채웁니다.

## Example commands / 실행 예시

```bash
# Watchlist or symbol briefing / 워치리스트 또는 종목 브리핑
python3 src/main.py --mode brief "오늘 뭐 봐야 해?"
python3 src/main.py --mode brief "NVDA MSFT 장전 브리핑 만들어줘"

# Sector/theme strength / 섹터·테마 강도
python3 src/main.py --mode sector_strength "장중 섹터별 강한 섹터 약한 섹터 알려줘"

# Technical snapshot / 기술적 스냅샷
python3 src/main.py --mode technical_snapshot "NVDA 차트 기술적 스냅샷 보여줘"

# Data packs / 데이터 팩
python3 src/main.py --mode yfinance_pack "NVDA yfinance 싹 가져와"
python3 src/main.py --mode sec_filings "NVDA 최근 8-K 10-Q 공시 요약"
python3 src/main.py --mode topic_hub "NVDA topic hub 보여줘"

# Ingestion / 수집
python3 src/main.py --mode ingest "NVDA MSFT AMZN 데이터 수집"
python3 src/main.py --mode saveticker_sync "SaveTicker 미국주 속보 수집"
python3 src/main.py --mode toss_sync "토스 미국지수 뉴스 수집"

# JSON payload / JSON 요청
python3 src/main.py --json '{"mode":"brief","symbols":["NVDA","MSFT","AMZN"],"portfolio":["NVDA"],"request":"미국장 브리핑 만들어줘"}'
```

## Modes / 모드

| Mode | English | 한국어 |
|---|---|---|
| `brief` | Market/watchlist briefing | 시장/워치리스트 브리핑 |
| `symbol_review` | Single or multi-symbol review | 단일/복수 종목 리뷰 |
| `sector_strength` | Sector/theme strength and rotation | 섹터/테마 강도 및 로테이션 |
| `technical_snapshot` | Technical indicator snapshot | 기술적 지표 스냅샷 |
| `why_symbol` | Explain why a symbol matters | 종목을 봐야 하는 이유 |
| `compare` | Compare symbols or candidates | 종목/후보 비교 |
| `what_changed` | Recent change summary | 최근 변화 요약 |
| `overnight_recap` | Overnight recap | 야간/장전 요약 |
| `portfolio_guard` | Portfolio risk/thesis guard | 포트폴리오 리스크/논리 점검 |
| `yfinance_pack` | yfinance quote/options/fundamentals/news pack | yfinance 종합 데이터 팩 |
| `sec_filings` | SEC/EDGAR filing summary | SEC/EDGAR 공시 요약 |
| `topic_hub` | Cached topic overview | 캐시된 토픽 개요 |
| `earnings` | Earnings date lookup | 실적 일정 확인 |
| `earnings_preview` | Earnings preview pack | 실적 프리뷰 팩 |
| `saveticker_sync` | SaveTicker ingestion | SaveTicker 수집 |
| `saveticker_breaking` | Important breaking-news summary | 중요 속보 요약 |
| `toss_sync` | TossInvest public data ingestion | 토스증권 공개 데이터 수집 |
| `social_search` | Threads seed-account search | Threads seed 계정 검색 |

## Project structure / 프로젝트 구조

```text
stock-research-agent/
  src/
    main.py                  # CLI entrypoint and response orchestration
    request_modes.py         # Request-to-mode routing
    sector_strength.py       # Sector/theme scoring and report building
    sector_theme_config.py   # ETF/theme/sub-theme symbol configuration
    technical_snapshot.py    # RSI/MACD/support/resistance snapshot
    yfinance_data.py         # Yahoo/yfinance quote and data helpers
    market_data.py           # Price/news/earnings helpers
    sec_filings.py           # SEC/EDGAR public filing helpers
    topic_hub.py             # DataHub-lite topic/cache view
    saveticker_data.py       # SaveTicker ingestion and scoring
    tossinvest_data.py       # TossInvest public data helpers
    tradingview_webhook.py   # TradingView alert payload handling
    telegram_notify.py       # Telegram notification helper
  scripts/
    run_sector_strength_alerts.py
    tradingview_webhook_server.py
    start_tradingview_webhook.sh
    stop_tradingview_webhook.sh
  tests/
    test_*.py
  config/
    watchlist.json
    tradingview_webhook.env.example
  docs/
    tradingview-webhook.md
    REFERENCE_REPOS.md
```

## Testing / 테스트

```bash
cd /mnt/d/Agents/stock-research-agent
python3 -m py_compile src/main.py src/sector_strength.py src/yfinance_data.py scripts/run_sector_strength_alerts.py
python3 -m unittest discover -s tests -p 'test_*.py'
```

Latest local verification:

최근 로컬 검증:

- `116` unit tests passed.
- `116`개 유닛 테스트 통과.
- Key runtime modules compiled successfully.
- 주요 런타임 모듈 컴파일 성공.

## Quote and market-data notes / 현재가·시장데이터 기준

- Premarket and intraday alerts prefer Yahoo chart data with 1-minute bars where available.
- 프리장/장중 알림은 가능한 경우 Yahoo chart 1분봉 데이터를 우선 사용합니다.
- Regular-session percent changes should be interpreted against the prior regular close, not against a moving current price baseline.
- 정규장 등락률은 움직이는 현재가 기준이 아니라 전일 정규장 종가 대비로 해석해야 합니다.
- Yahoo/yfinance can rate-limit or return stale/mixed fields, so outputs should be treated as research aids and cross-checked before trading.
- Yahoo/yfinance는 rate limit 또는 stale/mixed field 문제가 있을 수 있으므로 실제 매매 전 교차검증이 필요합니다.

## TradingView and Telegram / TradingView·Telegram 연동

TradingView alerts can be sent to the local webhook server and then formatted into Telegram messages.

TradingView 알림은 로컬 webhook 서버로 받고, stock-agent에서 해석한 뒤 Telegram 메시지로 전송할 수 있습니다.

See:

참고:

- [`docs/tradingview-webhook.md`](docs/tradingview-webhook.md)
- `config/tradingview_webhook.env.example`

## Security / 보안

Do not commit real tokens, secrets, webhook keys, local databases, or logs.

실제 토큰, secret, webhook key, 로컬 DB, 로그는 커밋하지 않습니다.

Ignored runtime files include:

Git에서 제외되는 런타임 파일 예시:

- `.env`, `*.env`, `.env.*`
- `data/*.db`
- `logs/`
- `__pycache__/`, `*.pyc`
- local tunnel binaries such as `tools/cloudflared`

## Disclaimer / 면책

This repository is for investment research and decision support only. It does not provide financial advice and does not guarantee trading performance. Always verify live prices, filings, news, liquidity, and risk before making trades.

이 저장소는 투자 리서치와 의사결정 보조 목적입니다. 투자 자문이 아니며 수익을 보장하지 않습니다. 매매 전 현재가, 공시, 뉴스, 유동성, 리스크를 반드시 직접 확인해야 합니다.
