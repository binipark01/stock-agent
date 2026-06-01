$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
$HostValue = if ($env:US_STOCK_AGENT_UI_HOST) { $env:US_STOCK_AGENT_UI_HOST } else { "127.0.0.1" }
$PortValue = if ($env:US_STOCK_AGENT_UI_PORT) { $env:US_STOCK_AGENT_UI_PORT } else { "8877" }
python scripts/ui_server.py --host $HostValue --port $PortValue
