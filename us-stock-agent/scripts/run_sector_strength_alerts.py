#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import re
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
    parser.add_argument("--mode", choices=["sector_strength", "oil_vix", "market_regime"], default="sector_strength", help="alert payload mode; oil_vix is for VIX/WTI spike alerts")
    parser.add_argument("--trigger-only", action="store_true", help="send only when the selected mode has explicit trigger alerts")
    return parser


def build_sector_response() -> dict[str, Any]:
    return build_response('{"mode":"sector_strength","request":"장중 섹터 강약 5분 알림"}')


def build_oil_vix_response() -> dict[str, Any]:
    return build_response('{"mode":"oil_vix","request":"VIX/WTI 급등 감시 알림"}')


def build_market_regime_response() -> dict[str, Any]:
    return build_response('{"mode":"market_regime","request":"장 분위기 급변 감시 알림"}')


def response_builder_for_mode(mode: str) -> ResponseBuilder:
    if mode == "oil_vix":
        return build_oil_vix_response
    if mode == "market_regime":
        return build_market_regime_response
    return build_sector_response


def _select_alert_focus_lines(focus: Any, max_items: int = 7) -> list[str]:
    if not isinstance(focus, list):
        return []
    cleaned = [str(item).strip() for item in focus if str(item).strip()]
    priority_prefixes = (
        "장 분위기:",
        "강한 테마:",
        "약한 테마:",
        "로테이션 해석:",
        "오늘 먼저 볼 종목:",
        "ETF 시장 참고:",
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


_BB_STATUS_TOKENS = "중립|상단근접|상단권|하단근접|하단권|밴드내"
_BB_STATUS_RE = re.compile(
    rf"(BB\s+[+-]?\d+(?:\.\d+)?%(?:\([^)]*\))?)(?:\s+(?:{_BB_STATUS_TOKENS}))(?=\s*(?:[,;:]|$))"
)


def _strip_bb_status_noise(text: str) -> str:
    return _BB_STATUS_RE.sub(r"\1", text)


def _strip_alert_display_noise(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return ""
    # Keep source/time correctness in the data pipeline, but do not surface
    # implementation/baseline labels in the mobile Telegram body.
    cleaned = cleaned.replace(" / source toss_wts_stock_prices", "")
    cleaned = cleaned.replace("source toss_wts_stock_prices", "")
    cleaned = re.sub(r"\s*/\s*SPY 대비\s*[+-]?\d+(?:\.\d+)?%?", "", cleaned)
    cleaned = re.sub(r"\s*/\s*전일대비\s*[+-]?\d+(?:\.\d+)?%", "", cleaned)
    cleaned = cleaned.replace(" / Toss base 대비", "")
    cleaned = cleaned.replace(", Toss base 대비", "")
    cleaned = cleaned.replace("Toss base 대비", "")
    cleaned = cleaned.replace(" / 세션 토스 데이마켓/주간거래", "")
    cleaned = cleaned.replace("세션 토스 데이마켓/주간거래", "")
    cleaned = cleaned.replace(", 토스 데이마켓/주간거래", "")
    cleaned = cleaned.replace("토스 데이마켓/주간거래, ", "")
    cleaned = cleaned.replace("토스 데이마켓/주간거래", "")
    cleaned = re.sub(r"\s*/\s*/\s*", " / ", cleaned)
    cleaned = re.sub(r",\s*,", ",", cleaned)
    cleaned = re.sub(r";\s*,", ";", cleaned)
    cleaned = re.sub(r"\(\s*([^)]*?)\s*,\s*\)", r"(\1)", cleaned)
    cleaned = re.sub(r"\(\s*([^)]*?)\s*;\s*\)", r"(\1)", cleaned)
    cleaned = _strip_bb_status_noise(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = cleaned.replace(" / 기준시각", " / 기준시각")
    return cleaned.strip(" ,/")


def _clean_focus_lines(focus: Any) -> list[str]:
    if not isinstance(focus, list):
        return []
    lines: list[str] = []
    for item in focus:
        cleaned = _strip_alert_display_noise(str(item))
        if cleaned:
            lines.append(cleaned)
    return lines


def _strip_focus_prefix(text: str, prefix: str) -> str:
    return text[len(prefix):].strip() if text.startswith(prefix) else text.strip()


def _focus_line(lines: list[str], prefix: str, contains: str | None = None, last: bool = False) -> str:
    iterable = reversed(lines) if last else iter(lines)
    for text in iterable:
        if not text.startswith(prefix):
            continue
        if contains and contains not in text:
            continue
        return _strip_focus_prefix(text, prefix)
    return ""


def _split_focus_parts(text: str, max_items: int) -> list[str]:
    if not text:
        return []
    parts = [part.strip() for part in text.split("|") if part.strip()]
    return parts[:max_items]


def _payload_collected_at(payload: dict[str, Any]) -> str | None:
    direct = payload.get("collected_at")
    if direct:
        return str(direct)
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    if not isinstance(data, dict):
        return None
    for key in ("sector_strength", "oil_vix", "market_regime"):
        section = data.get(key)
        if isinstance(section, dict) and section.get("collected_at"):
            return str(section.get("collected_at"))
    return None


def _alert_time_label(payload: dict[str, Any]) -> str:
    raw = _payload_collected_at(payload)
    dt: datetime | None = None
    if raw:
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            dt = None
    dt = _to_utc(dt or _now_utc())
    if ZoneInfo is None:
        return dt.strftime("%H:%M UTC")
    kst = dt.astimezone(ZoneInfo("Asia/Seoul"))
    et = dt.astimezone(ZoneInfo("America/New_York"))
    return f"{kst:%H:%M} KST / {et:%H:%M} ET"


def _sector_mood_label(text: str) -> str:
    label = text.split("/", 1)[0].strip()
    return label or "중립"


def _sector_mood_lines(focus_lines: list[str]) -> list[str]:
    benchmark = _focus_line(focus_lines, "장 분위기:", contains="NASDAQ", last=True)
    benchmark = _strip_alert_display_noise(benchmark.split(" / 기준시각", 1)[0].strip())
    mood = ""
    for text in focus_lines:
        if text.startswith("장 분위기:") and "NASDAQ" not in text:
            mood = _sector_mood_label(_strip_focus_prefix(text, "장 분위기:"))
            break
    etf = _focus_line(focus_lines, "ETF 시장 참고:")
    flow_proxy = _focus_line(focus_lines, "수급 proxy:")
    lines: list[str] = []
    if flow_proxy:
        lines.append(f"- 수급: {flow_proxy}")
    if benchmark:
        lines.append(f"- {benchmark}")
    return lines or ["데이터 부족"]



def _short_theme_label(name: str) -> str:
    if "우주" in name:
        return "우주"
    if "암호화" in name or "코인" in name:
        return "코인"
    if "원전" in name or "우라늄" in name or "전력" in name or "에너지" in name:
        return "원전"
    if "반도체" in name:
        return "반도체"
    if "AI" in name or "빅테크" in name or "인프라" in name:
        return "AI"
    if "양자" in name:
        return "양자"
    if "헬스" in name or "GLP" in name:
        return "헬스"
    return name.split("/", 1)[0].strip() or name.strip()


def _indicator_head(details: str, label: str) -> str:
    if label == "스토캐스틱 Slow":
        pattern = r"스토캐스틱 Slow\s+([^:;]+)"
    else:
        pattern = rf"{re.escape(label)}\s+([^:;]+)"
    match = re.search(pattern, details)
    if not match:
        return "n/a"
    value = match.group(1).strip()
    if label == "BB":
        # Telegram compact lines should keep the Bollinger value only.
        # Status words like "중립"/"상단근접" are noisy on mobile and duplicate
        # the user's own read of the %B number.
        bb_value = re.match(r"([+-]?\d+(?:\.\d+)?%(?:\([^)]*\))?)", value)
        if bb_value:
            return bb_value.group(1)
        for token in ("중립", "상단근접", "상단권", "하단근접", "하단권", "밴드내"):
            value = value.replace(token, "")
        return " ".join(value.split()) or "n/a"
    return value


def _compact_theme_leader(item: str, include_indicators: bool = True) -> str:
    text = item.strip()
    if not text:
        return text
    lead, sep, details = text.partition(" — ")
    theme, colon, rest = lead.partition(":")
    if not colon:
        base = lead.strip()
        theme_label = ""
    else:
        theme_label = _short_theme_label(theme.strip())
        rest_head = rest.split(",", 1)[0].strip()
        rest_head = re.sub(r"\b가격\s+([^,\s]+)", r"$\1", rest_head)
        base = f"{theme_label}: {rest_head}"
    if not sep or not include_indicators:
        return base or text
    rsi = _indicator_head(details, "RSI")
    macd = _indicator_head(details, "MACD")
    stoch = _indicator_head(details, "스토캐스틱 Slow")
    bb = _indicator_head(details, "BB")
    return f"{base} | RSI {rsi}, MACD {macd}, 스토캐스틱 Slow {stoch}, BB {bb}"

_BLOCKED_ALERT_INDICATOR_TOKENS = ("구름", "전환선", "기준선", "일목", "Ichimoku", "ichimoku")


def _normalize_alert_indicator_clause(clause: str) -> str:
    text = clause.strip()
    if text.startswith("Stoch "):
        return "스토캐스틱 Slow " + text[len("Stoch "):]
    return text


def _is_allowed_alert_indicator_clause(clause: str) -> bool:
    return not any(token in clause for token in _BLOCKED_ALERT_INDICATOR_TOKENS)


def _format_mover_lines(movers: list[str]) -> list[str]:
    if not movers:
        return ["데이터 부족"]
    lines: list[str] = []
    for item in movers:
        text = item.strip()
        if not text:
            continue
        if " — " not in text:
            lines.append(f"• {text}")
            continue
        lead, details = text.split(" — ", 1)
        lines.append(f"• {lead.strip()}")
        clauses = [part.strip() for part in details.split(";") if part.strip()]
        for clause in clauses:
            if not _is_allowed_alert_indicator_clause(clause):
                continue
            lines.append(f"  · {_normalize_alert_indicator_clause(clause)}")
    return lines or ["데이터 부족"]


def _format_rotation_lines(rotation: str) -> list[str]:
    text = rotation.strip()
    if not text:
        return ["데이터 부족"]
    parts = [part.strip() for part in text.split(" / ") if part.strip()]
    if len(parts) >= 2:
        return [f"• {part}" for part in parts[:2]]
    return [f"• {text}"]


_ACTION_TEXT_REPLACEMENTS = (
    ("추격 금지", "가격 과열 확인"),
    ("추격금지", "가격 과열 확인"),
    ("관망보다", "방향 확인 후"),
    ("관망", "방향 보류"),
    ("매매 관점", "확인"),
    ("한줄 판단", "결론"),
    ("추격보다", "조건은"),
)


def _clean_conclusion_action(text: str) -> str:
    cleaned = str(text or "").strip()
    for old, new in _ACTION_TEXT_REPLACEMENTS:
        cleaned = cleaned.replace(old, new)
    cleaned = cleaned.replace("강한 테마가 SPY 대비 계속 우위인지 5분 뒤 재확인", "강한 테마 우위가 5분 뒤에도 유지되는지 재확인")
    cleaned = cleaned.replace("SPY 대비", "")
    return " ".join(cleaned.split())


_SUMMARY_MARKET_MOOD_RE = re.compile(r"\s*/\s*(?:장 분위기|시장)\s*(?:중립|보합|혼조|강세|약세|리스크온|리스크오프)(?=\s*(?:/|$))")


def _clean_summary_text(summary: str) -> str:
    text = " ".join(str(summary or "").strip().split())
    text = _SUMMARY_MARKET_MOOD_RE.sub("", text)
    text = text.replace("장 분위기", "시장")
    return " ".join(text.strip(" /-").split())


def _weak_line_relative_label(line: str) -> tuple[str, str] | None:
    match = re.search(
        r"^(?P<theme>.+?)\s+평균\s+(?P<avg>[+-]?\d+(?:\.\d+)?)%.*?상승비율\s+(?P<breadth>[+-]?\d+(?:\.\d+)?)%",
        str(line or "").strip(),
    )
    if not match:
        return None
    theme = match.group("theme").strip()
    try:
        avg = float(match.group("avg"))
        breadth = float(match.group("breadth"))
    except ValueError:
        return None
    # If the weak bucket is still positive or more than half the names are rising,
    # it is weak only relative to stronger themes, not absolute weakness.
    label = "상대 약세" if avg >= 0 or breadth >= 50 else "약세"
    return theme, label


def _apply_relative_weakness_labels(summary_text: str, weak_lines: list[str] | None) -> str:
    text = summary_text
    for line in weak_lines or []:
        parsed = _weak_line_relative_label(line)
        if not parsed:
            continue
        theme, label = parsed
        text = text.replace(f"{theme} 상대 약세", f"{theme} {label}")
        text = text.replace(f"{theme} 약세", f"{theme} {label}")
    return " ".join(text.split())


_RISK_ACTION_MARKERS = ("리스크", "VIX", "WTI", "유가", "오일", "분봉")


def _is_risk_related_action(text: str) -> bool:
    return any(marker in text for marker in _RISK_ACTION_MARKERS)


def _format_conclusion_lines(summary: str, rotation: str, actions: list[str], weak_lines: list[str] | None = None) -> list[str]:
    lines: list[str] = []
    cleaned_actions = []
    for item in actions:
        cleaned = _clean_conclusion_action(item)
        if cleaned and not _is_risk_related_action(cleaned):
            cleaned_actions.append(cleaned)
    if cleaned_actions:
        lines.append(f"• 확인: {' / '.join(cleaned_actions[:2])}")
    else:
        lines.append("• 확인: 5분 뒤 SPY·주도테마 재확인")

    rotation_text = rotation.strip()
    if rotation_text and "뚜렷한 세부테마 내부 로테이션 없음" not in rotation_text:
        for line in _format_rotation_lines(rotation_text)[:2]:
            lines.append(f"• 로테이션: {line[2:] if line.startswith('• ') else line}")

    summary_text = _apply_relative_weakness_labels(_clean_summary_text(summary), weak_lines)
    if summary_text:
        lines.append(f"• 결론: {summary_text}")
    return lines


def _format_previous_close_strength_lines(line: str) -> list[str]:
    text = _strip_focus_prefix(line, "전일종가 대비 현재 강세:")
    if not text:
        return []
    body = text
    for marker in (" / 기준 ", " / 출처 "):
        body = body.split(marker, 1)[0].strip()
    items = [item.strip() for item in body.split(" | ") if item.strip()]
    lines = ["현재 강세"]
    for item in items[:3]:
        compact = item.replace(", 기준 전일 정규장 종가 대비 현재가", "")
        compact = compact.replace(", 출처 Yahoo chart 1m includePrePost", "")
        lines.append(f"• {compact}")
    return lines


def _build_sector_telegram_text(payload: dict[str, Any]) -> str:
    focus_lines = _clean_focus_lines(payload.get("focus") or [])
    summary = str(payload.get("summary") or "장중 테마 강약").strip()
    strong = _split_focus_parts(_focus_line(focus_lines, "강한 테마:"), 5)
    weak = _split_focus_parts(_focus_line(focus_lines, "약한 테마:"), 2)
    theme_leaders = _split_focus_parts(_focus_line(focus_lines, "테마별 대장주:"), 20)
    movers = _split_focus_parts(_focus_line(focus_lines, "오늘 먼저 볼 종목:"), 5)
    previous_close_strength = _focus_line(focus_lines, "전일종가 대비 현재 강세:")
    rotation = _focus_line(focus_lines, "로테이션 해석:") or "뚜렷한 세부테마 내부 로테이션 없음"
    actions = [str(item).strip() for item in (payload.get("next_actions") or []) if str(item).strip()]
    limit = min(1800, TELEGRAM_TEXT_LIMIT)

    def render(selected_movers: list[str], selected_theme_leaders: list[str] | None = None) -> str:
        rendered_theme_leaders = selected_theme_leaders if selected_theme_leaders is not None else theme_leaders
        lines = [
            f"[5분 테마 알림 | {_alert_time_label(payload)}]",
            "",
            "1) 시장",
        ]
        lines.extend(_sector_mood_lines(focus_lines))
        lines.extend([
            "",
            "2) 강한 테마",
        ])
        display_strong = strong[:5]
        display_weak = weak[:2]
        lines.extend(f"• {item}" for item in (display_strong or ["데이터 부족"]))
        lines.extend(["", "3) 약한 테마"])
        lines.extend(f"• {item}" for item in (display_weak or ["데이터 부족"]))
        lines.extend([
            "",
            "4) 먼저 볼 종목",
        ])
        if rendered_theme_leaders:
            lines.append("테마별 대장주:")
            lines.extend(f"• {item}" for item in rendered_theme_leaders)
        else:
            lines.extend(_format_mover_lines(selected_movers))
        if previous_close_strength:
            lines.extend(_format_previous_close_strength_lines(previous_close_strength))
        lines.extend(["", "5) 결론"])
        lines.extend(_format_conclusion_lines(summary, rotation, actions, display_weak))
        return "\n".join(lines).strip()

    initial_theme_leaders = [_compact_theme_leader(item) for item in theme_leaders[:7]] if theme_leaders else None
    text = render([] if theme_leaders else movers, initial_theme_leaders)
    if len(text) <= limit:
        return text

    if theme_leaders:
        compact_theme_leaders = [_compact_theme_leader(item) for item in theme_leaders[:7]]
        text = render([], compact_theme_leaders)
        if len(text) <= limit:
            return text

    # Analysis-style mover lines are intentionally more verbose. Use this path
    # only when there is no theme-leader block; otherwise it re-expands verbose
    # leaders and can hide sections 5/6 plus the one-line conclusion.
    if not theme_leaders:
        for count in range(min(len(movers), 4), 0, -1):
            text = render(movers[:count])
            if len(text) <= limit:
                return text

        if movers:
            first = movers[0]
            if len(first) > 420:
                first = first[:417].rstrip() + "..."
            text = render([first])
        if len(text) <= limit:
            return text

    if theme_leaders:
        for indicator_count in (2, 1):
            ultra_compact = [
                _compact_theme_leader(item, include_indicators=(idx < indicator_count))
                for idx, item in enumerate(theme_leaders[:7])
            ]
            text = render([], ultra_compact)
            if len(text) <= limit:
                return text
        for count in range(min(len(theme_leaders), 7), 0, -1):
            ultra_compact = [
                _compact_theme_leader(item, include_indicators=(idx == 0))
                for idx, item in enumerate(theme_leaders[:count])
            ]
            text = render([], ultra_compact)
            if len(text) <= limit:
                return text

    return text


def build_alert_text(payload: dict[str, Any]) -> str:
    if payload.get("mode") not in ("oil_vix", "market_regime"):
        return _build_sector_telegram_text(payload)

    lines: list[str] = []
    summary = str(payload.get("summary") or "장중 섹터 강약").strip()
    if payload.get("mode") == "oil_vix":
        prefix = "[Oil/VIX Spike Alert]"
    elif payload.get("mode") == "market_regime":
        prefix = "[Market Regime Alert]"
    else:
        prefix = "[Sector Strength Alert]"
    lines.append(f"{prefix} {summary}")

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
    if len(text) > min(1800, TELEGRAM_TEXT_LIMIT):
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


def _response_triggers(response: dict[str, Any]) -> list[str]:
    data = response.get("data") if isinstance(response.get("data"), dict) else {}
    if response.get("mode") == "oil_vix" and isinstance(data, dict):
        oil_vix = data.get("oil_vix") if isinstance(data.get("oil_vix"), dict) else {}
        alerts = oil_vix.get("alerts") if isinstance(oil_vix, dict) else []
        return [str(item) for item in alerts] if isinstance(alerts, list) else []
    return []


def build_alert_signature(response: dict[str, Any]) -> str:
    data = response.get("data") if isinstance(response.get("data"), dict) else {}
    if response.get("mode") == "oil_vix":
        oil_vix = (data or {}).get("oil_vix") if isinstance(data, dict) else {}
        if not isinstance(oil_vix, dict):
            oil_vix = {}
        alerts = oil_vix.get("alerts") or []
        if not isinstance(alerts, list):
            alerts = []
        alert_text = ",".join(str(item) for item in alerts) or "no_alert"
        vix = oil_vix.get("vix") if isinstance(oil_vix.get("vix"), dict) else {}
        oil = oil_vix.get("oil") if isinstance(oil_vix.get("oil"), dict) else {}
        return "|".join(
            str(item or "n/a")
            for item in (
                "oil_vix",
                alert_text,
                vix.get("structure") if isinstance(vix, dict) else None,
                oil.get("state") if isinstance(oil, dict) else None,
            )
        )

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
    trigger_only: bool = False,
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
    if trigger_only and not _response_triggers(response):
        return {
            "status": "skipped",
            "reason": "no_trigger",
            "mode": response.get("mode", "sector_strength"),
            "summary": response.get("summary"),
            "signature": build_alert_signature(response),
            "checked_at": now.isoformat(),
        }
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
            response_builder=response_builder_for_mode(args.mode),
            dry_run=args.dry_run,
            env_file=args.env_file,
            timeout_seconds=args.timeout_seconds,
            market_hours_only=args.market_hours_only,
            change_only=args.change_only,
            cooldown_seconds=args.cooldown_seconds,
            state_file=args.state_file,
            trigger_only=args.trigger_only,
        )
        print(json.dumps(result, ensure_ascii=False) if args.as_json else f"{args.mode} alert: {result.get('telegram')}", flush=True)
        if args.once:
            return 0
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
