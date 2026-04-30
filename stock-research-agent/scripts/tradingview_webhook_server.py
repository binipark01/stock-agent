#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from src.tradingview_webhook import build_tradingview_webhook_response, parse_tradingview_payload, verify_webhook_secret


def _last_nonempty_line(text: str) -> str:
    for line in reversed((text or "").splitlines()):
        if line.strip():
            return line.strip()
    return ""


def _redact_request_log_message(message: str) -> str:
    return re.sub(r"([?&]secret=)[^\s&\"]+", r"\1***", message)


def run_notify_command(notify_command: str, response: dict, timeout_seconds: int = 30) -> dict:
    """Run notify command and return a log/response-safe status summary."""
    try:
        completed = subprocess.run(
            notify_command,
            input=json.dumps(response, ensure_ascii=False),
            text=True,
            shell=True,
            timeout=timeout_seconds,
            check=False,
            capture_output=True,
        )
    except Exception as exc:
        return {"notify_status": "error", "notify_error": str(exc)}

    if completed.returncode != 0:
        detail = _last_nonempty_line(completed.stderr) or _last_nonempty_line(completed.stdout) or "no detail"
        return {
            "notify_status": "error",
            "notify_error": f"notify command exited {completed.returncode}: {detail}",
        }

    line = _last_nonempty_line(completed.stdout)
    if not line:
        return {"notify_status": "sent"}

    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return {"notify_status": "sent"}

    status = str(payload.get("status") or "sent")
    summary = {"notify_status": status}
    message_id = payload.get("message_id")
    if message_id is not None:
        summary["telegram_message_id"] = message_id
    return summary


def parse_notify_timeout_seconds(value: str | None, default: int = 30) -> int:
    try:
        parsed = int(str(value or "").strip())
    except ValueError:
        return default
    return parsed if parsed > 0 else default


class TradingViewWebhookHandler(BaseHTTPRequestHandler):
    server_version = "stock-research-tradingview-webhook/0.1"

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._send_json(200, {"status": "ok", "service": "tradingview-webhook"})
            return
        self._send_json(404, {"status": "error", "error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path not in {"/webhook/tradingview", "/tradingview"}:
            self._send_json(404, {"status": "error", "error": "not_found"})
            return

        query = parse_qs(parsed.query)
        headers = {key: value for key, value in self.headers.items()}
        secret = getattr(self.server, "webhook_secret", None)
        if not verify_webhook_secret(headers, query, secret):
            self._send_json(401, {"status": "error", "error": "unauthorized"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length < 0 or length > 1_000_000:
            self._send_json(400, {"status": "error", "error": "invalid_content_length"})
            return

        raw_body = self.rfile.read(length).decode("utf-8", errors="replace") if length else ""
        payload = parse_tradingview_payload(raw_body)

        try:
            response = build_tradingview_webhook_response(payload)
        except Exception as exc:  # keep webhook alive even if analysis fails
            self._send_json(500, {"status": "error", "error": str(exc)})
            return

        notify_command = getattr(self.server, "notify_command", None)
        if notify_command:
            timeout_seconds = getattr(self.server, "notify_timeout_seconds", 30)
            response.update(run_notify_command(notify_command, response, timeout_seconds=timeout_seconds))

        print(response["message"], flush=True)
        self._send_json(200, response)

    def log_message(self, fmt: str, *args) -> None:
        message = _redact_request_log_message(fmt % args)
        print(f"{self.address_string()} - {message}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="TradingView webhook receiver for stock-research-agent")
    parser.add_argument("--host", default=os.getenv("TRADINGVIEW_WEBHOOK_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("TRADINGVIEW_WEBHOOK_PORT", "8765")))
    parser.add_argument("--secret", default=os.getenv("TRADINGVIEW_WEBHOOK_SECRET", ""))
    parser.add_argument(
        "--notify-command",
        default=os.getenv("TRADINGVIEW_WEBHOOK_NOTIFY_COMMAND", ""),
        help="optional shell command that receives response JSON on stdin",
    )
    parser.add_argument(
        "--notify-timeout",
        type=int,
        default=parse_notify_timeout_seconds(os.getenv("TRADINGVIEW_WEBHOOK_NOTIFY_TIMEOUT", "30")),
        help="seconds to wait for optional notify command",
    )
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), TradingViewWebhookHandler)
    server.webhook_secret = args.secret or None
    server.notify_command = args.notify_command or None
    server.notify_timeout_seconds = parse_notify_timeout_seconds(str(args.notify_timeout), default=30)
    print(f"TradingView webhook listening on http://{args.host}:{args.port}/webhook/tradingview", flush=True)
    if server.webhook_secret:
        print("Secret auth enabled: pass ?secret=... or X-TradingView-Secret header", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
