# Stock Agent / 주식 투자 보조 에이전트

> A local-first stock research assistant for US-market watchlists, sector/theme strength, market briefings, filings, news, and Telegram/TradingView alert workflows.
>
> 미국주식 중심의 워치리스트, 섹터/테마 강도, 시장 브리핑, 공시/뉴스, Telegram/TradingView 알림 워크플로우를 지원하는 로컬 우선 주식 리서치 보조 에이전트입니다.

## Project / 프로젝트

This repository currently focuses on:

이 저장소의 핵심 프로젝트는 다음입니다:

- [`stock-research-agent`](./stock-research-agent): US-stock-first research and alert agent.
- [`stock-research-agent`](./stock-research-agent): 미국주식 중심 리서치/알림 에이전트.

## What it does / 주요 기능

- Market and watchlist briefings for US stocks.
- 미국주식 시장/워치리스트 브리핑.
- Sector and custom theme strength reports.
- 섹터 및 사용자 정의 테마 강도 리포트.
- Theme rotation interpretation, including internal sub-theme rotation.
- 테마 내부 서브테마 로테이션 해석.
- Yahoo/yfinance quote, history, news, options, fundamentals, earnings, and calendar summaries.
- Yahoo/yfinance 기반 현재가, 히스토리, 뉴스, 옵션, 펀더멘털, 실적, 일정 요약.
- SEC/EDGAR filing summaries for forms such as 8-K, 10-Q, 10-K, and S-3.
- SEC/EDGAR 공시 요약: 8-K, 10-Q, 10-K, S-3 등.
- SaveTicker breaking-news ingestion and ticker/rumor classification.
- SaveTicker 속보 수집 및 티커/루머 분류.
- TradingView webhook to stock-agent to Telegram alert workflow.
- TradingView webhook → stock-agent → Telegram 알림 워크플로우.
- Reddit public sentiment search for ticker/topic checks.
- Reddit 공개 반응 검색으로 종목/테마 소셜 분위기 확인.
- Technical snapshot with trend, RSI, MACD, support/resistance, stop level, and action bias.
- 추세, RSI, MACD, 지지/저항, 손절 기준, action bias 기반 기술적 스냅샷.

## Quick start / 빠른 시작

```bash
cd stock-research-agent
python3 -m pip install --user -r requirements.txt
python3 src/main.py "NVDA랑 TSLA 오늘 체크포인트 정리해줘"
```

WSL path used in the local development environment:

로컬 개발 환경에서 쓰는 WSL 경로:

```bash
cd /mnt/d/Agents/stock-research-agent
python3 src/main.py --mode brief "오늘 뭐 봐야 해?"
python3 src/main.py --mode sector_strength "장중 섹터별 강한 섹터 약한 섹터 알려줘"
python3 src/main.py --mode technical_snapshot "NVDA 차트 기술적 스냅샷 보여줘"
python3 src/main.py --mode sec_filings "NVDA 최근 8-K 10-Q 공시 요약"
python3 src/main.py --mode reddit_search "레딧 NVDA 반응"
```

## Setup / 설치

Clone the repository on the new machine:

새 컴퓨터에서 저장소를 받습니다:

```bash
mkdir -p ~/Agents
cd ~/Agents
git clone https://github.com/binipark01/stock-agent.git
cd stock-agent/stock-research-agent
python3 -m pip install --user -r requirements.txt
python3 src/main.py --mode brief "오늘 뭐 봐야 해?"
```

For WSL with a D: drive:

D 드라이브를 쓰는 WSL 환경이면:

```bash
mkdir -p /mnt/d/Agents
cd /mnt/d/Agents
git clone https://github.com/binipark01/stock-agent.git
cd stock-agent/stock-research-agent
python3 -m pip install --user -r requirements.txt
python3 src/main.py --mode sector_strength "장중 섹터별 강한 섹터 약한 섹터 알려줘"
```

For Windows PowerShell:

Windows PowerShell에서는:

```powershell
cd D:\Agents
git clone https://github.com/binipark01/stock-agent.git
cd stock-agent\stock-research-agent
python -m pip install -r requirements.txt
python src\main.py --mode technical_snapshot "NVDA 차트 기술적 스냅샷 보여줘"
```

Tell Hermes on the new computer:

새 컴퓨터의 Hermes에게 다음처럼 알려주면 됩니다:

```text
Use the stock-research-agent at ~/Agents/stock-agent/stock-research-agent for stock requests.
For WSL use /mnt/d/Agents/stock-agent/stock-research-agent if it exists.
Run brief requests with: python3 src/main.py --mode brief "<request>"
Run sector requests with: python3 src/main.py --mode sector_strength "<request>"
Run chart requests with: python3 src/main.py --mode technical_snapshot "<request>"
```

