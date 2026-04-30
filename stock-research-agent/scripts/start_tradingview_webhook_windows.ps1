# TradingView webhook autostart helper for Windows -> WSL
# Run from PowerShell. This starts the WSL watchdog and keeps the local webhook alive.

$Distro = $env:TRADINGVIEW_WEBHOOK_WSL_DISTRO
$Command = "cd /mnt/d/Agents/stock-research-agent && bash scripts/start_tradingview_webhook_watchdog.sh"

if ([string]::IsNullOrWhiteSpace($Distro)) {
    wsl.exe bash -lc $Command
} else {
    wsl.exe -d $Distro bash -lc $Command
}
