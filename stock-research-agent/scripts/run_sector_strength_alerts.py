#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable
try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.main import build_response
from src.telegram_notify import (
    TELEGRAM_TEXT_LIMIT,
    TelegramConfig,
    build_telegram_payload,
    load_telegram_config,
    send_telegram_message,
    summarize_telegram_result,
)


ResponseBuilder = Callable[[], dict[str, Any]]
Sender = Callable[[dict[str, Any], TelegramConfig], dict[str, Any]]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Send 5-minute sector-strength/regime alerts to Telegram")
    parser.add_argument("--interval-seconds", type=int, default=300, help="alert interval; default 300 seconds")
    parser.add_argument("--once", action="store_true", help="send one alert and exit")
    parser.add_argument("--dry-run", action="store_true", help="print sanitized Telegram payload without real send")
    parser.add_argument("--env-file", default=os.getenv("TELEGRAM_ENV_FILE"), help="Telegram env file path")
    parser.add_argument("--timeout-seconds", type=int, default=15, help="Telegram send timeout")
    parser.add_argument("--json", action="store_true", dest="as_json", help="print sanitized JSON result")
    parser.add_argument("--market-hours-only", action="store_true", help="send only during US regular market hours")
    parser.add_argument("--change-only", action="store_true", help="send only when alert signature changes or cooldown expires")
    parser.add_argument("--cooldown-seconds", type=int, default=900, help="minimum repeat interval for unchanged alerts; default 900 seconds")
    parser.add_argument("--state-file", default=str(ROOT / "logs" / "sector_strength_alert_state.json"), help="state file for change-only/cooldown")
    return parser


def build_sector_response() -> dict[str, Any]:
    return build_response('{"mode":"sector_strength","request":"장중 섹터 강약 5분 알림"}')


def _select_alert_focus_lines(focus: Any, max_items: int = 7) -> list[str]:
    if not isinstance(focus, list):
        return []
    cleaned = [str(item).strip() for item in focus if str(item).strip()]
    priority_prefixes = (
        "시장 레짐:",
        "강한 테마:",
        "약한 테마:",
        "로테이션 해석:",
        "오늘 먼저 볼 종목:",
        "ETF 시장 참고:",
        "벤치마크:",
    )
    selected: list[str] = []
    seen: set[str] = set()
    for prefix in priority_prefixes:
        for text in cleaned:
            if text.startswith(prefix) and text not in seen:
                selected.append(text)
                seen.add(text)
                break
    for text in cleaned:
        if len(selected) >= max_items:
            break
        if text not in seen:
            selected.append(text)
            seen.add(text)
    return selected[:max_items]


