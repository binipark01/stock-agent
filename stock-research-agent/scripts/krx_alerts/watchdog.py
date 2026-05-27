#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
MAX_AGE_MINUTES = int(os.getenv("KRX_WATCHDOG_MAX_AGE_MINUTES", "20"))
VERBOSE = os.getenv("KRX_WATCHDOG_VERBOSE", "").strip().lower() in {"1", "true", "yes", "on"}

REGULAR_SCRIPT = "krx_regular_alert_text.py"
AFTERHOURS_SCRIPT = "krx_afterhours_alert_text.py"


def hermes_home() -> Path:
    env = os.getenv("HERMES_HOME")
    if env:
        return Path(env)
    local = os.getenv("LOCALAPPDATA")
    if local:
        return Path(local) / "hermes"
    return Path.home() / "AppData" / "Local" / "hermes"


HOME = hermes_home()
JOBS_PATH = HOME / "cron" / "jobs.json"
OUTPUT_ROOT = HOME / "cron" / "output"
AGENT_LOG = HOME / "logs" / "agent.log"


def parse_dt(value: object) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value))
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=KST)
    return dt.astimezone(KST)


def load_jobs() -> list[dict]:
    data = json.loads(JOBS_PATH.read_text(encoding="utf-8"))
    jobs = data.get("jobs", [])
    return jobs if isinstance(jobs, list) else []


def find_job(jobs: list[dict], script_name: str) -> dict | None:
    for job in jobs:
        if str(job.get("script") or "").strip() == script_name:
            return job
    return None


def is_weekday(now: datetime) -> bool:
    return now.weekday() < 5


def active_target(now: datetime) -> tuple[str, str] | None:
    if not is_weekday(now):
        return None
    if 8 <= now.hour <= 15:
        return "정규장", REGULAR_SCRIPT
    if 16 <= now.hour <= 20:
        return "장후/SOR", AFTERHOURS_SCRIPT
    return None


def latest_output_file(job_id: str) -> Path | None:
    out_dir = OUTPUT_ROOT / job_id
    if not out_dir.exists():
        return None
    files = [p for p in out_dir.glob("*.md") if p.is_file()]
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def latest_delivery_time(job_id: str) -> datetime | None:
    if not AGENT_LOG.exists():
        return None
    pattern = re.compile(rf"^(\d{{4}}-\d{{2}}-\d{{2}} \d{{2}}:\d{{2}}:\d{{2}}),\d{{3}} .*Job '{re.escape(job_id)}': delivered to telegram:")
    try:
        with AGENT_LOG.open("rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - 4_000_000))
            text = f.read().decode("utf-8", errors="replace")
    except Exception:
        return None
    latest = None
    for line in text.splitlines():
        m = pattern.search(line)
        if not m:
            continue
        try:
            latest = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=KST)
        except Exception:
            continue
    return latest


def common_config_errors(label: str, job: dict | None) -> list[str]:
    errors: list[str] = []
    if not job:
        return [f"{label}: cron job 없음"]
    if not job.get("enabled"):
        errors.append(f"{label}: job 비활성화됨")
    if str(job.get("state") or "") not in {"scheduled", "running"}:
        errors.append(f"{label}: state={job.get('state')}")
    if not str(job.get("deliver") or "").startswith("telegram:"):
        errors.append(f"{label}: 텔레그램 deliver 아님")
    if job.get("no_agent") is not True:
        errors.append(f"{label}: no-agent 모드 아님")
    return errors


def active_delivery_errors(label: str, job: dict, now: datetime) -> list[str]:
    errors: list[str] = []
    job_id = str(job.get("id") or "")
    last_run = parse_dt(job.get("last_run_at"))
    age_limit = timedelta(minutes=MAX_AGE_MINUTES)

    if str(job.get("last_status") or "") != "ok":
        errors.append(f"{label}: last_status={job.get('last_status')} last_error={job.get('last_error') or '없음'}")
    if job.get("last_delivery_error"):
        errors.append(f"{label}: delivery_error={job.get('last_delivery_error')}")
    if not last_run:
        errors.append(f"{label}: last_run_at 없음")
    elif now - last_run > age_limit:
        errors.append(f"{label}: 마지막 실행 {int((now - last_run).total_seconds() // 60)}분 전")

    latest_out = latest_output_file(job_id)
    if not latest_out:
        errors.append(f"{label}: output 파일 없음")
    else:
        out_mtime = datetime.fromtimestamp(latest_out.stat().st_mtime, tz=KST)
        if now - out_mtime > age_limit:
            errors.append(f"{label}: output 갱신 {int((now - out_mtime).total_seconds() // 60)}분 전")
        if latest_out.stat().st_size < 100:
            errors.append(f"{label}: output 파일이 너무 작음")

    delivered_at = latest_delivery_time(job_id)
    if not delivered_at:
        errors.append(f"{label}: 최근 텔레그램 전송 로그 없음")
    elif now - delivered_at > age_limit:
        errors.append(f"{label}: 마지막 텔레그램 전송 로그 {int((now - delivered_at).total_seconds() // 60)}분 전")

    return errors


def main() -> int:
    now = datetime.now(KST)
    try:
        jobs = load_jobs()
    except Exception as exc:
        print(f"국장 알림 watchdog {now:%Y-%m-%d %H:%M}\n- cron jobs.json 읽기 실패: {exc}")
        return 0

    regular = find_job(jobs, REGULAR_SCRIPT)
    afterhours = find_job(jobs, AFTERHOURS_SCRIPT)

    errors: list[str] = []
    errors.extend(common_config_errors("정규장", regular))
    errors.extend(common_config_errors("장후/SOR", afterhours))

    target = active_target(now)
    if target:
        label, script = target
        job = regular if script == REGULAR_SCRIPT else afterhours
        if job:
            errors.extend(active_delivery_errors(label, job, now))

    if errors:
        print(f"국장 알림 watchdog {now:%Y-%m-%d %H:%M}\n장애 감지")
        for err in errors:
            safe = re.sub(r"telegram:[-0-9]+", "telegram:<redacted>", str(err))
            print(f"- {safe}")
        print("조치: Hermes cron/gateway와 KRX 알림 스크립트 확인 필요")
        return 0

    if VERBOSE:
        if target:
            label, _ = target
            print(f"국장 알림 watchdog {now:%Y-%m-%d %H:%M}: 정상 ({label} 전송 확인)")
        else:
            print(f"국장 알림 watchdog {now:%Y-%m-%d %H:%M}: 정상 (점검 시간 외, 설정만 확인)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
