from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
UI_DIR = ROOT / "ui"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8877
MAX_BODY_BYTES = 1_000_000

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.main import DEFAULT_WATCHLIST_PATH, build_response  # noqa: E402
from src.chat_llm import build_llm_chat_response, should_use_llm_chat  # noqa: E402
from src.watchlists import load_watchlist  # noqa: E402


MODE_OPTIONS: tuple[dict[str, str], ...] = (
    {"value": "auto", "label": "자동"},
    {"value": "brief", "label": "브리프"},
    {"value": "symbol_review", "label": "종목 리뷰"},
    {"value": "portfolio_guard", "label": "포트폴리오"},
    {"value": "sector_strength", "label": "섹터 강약"},
    {"value": "sector_intelligence", "label": "섹터 인텔"},
    {"value": "market_regime", "label": "장 분위기"},
    {"value": "oil_vix", "label": "VIX/원유"},
    {"value": "technical_snapshot", "label": "기술 분석"},
    {"value": "options_flow", "label": "옵션 플로우"},
    {"value": "options_sweep", "label": "옵션 스윕"},
    {"value": "sec_filings", "label": "SEC 공시"},
    {"value": "earnings_preview", "label": "실적 프리뷰"},
    {"value": "yfinance_pack", "label": "YFinance"},
    {"value": "openbb_quote", "label": "OpenBB Quote"},
    {"value": "openbb_history", "label": "OpenBB History"},
    {"value": "social_search", "label": "Social"},
    {"value": "threads_view_scan", "label": "Threads Scan"},
    {"value": "watchlist_scan", "label": "Watchlist"},
    {"value": "compare", "label": "비교"},
    {"value": "what_changed", "label": "변화점"},
    {"value": "overnight_recap", "label": "Overnight"},
    {"value": "why_symbol", "label": "Why"},
)


def _json_bytes(payload: dict[str, Any], status: int = 200) -> tuple[int, bytes]:
    return status, json.dumps(payload, ensure_ascii=False).encode("utf-8")


def _split_symbols(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        raw_items = value
    else:
        raw_items = str(value).replace("\n", ",").replace(" ", ",").split(",")
    symbols: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        symbol = str(item).strip().upper()
        if not symbol or symbol in seen:
            continue
        symbols.append(symbol)
        seen.add(symbol)
    return symbols


def _mode_value(value: Any) -> str | None:
    mode = str(value or "").strip()
    if not mode or mode == "auto":
        return None
    valid_modes = {item["value"] for item in MODE_OPTIONS}
    if mode not in valid_modes:
        raise ValueError(f"unsupported mode: {mode}")
    return mode


def _runtime_context(body: dict[str, Any]) -> dict[str, Any]:
    context = body.get("runtime_context")
    if not isinstance(context, dict):
        context = {}
    else:
        context = dict(context)
    portfolio = _split_symbols(body.get("portfolio"))
    if portfolio:
        context["portfolio"] = portfolio
    return context


def _agent_request_payload(body: dict[str, Any]) -> str:
    request_text = str(body.get("request") or "").strip() or "오늘 미국장 체크포인트 정리해줘"
    payload: dict[str, Any] = {"request": request_text}
    for key in ("symbols", "portfolio", "watchlist"):
        symbols = _split_symbols(body.get(key))
        if symbols:
            payload[key] = symbols
    for key in ("db_path", "watchlist_path"):
        value = body.get(key)
        if isinstance(value, str) and value.strip():
            payload[key] = value.strip()
    return json.dumps(payload, ensure_ascii=False)


def build_api_response(
    body: dict[str, Any],
    *,
    agent_runner: Callable[..., dict[str, Any]] = build_response,
    chat_runner: Callable[..., dict[str, Any]] = build_llm_chat_response,
) -> dict[str, Any]:
    explicit_mode = _mode_value(body.get("mode"))
    request_text = str(body.get("request") or "").strip() or "오늘 미국장 체크포인트 정리해줘"
    if should_use_llm_chat(request_text, explicit_mode=explicit_mode):
        return {"ok": True, "response": chat_runner(request_text, history=body.get("history"))}
    response = agent_runner(
        _agent_request_payload(body),
        runtime_context=_runtime_context(body),
        explicit_mode=explicit_mode,
    )
    return {"ok": True, "response": response}


def build_health_payload() -> dict[str, Any]:
    watchlist_data = load_watchlist(DEFAULT_WATCHLIST_PATH)
    return {
        "agent": "us-stock-agent",
        "status": "ok",
        "modes": list(MODE_OPTIONS),
        "watchlist": watchlist_data.get("watchlist", []),
        "portfolio": watchlist_data.get("portfolio", []),
        "lists": watchlist_data.get("lists", {}),
    }


def _content_type(path: Path) -> str:
    guessed = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    if guessed.startswith("text/") or guessed in {"application/javascript", "application/json"}:
        return f"{guessed}; charset=utf-8"
    return guessed


def _static_path(request_path: str) -> Path | None:
    parsed_path = urlparse(request_path).path
    relative = "index.html" if parsed_path in {"", "/"} else parsed_path.lstrip("/")
    candidate = (UI_DIR / relative).resolve()
    try:
        candidate.relative_to(UI_DIR.resolve())
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    return candidate


class StockAgentUiHandler(BaseHTTPRequestHandler):
    server_version = "StockAgentUi/1.0"

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.end_headers()

    def do_GET(self) -> None:
        parsed_path = urlparse(self.path).path
        if parsed_path == "/api/health":
            self._send_json(build_health_payload())
            return
        static_path = _static_path(self.path)
        if static_path is None:
            self._send_json({"ok": False, "error": "not found"}, status=404)
            return
        self.send_response(200)
        self.send_header("Content-Type", _content_type(static_path))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(static_path.read_bytes())

    def do_POST(self) -> None:
        parsed_path = urlparse(self.path).path
        if parsed_path != "/api/respond":
            self._send_json({"ok": False, "error": "not found"}, status=404)
            return
        try:
            body = self._read_json_body()
            self._send_json(build_api_response(body))
        except ValueError as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:  # pragma: no cover - defensive server boundary
            self._send_json({"ok": False, "error": f"agent error: {exc}"}, status=500)

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"{self.address_string()} - {fmt % args}", flush=True)

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length > MAX_BODY_BYTES:
            raise ValueError("request body too large")
        raw = self.rfile.read(length)
        if not raw:
            return {}
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("JSON object expected")
        return data

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        status, body = _json_bytes(payload, status)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the us-stock-agent web UI")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    server = ThreadingHTTPServer((args.host, args.port), StockAgentUiHandler)
    print(f"US Stock Agent UI: http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping UI server", flush=True)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