def build_alert_text(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    summary = str(payload.get("summary") or "장중 섹터 강약").strip()
    lines.append(f"[Sector Strength Alert] {summary}")

    for text in _select_alert_focus_lines(payload.get("focus") or []):
        lines.append(f"- {text}")

    next_actions = payload.get("next_actions") or []
    if isinstance(next_actions, list) and next_actions:
        lines.append("[액션]")
        for item in next_actions[:3]:
            text = str(item).strip()
            if text:
                lines.append(f"- {text}")

    text = "\n".join(lines).strip()
    if len(text) > min(1200, TELEGRAM_TEXT_LIMIT):
        text = text[:1180].rstrip() + "\n...[truncated]"
    return text


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def is_us_regular_market_hours(now: datetime | None = None) -> bool:
    now = _to_utc(now or _now_utc())
    if ZoneInfo is None:
        et = now.astimezone(timezone.utc)
        hour_float = et.hour + et.minute / 60
        return et.weekday() < 5 and 14.5 <= hour_float < 21.0
    et = now.astimezone(ZoneInfo("America/New_York"))
    minutes = et.hour * 60 + et.minute
    return et.weekday() < 5 and (9 * 60 + 30) <= minutes < (16 * 60)


def _load_state(state_file: str | None) -> dict[str, Any]:
    if not state_file:
        return {}
    path = Path(state_file)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state_file: str | None, state: dict[str, Any]) -> None:
    if not state_file:
        return
    path = Path(state_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _first_symbol(rows: Any) -> str:
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        return str(rows[0].get("symbol") or rows[0].get("key") or "")
    return ""


def build_alert_signature(response: dict[str, Any]) -> str:
    report = ((response.get("data") or {}).get("sector_strength") or {}) if isinstance(response.get("data"), dict) else {}
    if not isinstance(report, dict):
        report = {}
    regime = (report.get("regime") or {}).get("label") if isinstance(report.get("regime"), dict) else None
    strong_theme = _first_symbol(report.get("strong_themes"))
    weak_theme = _first_symbol(report.get("weak_themes"))
    strong_sub_theme = _first_symbol(report.get("strong_sub_themes"))
    weak_sub_theme = _first_symbol(report.get("weak_sub_themes"))
    mover = _first_symbol(report.get("watchlist_movers"))
    if strong_theme or weak_theme or strong_sub_theme or weak_sub_theme or mover:
        return "|".join(str(item or "n/a") for item in (regime, strong_theme, weak_theme, strong_sub_theme, weak_sub_theme, mover))
    strong = _first_symbol(report.get("strong"))
    weak = _first_symbol(report.get("weak"))
    if any((regime, strong, weak)):
        return "|".join(str(item or "n/a") for item in (regime, strong, weak, mover))
    return str(response.get("summary") or "")


def _seconds_since(timestamp: str | None, now: datetime) -> float | None:
    if not timestamp:
        return None
    try:
        previous = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except Exception:
        return None
    return (_to_utc(now) - _to_utc(previous)).total_seconds()


def should_send_alert(response: dict[str, Any], state: dict[str, Any], now: datetime, change_only: bool, cooldown_seconds: int) -> tuple[bool, str, str]:
    signature = build_alert_signature(response)
    if not change_only:
        return True, "send", signature
    last_signature = str(state.get("last_signature") or "")
    elapsed = _seconds_since(state.get("last_sent_at"), now)
    cooldown = max(0, int(cooldown_seconds))
    if last_signature == signature and elapsed is not None and elapsed < cooldown:
        return False, "unchanged_cooldown", signature
    return True, "changed" if last_signature != signature else "cooldown_elapsed", signature


def _updated_state(signature: str, response: dict[str, Any], now: datetime) -> dict[str, Any]:
    return {
        "last_signature": signature,
        "last_summary": response.get("summary"),
        "last_sent_at": _to_utc(now).isoformat(),
    }


def _load_config(env_file: str | None, dry_run: bool, timeout_seconds: int) -> TelegramConfig:
    old_env_file = os.environ.get("TELEGRAM_ENV_FILE")
    old_dry_run = os.environ.get("TELEGRAM_NOTIFY_DRY_RUN")
    old_timeout = os.environ.get("TELEGRAM_NOTIFY_TIMEOUT")
    try:
        if env_file:
            os.environ["TELEGRAM_ENV_FILE"] = env_file
        if dry_run:
            os.environ["TELEGRAM_NOTIFY_DRY_RUN"] = "1"
        os.environ["TELEGRAM_NOTIFY_TIMEOUT"] = str(timeout_seconds)
        config = load_telegram_config()
    finally:
        if old_env_file is None:
            os.environ.pop("TELEGRAM_ENV_FILE", None)
        else:
            os.environ["TELEGRAM_ENV_FILE"] = old_env_file
        if old_dry_run is None:
            os.environ.pop("TELEGRAM_NOTIFY_DRY_RUN", None)
        else:
            os.environ["TELEGRAM_NOTIFY_DRY_RUN"] = old_dry_run
        if old_timeout is None:
            os.environ.pop("TELEGRAM_NOTIFY_TIMEOUT", None)
        else:
            os.environ["TELEGRAM_NOTIFY_TIMEOUT"] = old_timeout

    return replace(
        config,
        dry_run=bool(dry_run or config.dry_run),
        timeout_seconds=max(1, int(timeout_seconds)),
        env_file=env_file or config.env_file,
    )


def run_once(
    response_builder: ResponseBuilder = build_sector_response,
    sender: Sender = send_telegram_message,
    dry_run: bool = False,
    env_file: str | None = None,
    timeout_seconds: int = 15,
    market_hours_only: bool = False,
    change_only: bool = False,
    cooldown_seconds: int = 900,
    state_file: str | None = None,
    now_provider: Callable[[], datetime] = _now_utc,
) -> dict[str, Any]:
    now = _to_utc(now_provider())
    if market_hours_only and not is_us_regular_market_hours(now):
        return {
            "status": "skipped",
            "reason": "outside_market_hours",
            "mode": "sector_strength",
            "checked_at": now.isoformat(),
        }

    response = response_builder()
    state = _load_state(state_file)
    should_send, reason, signature = should_send_alert(response, state, now, change_only=change_only, cooldown_seconds=cooldown_seconds)
    if not should_send:
        return {
            "status": "skipped",
            "reason": reason,
            "mode": response.get("mode", "sector_strength"),
            "summary": response.get("summary"),
            "signature": signature,
            "checked_at": now.isoformat(),
        }

    text = build_alert_text(response)
    config = _load_config(env_file=env_file, dry_run=dry_run, timeout_seconds=timeout_seconds)
    payload = build_telegram_payload({"message": text}, chat_id=config.chat_id, thread_id=config.thread_id)
    telegram_result = sender(payload, config)
    _save_state(state_file, _updated_state(signature, response, now))
    return {
        "status": "ok",
        "reason": reason,
        "mode": response.get("mode", "sector_strength"),
        "summary": response.get("summary"),
        "signature": signature,
        "telegram": telegram_result if dry_run else summarize_telegram_result(telegram_result),
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.interval_seconds <= 0:
        parser.error("--interval-seconds must be positive")

    while True:
        result = run_once(
            dry_run=args.dry_run,
            env_file=args.env_file,
            timeout_seconds=args.timeout_seconds,
            market_hours_only=args.market_hours_only,
            change_only=args.change_only,
            cooldown_seconds=args.cooldown_seconds,
            state_file=args.state_file,
        )
        print(json.dumps(result, ensure_ascii=False) if args.as_json else f"sector_strength alert: {result.get('telegram')}", flush=True)
        if args.once:
            return 0
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
