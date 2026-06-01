from __future__ import annotations

import http.client
import importlib.util
import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import ModuleType
from typing import Any


JOB_ID = "test-job"


def load_dashboard_module() -> ModuleType:
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "stock_theme_dashboard.py"
    spec = importlib.util.spec_from_file_location("stock_theme_dashboard", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def make_hermes_home(tmp_path: Path) -> Path:
    home = tmp_path / "hermes"
    output_dir = home / "cron" / "output" / JOB_ID
    output_dir.mkdir(parents=True)

    write_json(home / "cache" / "sector_strength_alert_cache.json", {"text": ""})
    write_json(
        home / "cache" / "stock_alert_delivery_watchdog_state.json",
        {
            "targets": {
                "us_sector": {
                    "healthy": True,
                    "facts": {
                        "deliver": "telegram token should not leak",
                        "chat_id": "123456",
                        "last_run": "1분 전",
                    },
                }
            }
        },
    )
    write_json(
        home / "cron" / "jobs.json",
        {
            "jobs": [
                {
                    "id": JOB_ID,
                    "name": "US stock sector/theme leadership snapshot",
                    "enabled": True,
                    "state": "scheduled",
                    "last_status": "ok",
                    "last_delivery_error": "bot token should not leak",
                    "schedule": {"display": "*/5 9-23 * * 1", "secret": "hidden"},
                    "repeat": {"completed": 7},
                }
            ]
        },
    )
    (output_dir / "2026-06-01_09-00-00.md").write_text(
        "# Cron Job: US sector\n"
        "private scheduler envelope\n"
        "---\n\n"
        "1) Market\n"
        "NVDA leads AI infra.\n\n"
        "2) Risk\n"
        "Watch crowded long exposure.\n",
        encoding="utf-8",
    )
    return home


def request_json(server: ThreadingHTTPServer, path: str) -> tuple[int, dict[str, Any]]:
    host, port = server.server_address
    conn = http.client.HTTPConnection(host, port, timeout=3)
    try:
        conn.request("GET", path)
        response = conn.getresponse()
        body = response.read().decode("utf-8")
        return response.status, json.loads(body)
    finally:
        conn.close()


def request_text(server: ThreadingHTTPServer, path: str) -> tuple[int, str]:
    host, port = server.server_address
    conn = http.client.HTTPConnection(host, port, timeout=3)
    try:
        conn.request("GET", path)
        response = conn.getresponse()
        return response.status, response.read().decode("utf-8")
    finally:
        conn.close()


def start_server(module: ModuleType, data: Any) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", 0), module.make_handler(data))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_dashboard_data_redacts_runtime_status_and_strips_cron_envelope(tmp_path: Path) -> None:
    module = load_dashboard_module()
    data = module.DashboardData(make_hermes_home(tmp_path), JOB_ID)

    status, status_errors = data.status()
    assert status_errors == []
    assert status["healthy"] is True
    assert status["job"]["last_delivery_error"] == "<redacted>"
    assert status["job"]["schedule"]["secret"] == "<redacted>"
    assert status["watchdog_target"]["facts"]["deliver"] == "<redacted>"
    assert status["watchdog_target"]["facts"]["chat_id"] == "<redacted>"

    latest, latest_errors = data.latest()
    assert latest_errors == []
    assert "# Cron Job:" not in latest["text"]
    assert latest["sections"][0]["title"] == "1) Market"
    assert "NVDA leads AI infra" in latest["sections"][0]["body"]


def test_dashboard_server_smoke_serves_terminal_html_and_api(tmp_path: Path) -> None:
    module = load_dashboard_module()
    data = module.DashboardData(make_hermes_home(tmp_path), JOB_ID)
    server = start_server(module, data)
    try:
        html_status, html = request_text(server, "/")
        assert html_status == 200
        assert "<title>Market Terminal</title>" in html
        assert "US Theme Monitor" not in html
        assert "COMMAND COACH" in html
        assert "MCMD" in html
        assert "SCMD" in html
        for test_id in [
            "terminal-app",
            "terminal-header",
            "command-input",
            "language-select",
            "refresh-button",
            "command-coach",
            "function-key-strip",
            "terminal-tab-strip",
            "market-tape",
            "terminal-main",
            "workspace-panel",
            "workspace-detail",
            "strong-leaderboard",
            "weak-board",
            "sidepane",
            "detail-panel",
            "ticker-movers-panel",
            "previous-leaders-panel",
            "event-tape-panel",
            "terminal-footer",
        ]:
            assert f'data-testid="{test_id}"' in html

        api_status, payload = request_json(server, "/api/dashboard?limit=500")
        assert api_status == 200
        assert payload["status"]["job_id"] == JOB_ID
        assert len(payload["history"]) == 1
        assert payload["history"][0]["preview"].startswith("1) Market")

        bad_status, bad_payload = request_json(server, "/api/output?file=../secret.md")
        assert bad_status == 404
        assert bad_payload["error"] == "invalid file name"
    finally:
        server.shutdown()
        server.server_close()


def test_security_endpoint_normalizes_symbols_and_uses_local_cache(tmp_path: Path, monkeypatch: Any) -> None:
    module = load_dashboard_module()
    data = module.DashboardData(make_hermes_home(tmp_path), JOB_ID)
    calls: list[str] = []

    def fake_fetch(symbol: str) -> dict[str, Any]:
        calls.append(symbol)
        return {"symbol": symbol, "sources": ["test"], "errors": []}

    monkeypatch.setattr(module, "fetch_terminal_security_pack", fake_fetch)
    server = start_server(module, data)
    try:
        first_status, first = request_json(server, "/api/security?symbol=nvda!!!")
        assert first_status == 200
        assert first["security"]["symbol"] == "NVDA"
        assert first["security"]["cache"]["hit"] is False

        second_status, second = request_json(server, "/api/security?symbol=NVDA")
        assert second_status == 200
        assert second["security"]["symbol"] == "NVDA"
        assert second["security"]["cache"]["hit"] is True
        assert calls == ["NVDA"]
    finally:
        server.shutdown()
        server.server_close()
