# Stock Alert Runtime

이 문서는 현재 로컬 PC에서 돌아가는 국장/미장 텔레그램 알림 구조와 수정 위치를 정리한다.
토큰, 채팅방 ID, API 키 같은 비밀값은 저장하지 않는다.

## 현재 유지하는 구조

당장은 Hermes 구조를 유지한다.

```text
Hermes gateway
→ Hermes 내부 cron
→ 알림 스크립트 실행
→ Telegram 전송

Windows Task Scheduler
→ stock_alert_delivery_watchdog.py
→ 알림/게이트웨이 상태 점검
```

Hermes를 제거하고 `Windows Task Scheduler → pythonw.exe → Telegram Bot API 직접 전송` 구조로 단순화할 수는 있지만, 현재는 기존 Hermes 운영 구조를 유지한다.

## Windows 예약작업

현재 Windows 예약작업에 직접 등록된 알림 관련 작업은 하나다.

```text
작업명: HermesStockAlertDeliveryWatchdog
실행: D:\Workspace\Hermes\venv\Scripts\pythonw.exe
스크립트: C:\Users\PSB\AppData\Local\hermes\scripts\stock_alert_delivery_watchdog.py
주기: 24시간 30분마다
표시: Hidden=True, pythonw.exe 사용으로 콘솔창 안 뜸
역할: 미장/국장 알림 출력, 전송 로그, Hermes gateway 상태 점검 및 필요 시 gateway 재시작
```

확인:

```powershell
Get-ScheduledTask -TaskName HermesStockAlertDeliveryWatchdog |
  Select-Object TaskName,State,Settings,Actions,Triggers

Get-ScheduledTask -TaskName HermesStockAlertDeliveryWatchdog |
  Get-ScheduledTaskInfo
```

주기 변경 예시:

```powershell
$taskName = "HermesStockAlertDeliveryWatchdog"
$pythonw = "D:\Workspace\Hermes\venv\Scripts\pythonw.exe"
$script = "C:\Users\PSB\AppData\Local\hermes\scripts\stock_alert_delivery_watchdog.py"
$tr = "`"$pythonw`" -X utf8 `"$script`""

# 30분마다, 창 안 뜨게 실행
schtasks.exe /Create /TN $taskName /SC MINUTE /MO 30 /TR $tr /F

$task = Get-ScheduledTask -TaskName $taskName
$settings = $task.Settings
$settings.Hidden = $true
$settings.StartWhenAvailable = $false
$settings.MultipleInstances = "IgnoreNew"
Set-ScheduledTask -TaskName $taskName -Settings $settings
```

## Hermes gateway

텔레그램 전송 gateway는 별도 상주 프로세스로 유지된다.

```text
감시 스크립트: C:\Users\PSB\hermes_gateway_watchdog.ps1
gateway 실행: D:\Workspace\Hermes\venv\Scripts\python.exe -m hermes_cli.main gateway run -v
상태 파일: C:\Users\PSB\AppData\Local\hermes\gateway_state.json
로그: C:\Users\PSB\AppData\Local\hermes\logs\
```

로그인 시 자동 시작 항목:

```text
C:\Users\PSB\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\Hermes Gateway Autostart.cmd
```

주의:

- 이 gateway를 끄면 Hermes 내부 cron의 텔레그램 전송이 막힐 수 있다.
- `HermesStockAlertDeliveryWatchdog`는 gateway가 비정상이면 재시작을 시도한다.

## Hermes 내부 cron

Hermes 내부 cron 설정 파일:

```text
C:\Users\PSB\AppData\Local\hermes\cron\jobs.json
```

현재 주요 작업:

```text
미장 알림
- 이름: US stock sector/theme leadership snapshot every 5 minutes
- 주기: every 5m
- 스크립트: sector_strength_alert_text.py
- 전송: telegram + Discord
- 주말 차단: live script에서 토요일 09:00 KST 이후 ~ 월요일 09:00 KST 전까지 Discord 전송을 skip한다.

국장 정규장
- 이름: KRX 수급 알림 - 정규장 (script direct)
- 주기: 평일 08:00~15:55, 5분마다
- 스크립트: krx_regular_alert_text.py
- 전송: telegram + Discord

국장 장후
- 이름: KRX 수급 알림 - 장후/SOR (script direct)
- 주기: 평일 16:00~19:55, 5분마다
- 스크립트: krx_afterhours_alert_text.py
- 전송: telegram + Discord

국장 20:00 final
- 이름: KRX 수급 알림 - 장후/SOR 20:00 final (script direct)
- 주기: 평일 20:00 1회
- 스크립트: krx_afterhours_alert_text.py
- 전송: telegram + Discord

