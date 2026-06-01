# US/KR agent split plan

Target:
- /mnt/d/Agents/us-stock-agent: US stock/theme/sector agent.
- /mnt/d/Agents/kr-stock-agent: Korean KRX/Kiwoom flow/theme agent.
- /mnt/d/Agents/orchestrator: central router only.

US bucket: src/us/**, US shims, US-only main/request_modes, sector/theme scripts and tests.
KR bucket: src/kr/**, krx_/kiwoom shims, KR-only main/request_modes, KRX configs/tests.
Secrets not copied: config/kiwoom.env, *appkey*, *secretkey*, tokens, db/cache data.
Cron wrappers should move only after smoke tests pass. Original stock-research-agent remains rollback.
