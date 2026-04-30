from __future__ import annotations

from dataclasses import dataclass
import http.client
import json
import os
import socket
import ssl
import sys
from pathlib import Path
from typing import Any
from urllib import error, request

TELEGRAM_TEXT_LIMIT = 4096
TELEGRAM_API_HOST = "api.telegram.org"
DEFAULT_TELEGRAM_FALLBACK_IPS = ("149.154.166.110", "149.154.167.220")


@dataclass(frozen=True)
class TelegramConfig:
    bot_token: str = ""
    chat_id: str = ""
    thread_id: str | None = None
    dry_run: bool = False
    timeout_seconds: int = 15
    fallback_ips: tuple[str, ...] = DEFAULT_TELEGRAM_FALLBACK_IPS
    prefer_fallback_ips: bool = False
    env_file: str | None = None


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _truncate_text(text: str, limit: int = TELEGRAM_TEXT_LIMIT) -> str:
    if len(text) <= limit:
        return text
    suffix = "\n...[truncated]"
    keep = max(0, limit - len(suffix))
    return text[:keep].rstrip() + suffix


def _read_env_file(path: str | None) -> dict[str, str]:
    if not path:
        return {}
    env_path = Path(path).expanduser()
    if not env_path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip().strip("\ufeff")
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        values[key] = value
    return values


def _env_value(key: str, file_values: dict[str, str], default: str = "") -> str:
    return os.getenv(key, file_values.get(key, default))


def _parse_fallback_ips(value: str) -> tuple[str, ...]:
    ips: list[str] = []
    for part in value.replace(";", ",").split(","):
        candidate = part.strip()
        if not candidate:
            continue
        try:
            socket.inet_aton(candidate)
        except OSError:
            continue
        ips.append(candidate)
    return tuple(dict.fromkeys(ips))


class _TelegramFallbackHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, ip_address: str, server_hostname: str, timeout: int):
        super().__init__(ip_address, 443, timeout=timeout, context=ssl.create_default_context())
        self._server_hostname = server_hostname

    def connect(self) -> None:
        self.sock = socket.create_connection((self.host, self.port), self.timeout, self.source_address)
        self.sock = self._context.wrap_socket(self.sock, server_hostname=self._server_hostname)


def _post_telegram_via_fallback_ip(ip_address: str, path: str, body: bytes, timeout_seconds: int) -> dict[str, Any]:
    conn = _TelegramFallbackHTTPSConnection(ip_address, TELEGRAM_API_HOST, timeout_seconds)
    try:
        conn.request(
            "POST",
            path,
            body=body,
            headers={
                "Host": TELEGRAM_API_HOST,
                "Content-Type": "application/json",
                "Content-Length": str(len(body)),
                "Connection": "close",
                "User-Agent": "stock-research-agent-telegram-notify",
            },
        )
        resp = conn.getresponse()
        decoded = resp.read().decode("utf-8", errors="replace")
        if 200 <= resp.status < 300:
            return json.loads(decoded) if decoded else {"ok": True}
        raise RuntimeError(f"Telegram send failed HTTP {resp.status}: {decoded}")
    finally:
        conn.close()


def load_telegram_config() -> TelegramConfig:
    env_file = os.getenv("TELEGRAM_ENV_FILE")
    file_values = _read_env_file(env_file)
    dry_run = _truthy(_env_value("TELEGRAM_NOTIFY_DRY_RUN", file_values))
    token = _env_value("TELEGRAM_BOT_TOKEN", file_values).strip()
    chat_id = _env_value("TELEGRAM_CHAT_ID", file_values).strip()
    if not chat_id:
        allowed_users = _env_value("TELEGRAM_ALLOWED_USERS", file_values).strip()
        chat_id = next((part.strip() for part in allowed_users.replace(";", ",").split(",") if part.strip()), "")
    thread_id = _env_value("TELEGRAM_THREAD_ID", file_values).strip() or None
    timeout_raw = _env_value("TELEGRAM_NOTIFY_TIMEOUT", file_values, "15").strip() or "15"
    try:
        timeout_seconds = max(1, int(timeout_raw))
    except ValueError:
        timeout_seconds = 15

    fallback_raw = _env_value("TELEGRAM_FALLBACK_IPS", file_values, ",".join(DEFAULT_TELEGRAM_FALLBACK_IPS)).strip()
    fallback_ips = () if _truthy(_env_value("TELEGRAM_DISABLE_FALLBACK_IPS", file_values)) else _parse_fallback_ips(fallback_raw)
    prefer_fallback_ips = _truthy(_env_value("TELEGRAM_PREFER_FALLBACK_IPS", file_values))

    if not dry_run and (not token or not chat_id):
        raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required unless TELEGRAM_NOTIFY_DRY_RUN=1")
    if dry_run and not chat_id:
        chat_id = "dry-run"

    return TelegramConfig(
        bot_token=token,
        chat_id=chat_id,
        thread_id=thread_id,
        dry_run=dry_run,
        timeout_seconds=timeout_seconds,
        fallback_ips=fallback_ips,
        prefer_fallback_ips=prefer_fallback_ips,
        env_file=env_file,
    )


