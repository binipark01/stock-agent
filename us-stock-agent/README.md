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

General chat messages use an OpenAI-compatible chat endpoint when configured:

```powershell
$env:OPENAI_API_KEY="..."
$env:OPENAI_MODEL="gpt-4o-mini"
```

Stock requests such as `NVDA 체크해줘` still use the local stock agent.
