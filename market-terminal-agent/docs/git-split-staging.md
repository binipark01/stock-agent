# Git Split Staging

현재 `D:\Agents`가 Git root이고 `market-terminal-agent`는 그 아래 새 agent 폴더로 작업 중이다. root에서 `git add .`를 실행하면 다른 agent 폴더, runtime log, split 중인 삭제분이 한 번에 섞일 수 있으므로 staging 범위를 명시한다.

## 현재 terminal 작업 단위

이번 `market-terminal-agent` 쪽 작업을 별도 단위로 올릴 때 우선 포함할 파일:

```powershell
cd D:\Agents
git add market-terminal-agent\.gitignore
git add market-terminal-agent\AGENT.md
git add market-terminal-agent\README.md
git add market-terminal-agent\DESIGN.md
git add market-terminal-agent\docs\browser-smoke.md
git add market-terminal-agent\scripts\stock_theme_dashboard.py
git add market-terminal-agent\tests\test_stock_theme_dashboard_server.py
```

이 단위의 검증:

```powershell
cd D:\Agents\market-terminal-agent
python -m py_compile scripts\stock_theme_dashboard.py
python -m pytest -q tests\test_stock_theme_dashboard_server.py tests\test_us_agent_framework.py
```

## 포함하지 않을 것

아래는 runtime/local artifact라 staging하지 않는다.

```text
market-terminal-agent\.venv\
market-terminal-agent\.pytest_cache\
market-terminal-agent\logs\
market-terminal-agent\__pycache__\
market-terminal-agent\data\probes\
market-terminal-agent\data\kiwoom_token*.json
market-terminal-agent\*.env
market-terminal-agent\config\kiwoom.env
market-terminal-agent\tools\cloudflared*
market-terminal-agent\tools\bootstrap\get-pip.py
market-terminal-agent\scripts\krx_alerts\*.last.txt
market-terminal-agent\scripts\krx_alerts\*.issue_candidates.json
```

`.gitignore`에는 local server log, probe output, local bootstrap/binary, alert runtime marker를 추가했다. 서버 smoke와 probe 중 생기는 산출물이 source split에 섞이지 않게 하기 위함이다.

## stock-research-agent 삭제분

현재 root status에는 기존 `stock-research-agent`가 삭제된 것으로 보인다. 이 삭제분은 `us-stock-agent`, `kr-stock-agent`, `market-terminal-agent` split이 의도한 최종 상태인지 확인한 뒤 별도 commit으로 다루는 편이 안전하다.

삭제분을 확정할 때만:

```powershell
cd D:\Agents
git add -A stock-research-agent
```

그 전에는 `market-terminal-agent` 작업과 섞어 stage하지 않는다.

## sibling agent 폴더

현재 root에는 `us-stock-agent`, `kr-stock-agent`, `orchestrator`, `DiscordAgent` 등 sibling 폴더가 untracked로 보일 수 있다. 각 agent는 별도 작업 단위로 검증하고 stage한다.

`market-terminal-agent` commit에는 필요한 경우가 아니면 sibling 폴더를 포함하지 않는다.
