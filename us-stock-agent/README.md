# US Stock Agent

Dedicated US stock agent. Runs standalone from this repository; no source monorepo checkout is required at runtime.

## UI

Run the local web UI:

```bash
python scripts/ui_server.py --host 127.0.0.1 --port 8877
```

Windows:

```powershell
.\scripts\start_ui_windows.ps1
```

General chat messages use the same Codex/OMX LLM path as the Discord agent by default:

```powershell
$env:US_STOCK_AGENT_LLM_PROVIDER="codex"
```

The Codex/OMX provider reads model settings in this order: `OMX_DEFAULT_FRONTIER_MODEL`,
`~/.codex/.omx-config.json`, then `~/.codex/config.toml`.
Stock requests such as `NVDA 체크해줘` still use the local stock agent.
