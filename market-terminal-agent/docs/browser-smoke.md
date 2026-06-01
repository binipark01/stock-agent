# Browser Smoke

`market-terminal-agent`의 실제 브라우저 동작을 빠르게 확인하는 절차다. 목적은 화면이 열리는지, 핵심 명령이 workspace를 바꾸는지, console error가 없는지 확인하는 것이다.

## 실행 전

```powershell
cd D:\Agents\market-terminal-agent
python scripts\stock_theme_dashboard.py --host 127.0.0.1 --port 8898
```

브라우저:

```text
http://127.0.0.1:8898/
```

브라우저 title은 `Market Terminal`이어야 한다.

## 안정 selector

Browser smoke는 표시 문구보다 `data-testid`를 우선 사용한다.

```text
terminal-app
terminal-header
command-input
language-select
refresh-button
command-coach
function-key-strip
terminal-tab-strip
market-tape
terminal-main
workspace-panel
workspace-detail
strong-leaderboard
weak-board
sidepane
detail-panel
ticker-movers-panel
previous-leaders-panel
event-tape-panel
terminal-footer
```

## 핵심 명령 smoke

명령 입력창(`data-testid="command-input"`)에 아래 명령을 순서대로 입력하고 Enter를 누른다.

```text
MCMD
WSP MARKET
WSP SECURITY DELL
SCMD DELL
LIVEQ
LANG EN
LANG KO
```

각 명령 후 확인할 것:

- `command-coach`가 현재 명령에 맞는 다음 액션을 보여준다.
- `workspace-detail`이 해당 화면으로 바뀐다. `LANG EN/KO`는 shell language 전환이므로 home/언어 상태 전환만 확인한다.
- `language-select` 값이 `LANG EN` 후 `en`, `LANG KO` 후 `ko`가 된다.
- browser console error가 없어야 한다.

브라우저 입력 자동화가 막히는 경우에는 URL 명령으로 같은 화면 전환을 확인할 수 있다.

```text
http://127.0.0.1:8898/?cmd=MCMD
http://127.0.0.1:8898/?cmd=WSP%20MARKET
http://127.0.0.1:8898/?cmd=WSP%20SECURITY%20DELL
```

URL 명령 smoke에서도 `command-input` 값, `command-coach`, `workspace-detail`, browser title, console error를 확인한다.

## Refresh smoke

`refresh-button`을 누른 뒤 확인한다.

- 버튼 text가 일시적으로 `갱신중` 또는 `REFRESHING`으로 바뀐 뒤 원래 상태로 돌아온다.
- command input 값과 현재 shell language가 유지된다.
- `command-coach`, footer status, market data freshness가 다시 렌더된다.
- console error가 없어야 한다.

## 현재 확인한 결과

2026-06-01 KST 기준으로 다음 조합을 in-app Browser에서 확인했다.

```text
MCMD
WSP MARKET
WSP SECURITY DELL
LIVEQ
LANG EN
LANG KO
REFRESH
```

결과:

- `command-coach`와 `workspace-detail` 정상 전환.
- browser title은 `Market Terminal`이고 기존 `US Theme Monitor` title 문자열은 없음.
- `LANG EN` / `LANG KO` shell language 정상 전환.
- `REFRESH` 후 버튼과 command input 상태 정상.
- `?cmd=MCMD` URL 명령 smoke 정상.
- console error 없음.

## 자동 테스트와 연결

서버/API 쪽 smoke는 pytest로 확인한다.

```powershell
python -m py_compile scripts\stock_theme_dashboard.py
python -m pytest -q tests\test_stock_theme_dashboard_server.py
```

`tests/test_stock_theme_dashboard_server.py`는 위 `data-testid` selector가 HTML에 남아 있는지도 확인한다.
