from __future__ import annotations

import json
import re
import subprocess
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_THREADS_SEED_PATH = Path(__file__).resolve().parents[1] / "config" / "threads_seed_accounts.json"
DEFAULT_THREADS_CLASSIFIED_PATH = Path(__file__).resolve().parents[1] / "config" / "threads_seed_accounts_classified.json"


def load_threads_seed_accounts(path: str | Path | None = None) -> list[dict[str, str]]:
    seed_path = Path(path or DEFAULT_THREADS_SEED_PATH)
    if not seed_path.exists():
        return []
    try:
        data = json.loads(seed_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    accounts = data.get("accounts", []) if isinstance(data, dict) else []
    normalized = []
    for item in accounts:
        if not isinstance(item, dict):
            continue
        handle = str(item.get("handle") or "").strip()
        display_name = str(item.get("display_name") or handle).strip()
        if handle:
            normalized.append({"handle": handle, "display_name": display_name})
    return normalized


def classify_seed_account(handle: str, display_name: str) -> dict[str, str]:
    text = f"{handle} {display_name}".lower()
    if any(token in text for token in ["btc", "코인", "crypto", "비트코인", "eth", "coin"]):
        category = "crypto"
    elif any(token in text for token in ["news", "경제", "증시", "wall_street", "futuresnow", "today", "전략가", "guide"]):
        category = "macro_news"
    elif any(token in text for token in ["trader", "차트", "매매", "투자노트", "투자일지", "bull", "양봉", "롱", "숏"]):
        category = "trader"
    elif any(token in text for token in ["미국주식", "국내주식", "stock", "nasdaq", "invest"]):
        category = "stocks"
    elif any(token in text for token in ["coding", "code", "조코딩"]):
        category = "other"
    else:
        category = "general_investing"

    if category in {"macro_news", "stocks", "trader", "crypto"}:
        priority = "high"
    elif category == "general_investing":
        priority = "medium"
    else:
        priority = "low"
    return {"category": category, "priority": priority}


def build_threads_seed_classification(seed_path: str | Path | None = None) -> dict[str, Any]:
    accounts = load_threads_seed_accounts(seed_path)
    classified = []
    for item in accounts:
        meta = classify_seed_account(item["handle"], item["display_name"])
        classified.append({**item, **meta})
    grouped: dict[str, list[str]] = {}
    for item in classified:
        grouped.setdefault(item["category"], []).append(item["handle"])
    return {
        "version": 1,
        "generated_by": "heuristic_seed_classification",
        "accounts": classified,
        "grouped_handles": grouped,
    }


def save_threads_seed_classification(output_path: str | Path | None = None, seed_path: str | Path | None = None) -> Path:
    target_path = Path(output_path or DEFAULT_THREADS_CLASSIFIED_PATH)
    payload = build_threads_seed_classification(seed_path)
    target_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target_path


def _extract_recent_hits_from_search_markdown(markdown: str, allowed_handles: set[str], query: str, recent_days: int = 14, now: datetime | None = None) -> list[dict[str, Any]]:
    now = now or datetime.utcnow()
    lines = markdown.splitlines()
    hits: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw in lines:
        line = raw.strip()
        profile_match = re.match(r"\[(.+?)\]\(https://www\.threads\.com/@([^/\)]+)\)", line)
        if profile_match:
            handle = profile_match.group(2)
            if handle in allowed_handles:
                current = {
                    "display_name": profile_match.group(1),
                    "handle": handle,
                    "date": None,
                    "post_url": None,
                    "texts": [],
                    "query": query,
                }
            else:
                current = None
            continue
        if current is None:
            continue
        post_match = re.match(r"\[(\d{2}/\d{2}/\d{2})\]\((https://www\.threads\.com/@[^/]+/post/[^\)]+)\)", line)
        if post_match:
            current["date"] = post_match.group(1)
            current["post_url"] = post_match.group(2)
            continue
        if not current.get("date"):
            continue
        if not line or line == "Translate" or line == "Related threads" or line.startswith("!["):
            continue
        current["texts"].append(line)
        if len(current["texts"]) >= 4:
            try:
                dt = datetime.strptime(str(current["date"]), "%m/%d/%y")
            except ValueError:
                current = None
                continue
            days_ago = (now - dt).days
            if days_ago <= recent_days:
                text = " | ".join(current["texts"][:4])
                hits.append(
                    {
                        "handle": current["handle"],
                        "display_name": current["display_name"],
                        "date": current["date"],
                        "days_ago": days_ago,
                        "post_url": current["post_url"],
                        "text": text,
                        "query": query,
                    }
                )
            current = None
    deduped = []
    seen = set()
    for item in hits:
        key = item["post_url"]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def search_threads_seed_accounts(query: str, recent_days: int = 14, seed_path: str | Path | None = None) -> list[dict[str, Any]]:
    accounts = load_threads_seed_accounts(seed_path)
    allowed_handles = {item["handle"] for item in accounts}
    if not allowed_handles:
        return []
    queries = [query]
    if query.upper() != query:
        queries.append(query.upper())
    all_hits: list[dict[str, Any]] = []
    for q in list(dict.fromkeys(item for item in queries if item.strip())):
        search_url = "https://r.jina.ai/http://https://www.threads.com/search?q=" + urllib.parse.quote(q)
        output = subprocess.check_output(["curl", "-sS", "-L", search_url], text=True, timeout=90)
        all_hits.extend(_extract_recent_hits_from_search_markdown(output, allowed_handles, q, recent_days=recent_days))
    deduped = []
    seen = set()
    for item in sorted(all_hits, key=lambda row: (row["days_ago"], row["handle"])):
        if item["post_url"] in seen:
            continue
        seen.add(item["post_url"])
        deduped.append(item)
    return deduped
