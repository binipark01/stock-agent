# market-terminal-agent / 금융 터미널 에이전트

로컬 브라우저에서 실행하는 미국 주식 중심 금융 터미널 프로토타입입니다. 기존 알림 결과를 보여주는 화면이 아니라, 명령어 중심으로 시장, 종목, 뉴스, 차트, 스크리너, paper 주문, 포트폴리오, 리스크 흐름을 연결하는 워크스테이션을 목표로 합니다.

기본 UI는 [scripts/stock_theme_dashboard.py](scripts/stock_theme_dashboard.py)에 있는 단일 파일 서버/HTML/JS/CSS 프로토타입입니다. 장기적으로는 분리된 웹 앱 구조가 필요하지만, 현재는 빠른 로컬 검증과 기능 탐색을 우선합니다.

## 핵심 방향

- `MCMD` / `시장체인`: 시장 -> 테마 -> 리더 -> 종목 -> paper 실행 -> 리스크 순서로 보는 시장 command chain.
- `SCMD <ticker>` / `종목체인 <ticker>`: 한 종목을 `DES`, `FA`, `EE`, `GP`, `CN`, `DEPTHX`, `TICKET`, `LIVEQ`, `RISK360`, `PMON` 순서로 보는 종목 command chain.
- `WSP MARKET`, `WSP SECURITY <ticker>`, `WSP TRADER`, `WSP RISK`, `WSP RESEARCH`, `WSP DATA`: 멀티 패널 워크스페이스.
- `LIVEQ`, `TPLAYX`, `OMS`, `PORT`, `PMON`, `RISK360`: 로컬 paper 실행과 포트폴리오/리스크 연결.
- `LANG KO`, `LANG EN`: 한국어/영어 UI shell 전환. 명령어와 ticker mnemonic은 영어를 유지합니다.

실제 브로커 주문은 보내지 않습니다. `TICKET`, `ORDER`, `OMS`, `FILL` 흐름은 모두 로컬 paper workflow입니다.

## 빠른 실행

Windows PowerShell:

```powershell
cd D:\Agents\market-terminal-agent
python -m pip install -r requirements.txt
python scripts\stock_theme_dashboard.py --host 127.0.0.1 --port 8898 --open
```

브라우저에서 직접 열기:

```text
http://127.0.0.1:8898
```

WSL에서 Windows 경로를 쓰는 경우:

```bash
cd /mnt/d/Agents/market-terminal-agent
python3 -m pip install --user -r requirements.txt
python3 scripts/stock_theme_dashboard.py --host 127.0.0.1 --port 8898
```

## API

로컬 UI 서버는 Hermes cron/cache 산출물과 provider 보조 데이터를 읽기 전용으로 노출합니다.

```text
GET /api/status
GET /api/dashboard?limit=120
GET /api/latest
GET /api/history?limit=80
GET /api/output?file=<output.md>
GET /api/security?symbol=NVDA
```

민감정보로 보이는 key(`token`, `secret`, `chat_id`, `api_key`, `password`, `deliver` 등)는 응답에서 `<redacted>`로 가립니다.

## 명령 예시

```text
MCMD
시장체인
SCMD DELL
종목체인 NVDA
WSP MARKET
WSP SECURITY DELL
WSP TRADER
LIVEQ
TPLAYX GO
TICKET NVDA
OMS
PORT
PMON
RISK360
EQS MOVE>3 RSI>60
BQL PX>100 MCAP>10B TARGETGAP>0
FIELDS
HELP WSP
LANG KO
LANG EN
```

Bloomberg-style 순서도 일부 정규화됩니다.

```text
DELL US Equity DES
DELL GP
NVDA CN
AAPL US Equity EE
MSFT SEC360
```

## 테스트

주요 smoke:

```powershell
python -m py_compile scripts\stock_theme_dashboard.py
python -m pytest -q tests\test_stock_theme_dashboard_server.py
python -m pytest -q tests\test_us_agent_framework.py
```

`tests/test_stock_theme_dashboard_server.py`는 다음을 확인합니다.

- 터미널 HTML이 로드되고 `COMMAND COACH`, `MCMD`, `SCMD` 진입점이 노출되는지.
- browser smoke에서 쓸 안정 selector(`data-testid`)가 command bar, coach, workspace, leaderboard, side panels, footer에 있는지.
- `/api/dashboard`, `/api/output`, `/api/security`가 기본 응답을 유지하는지.
- Hermes cron envelope가 화면용 text에서 제거되는지.
- runtime status에 secret/chat id/delivery 값이 노출되지 않는지.
- security pack 호출이 ticker 정규화와 로컬 cache를 지키는지.

## 관련 문서

- [DESIGN.md](DESIGN.md): 제품 방향, UX 원칙, 현재 구현 현황, open questions.
- [docs/browser-smoke.md](docs/browser-smoke.md): 실제 브라우저에서 핵심 terminal command를 확인하는 smoke 절차.
- [docs/git-split-staging.md](docs/git-split-staging.md): `D:\Agents` root에서 안전하게 staging할 파일 범위.
- [docs/us-kr-agent-split-plan.md](docs/us-kr-agent-split-plan.md): `stock-research-agent`를 US/KR/terminal 역할로 나누는 계획.
- [docs/stock-alert-runtime.md](docs/stock-alert-runtime.md): Hermes cron, Telegram/Discord alert runtime 정리.

## 운영 주의

- 이 repo에는 Telegram token, webhook secret, Kiwoom key, Toss/SEC credential 같은 비밀값을 넣지 않습니다.
- `data/kiwoom_token*.json`, `*.env`, private config, local cache는 Git 제외 대상입니다.
- 현재 Git 루트는 상위 `D:\Agents`일 수 있으므로 commit 전에는 split/rename 의도와 staging 범위를 반드시 확인합니다.