def build_telegram_payload(response: dict[str, Any], chat_id: str, thread_id: str | None = None) -> dict[str, Any]:
    message = str(response.get("message") or "").strip()
    if not message:
        symbol = str(response.get("symbol") or "UNKNOWN")
        message = f"TradingView alert: {symbol}\n(no message returned)"

    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": _truncate_text(message),
        "disable_web_page_preview": True,
    }
    if thread_id:
        payload["message_thread_id"] = int(thread_id)
    return payload


def _safe_log_payload(payload: dict[str, Any]) -> dict[str, Any]:
    safe = dict(payload)
    if "chat_id" in safe:
        safe["chat_id"] = "***"
    if "message_thread_id" in safe:
        safe["message_thread_id"] = "***"
    return safe


def send_telegram_message(payload: dict[str, Any], config: TelegramConfig) -> dict[str, Any]:
    if config.dry_run:
        print(json.dumps({"status": "dry_run", "payload": _safe_log_payload(payload)}, ensure_ascii=False), flush=True)
        return {"status": "dry_run", "payload": payload}

    url = f"https://{TELEGRAM_API_HOST}/bot{config.bot_token}/sendMessage"
    path = f"/bot{config.bot_token}/sendMessage"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def try_fallback_ips() -> dict[str, Any]:
        last_error: Exception | None = None
        for ip_address in config.fallback_ips:
            try:
                return _post_telegram_via_fallback_ip(ip_address, path, body, config.timeout_seconds)
            except Exception as fallback_exc:
                last_error = fallback_exc
        if last_error is not None:
            raise last_error
        raise RuntimeError("no Telegram fallback IPs configured")

    if config.prefer_fallback_ips and config.fallback_ips:
        try:
            return try_fallback_ips()
        except Exception:
            # If the direct-IP route is degraded, still allow normal DNS/HTTPS as a last chance.
            pass

    req = request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with request.urlopen(req, timeout=config.timeout_seconds) as resp:
            decoded = resp.read().decode("utf-8", errors="replace")
            return json.loads(decoded) if decoded else {"ok": True}
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram send failed HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:
        try:
            return try_fallback_ips()
        except Exception as fallback_exc:
            raise RuntimeError(f"Telegram send failed: {fallback_exc}") from exc


def summarize_telegram_result(result: dict[str, Any]) -> dict[str, Any]:
    """Return a log-safe Telegram result without chat/user/message content."""
    summary: dict[str, Any] = {"status": "sent", "ok": bool(result.get("ok"))}
    message = result.get("result") if isinstance(result.get("result"), dict) else {}
    message_id = message.get("message_id")
    if message_id is not None:
        summary["message_id"] = message_id
    return summary


def main(stdin_text: str | None = None) -> int:
    raw = sys.stdin.read() if stdin_text is None else stdin_text
    try:
        response = json.loads(raw or "{}")
        if not isinstance(response, dict):
            raise ValueError("stdin JSON must be an object")
        config = load_telegram_config()
        payload = build_telegram_payload(response, config.chat_id, config.thread_id)
        result = send_telegram_message(payload, config)
        if not config.dry_run:
            print(json.dumps(summarize_telegram_result(result), ensure_ascii=False), flush=True)
        return 0
    except Exception as exc:
        print(f"telegram_notify_error: {exc}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