```text
앞으로 주식 요청은 ~/Agents/stock-agent/stock-research-agent 에 있는 stock-research-agent를 우선 사용해.
WSL에서 /mnt/d/Agents/stock-agent/stock-research-agent 가 있으면 그 경로를 사용해.
브리핑: python3 src/main.py --mode brief "<요청>"
섹터: python3 src/main.py --mode sector_strength "<요청>"
차트: python3 src/main.py --mode technical_snapshot "<요청>"
```

Real Telegram or TradingView secrets are not included in Git. Create a local env file from the example if needed:

Telegram/TradingView 실제 secret은 Git에 포함하지 않습니다. 필요하면 예시 파일로 로컬 env를 만듭니다:

```bash
cp config/tradingview_webhook.env.example config/tradingview_webhook.env
```

## Common modes / 주요 실행 모드

| Mode | English | 한국어 |
|---|---|---|
| `brief` | Market/watchlist briefing | 시장/워치리스트 브리핑 |
| `sector_strength` | Sector and theme strength report | 섹터/테마 강도 리포트 |
| `technical_snapshot` | Chart-style technical summary | 차트형 기술적 요약 |
| `yfinance_pack` | Yahoo/yfinance data pack | Yahoo/yfinance 데이터 팩 |
| `sec_filings` | SEC filing summary | SEC 공시 요약 |
| `topic_hub` | Cached topic/data overview | 캐시된 토픽/데이터 확인 |
| `earnings` | Earnings date check | 실적 일정 확인 |
| `earnings_preview` | Earnings preview pack | 실적 프리뷰 팩 |
| `saveticker_sync` | SaveTicker news ingestion | SaveTicker 뉴스 수집 |
| `reddit_search` | Reddit public sentiment search | Reddit 공개 반응 검색 |
| `toss_sync` | TossInvest public market/news ingestion | 토스증권 공개 시장/뉴스 수집 |

## Repository structure / 구조

```text
stock-research-agent/
  src/
    main.py                  # CLI entrypoint and response orchestration
    request_modes.py         # Request-to-mode routing
    sector_strength.py       # Sector/theme scoring and report building
    sector_theme_config.py   # ETF/theme/sub-theme symbol configuration
    technical_snapshot.py    # RSI/MACD/support/resistance snapshot
    yfinance_data.py         # Yahoo/yfinance data helpers
    sec_filings.py           # SEC/EDGAR helpers
    tradingview_webhook.py   # TradingView payload handling
    telegram_notify.py       # Telegram notification helpers
  scripts/                   # Alert runners and webhook scripts
  tests/                     # unittest test suite
  config/                    # Example config and watchlists
  docs/                      # Notes and integration guides
```

## Testing / 테스트

```bash
cd stock-research-agent
python3 -m py_compile src/main.py src/sector_strength.py src/yfinance_data.py scripts/run_sector_strength_alerts.py
python3 -m unittest discover -s tests -p 'test_*.py'
```

Current verification status after the latest refactor:

최근 리팩터링 이후 검증 상태:

- `116` unit tests passing.
- `116`개 유닛 테스트 통과.
- Core runtime files compile successfully with `py_compile`.
- 주요 런타임 파일 `py_compile` 성공.

## Data sources / 데이터 소스

- Yahoo Finance / yfinance
- SEC EDGAR public data
- SaveTicker public breaking-news pages
- TossInvest public market/news pages
- TradingView webhook payloads
- Local SQLite cache/database

## Safety and disclaimer / 주의사항

This project is an investment research assistant, not a licensed financial advisor. Outputs are for research and decision support only. Always verify live prices, filings, and news before trading.

이 프로젝트는 투자 판단을 보조하는 리서치 도구이며, 투자 자문 서비스가 아닙니다. 실제 매매 전에는 현재가, 공시, 뉴스, 유동성, 리스크를 반드시 직접 재확인해야 합니다.

## Secrets / 민감정보

Real environment files and runtime artifacts are intentionally ignored:

실제 환경변수 파일과 런타임 산출물은 의도적으로 Git에서 제외합니다:

- `.env`, `*.env`, `.env.*`
- local SQLite databases / 로컬 SQLite DB
- logs, pid files, caches / 로그, PID, 캐시
- local tunnel binaries / 로컬 터널 바이너리

Use example files such as `*.env.example` for documentation only.

문서화에는 `*.env.example` 예시 파일만 사용합니다.