KRX 내부 watchdog
- 이름: KRX 알림 전송 watchdog
- 주기: 평일 08:07~20:07, 매시 7분
- 스크립트: krx_alert_watchdog.py
- 전송: 문제 있을 때만 telegram + Discord
```

## live script 위치

Hermes가 실제 실행하는 스크립트:

```text
C:\Users\PSB\AppData\Local\hermes\scripts\sector_strength_alert_text.py
C:\Users\PSB\AppData\Local\hermes\scripts\krx_regular_alert_text.py
C:\Users\PSB\AppData\Local\hermes\scripts\krx_afterhours_alert_text.py
C:\Users\PSB\AppData\Local\hermes\scripts\krx_alert_watchdog.py
C:\Users\PSB\AppData\Local\hermes\scripts\stock_alert_delivery_watchdog.py
```

repo 쪽 기준 파일:

```text
D:\Agents\stock-research-agent\scripts\krx_alerts\regular.py
D:\Agents\stock-research-agent\scripts\krx_alerts\afterhours.py
D:\Agents\stock-research-agent\scripts\krx_alerts\watchdog.py
```

국장 알림 로직을 수정할 때는 repo 파일을 먼저 수정하고 검증한 뒤, Hermes live script에 동기화한다.

Discord 전송 공통 코드:

```text
별도 DiscordAgent repo/discord_notify.py
별도 DiscordAgent repo/.env
```

Telegram 전송은 그대로 유지하고, stock repo code에서는 DiscordAgent를 import하지 않는다. cron/scheduler가 `STOCK_ALERT_NOTIFY_COMMAND` 같은 외부 명령 env로만 DiscordAgent에 연결한다.
Discord 값은 DiscordAgent 쪽 `.env`만 사용한다.

## 빠른 점검 명령

창이 뜨는 예전 예약작업이 남아있는지 확인:

```powershell
Get-ScheduledTask | Where-Object {
  ($_.Actions | ForEach-Object { $_.Execute + " " + $_.Arguments }) -match "stock_alert_delivery_watchdog\.py" -and
  ($_.Actions | ForEach-Object { $_.Execute }) -match "python\.exe$"
}
```

현재 알림 관련 상주 프로세스 확인:

```powershell
Get-CimInstance Win32_Process |
  Where-Object {
    $_.CommandLine -match "stock_alert_delivery_watchdog|krx_alert_watchdog|hermes_gateway_watchdog|hermes_cli\.main gateway|krx_regular_alert|krx_afterhours_alert|sector_strength_alert"
  } |
  Select-Object ProcessId,Name,ParentProcessId,CreationDate,CommandLine
```

Hermes 내부 cron 목록 확인:

```powershell
$jobsPath = "$env:LOCALAPPDATA\hermes\cron\jobs.json"
Get-Content $jobsPath -Raw -Encoding UTF8 | ConvertFrom-Json
```

## 운영 원칙

- 비밀값은 repo에 넣지 않는다.
- 채팅방 ID, bot token, API key는 문서/커밋에 남기지 않는다.
- Windows 예약작업은 콘솔창 방지를 위해 `pythonw.exe`를 사용한다.
- Hermes 내부 cron은 gateway 안에서 실행되므로 별도 cmd창을 띄우는 구조가 아니다.
- 알림 구조를 단순화하려면 나중에 Hermes 내부 cron을 Windows 예약작업 직접 실행 방식으로 이관한다.

## Discord 운영

Discord는 서버 하나 안에 목적별 채널을 나눠 운영한다.

현재 확정:

```text
국장 cron 알림 채널
미장 cron 알림 채널
```

추가 채널:

```text
agent 대화 채널
watchdog 전용 채널
test 채널
```

Discord 전용 로컬 환경 파일에 저장할 키:

```text
별도 DiscordAgent repo/.env

DISCORD_GUILD_ID=
DISCORD_KRX_CHANNEL_ID=
DISCORD_US_CHANNEL_ID=
DISCORD_WATCHDOG_CHANNEL_ID=
DISCORD_AGENT_CHANNEL_ID=
DISCORD_KR_AGENT_CHANNEL_ID=
DISCORD_US_AGENT_CHANNEL_ID=
DISCORD_BOT_TOKEN=
```

Hermes `.env`에는 Discord 값을 두지 않고, DiscordAgent 쪽 `.env`에서만 관리한다.
안전한 예시는 DiscordAgent 쪽 `.env.example`에 둔다.

운영 원칙:

- 국장/미장 cron 알림 채널과 agent 대화 채널은 분리한다.
- 알림만 보내는 기능은 bot token 기반 REST 전송으로 시작한다.
- `/수급`, `/국장`, `/미장`, `/agent` 같은 대화형 기능은 별도 Discord bot 상주 프로세스로 붙인다.
- Discord token은 절대 repo, 문서, 로그, 커밋에 남기지 않는다.
