# TradingView webhook autostart helper for Windows -> WSL
# Run from PowerShell. This starts the WSL watchdog and keeps the local webhook alive.

$Distro = $env:TRADINGVIEW_WEBHOOK_WSL_DISTRO
$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$Drive = $RepoRoot.Substring(0, 1).ToLowerInvariant()
$Rest = $RepoRoot.Substring(2).Replace("\", "/")
$WslRepoRoot = "/mnt/$Drive$Rest"
$Command = "cd '$WslRepoRoot' && bash scripts/start_tradingview_webhook_watchdog.sh"

if ([string]::IsNullOrWhiteSpace($Distro)) {
    wsl.exe bash -lc $Command
} else {
    wsl.exe -d $Distro bash -lc $Command
}
