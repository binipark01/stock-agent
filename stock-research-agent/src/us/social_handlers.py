"""US social and Threads mode handlers."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:
    from .social.threads import search_threads_seed_accounts
    from .social.threads_view_miner import build_threads_view_scan_report, save_threads_slow_state, save_threads_view_scan_artifacts
except ImportError:  # direct script execution
    from us.social.threads import search_threads_seed_accounts
    from us.social.threads_view_miner import build_threads_view_scan_report, save_threads_slow_state, save_threads_view_scan_artifacts


def extract_social_search_query(request_text: str, provided_symbols: list[str] | None = None) -> str:
    if provided_symbols:
        return provided_symbols[0]
    query = request_text
    for token in ["스레드", "threads", "threads에서", "찾아줘", "검색", "social", "팔로잉", "목록에서", "알려줘"]:
        query = query.replace(token, " ")
    query = re.sub(r"\s+", " ", query).strip()
    return query or request_text.strip() or "NVDA"


def build_social_search_payload(
    request_text: str,
    symbols: list[str],
    recent_days: int = 14,
    search_func=search_threads_seed_accounts,
) -> tuple[str, list[str], list[str]]:
    query = extract_social_search_query(request_text, provided_symbols=symbols)
    hits = search_func(query, recent_days=recent_days)
    focus = [f"최근 Threads 반응: seed 계정 기준 최근 {recent_days}일 검색 / query={query}"]
    if not hits:
        focus.append(f"최근 Threads 반응: 최근 {recent_days}일 기준 seed 계정 언급 없음")
        next_actions = [
            "검색어를 ticker / 한글 종목명 / 회사명으로 바꿔서 다시 조회",
            "최근 1~2주 언급이 없으면 뉴스/공시 쪽을 먼저 확인",
            "필요하면 코인/미국주식 계정군만 별도로 좁혀서 재검색",
        ]
        summary = f"seed 계정 기준 Threads 최근 반응을 찾았지만 {query} 언급은 없었습니다."
        return summary, focus, next_actions

    for item in hits[:5]:
        focus.append(f"@{item['handle']} / {item['days_ago']}일 전 / {item['text']}")
    next_actions = [
        "가장 최근 언급 계정부터 원문 맥락 확인",
        "같은 종목이 뉴스/공시에도 같이 나오는지 교차검증",
        "소셜 반응은 촉매 탐지용으로만 보고 가격/거래량 확인",
    ]
    summary = f"seed 계정 기준 Threads 최근 반응 {len(hits)}건을 찾았습니다: {query}"
    return summary, focus, next_actions


def build_us_social_response(
    mode: str,
    payload: dict[str, Any],
    runtime_context: dict[str, Any],
    request_text: str,
    symbols: list[str],
    social_search_func=search_threads_seed_accounts,
) -> dict[str, Any] | None:
    if mode == "threads_view_scan":
        scan_report = build_threads_view_scan_report(
            accounts=payload.get("threads_accounts") or runtime_context.get("threads_accounts"),
            profile_markdown_by_handle=payload.get("threads_profile_markdown") or runtime_context.get("threads_profile_markdown"),
            max_accounts=int(payload.get("max_accounts") if payload.get("max_accounts") is not None else runtime_context.get("max_accounts") or 0),
            account_offset=int(payload.get("account_offset") or runtime_context.get("threads_account_offset") or 0),
            max_posts_per_account=int(payload.get("max_posts_per_account") or runtime_context.get("max_posts_per_account") or 8),
            fetch_live=bool(payload.get("fetch_live") if payload.get("fetch_live") is not None else runtime_context.get("threads_fetch_live", True)),
            account_source=str(payload.get("account_source") or runtime_context.get("account_source") or "seed_high_signal"),
            cache_dir=payload.get("cache_dir") or runtime_context.get("threads_cache_dir"),
            cache_ttl_seconds=float(payload.get("cache_ttl_seconds") or runtime_context.get("threads_cache_ttl_seconds") or 0),
            delay_seconds=float(payload.get("delay_seconds") or runtime_context.get("threads_delay_seconds") or 0),
            max_consecutive_rate_limits=int(payload.get("max_consecutive_rate_limits") or runtime_context.get("threads_max_consecutive_rate_limits") or 2),
            timeout_seconds=int(payload.get("timeout_seconds") or runtime_context.get("threads_timeout_seconds") or 30),
        )
        artifact_paths = None
        if payload.get("save_artifacts") or runtime_context.get("threads_save_artifacts"):
            artifact_paths = save_threads_view_scan_artifacts(
                scan_report,
                output_dir=payload.get("output_dir") or runtime_context.get("threads_output_dir") or None or Path(__file__).resolve().parents[2] / "data",
                date_label=payload.get("date_label") or runtime_context.get("date_label"),
            )
            scan_report["artifact_paths"] = {key: str(value) for key, value in artifact_paths.items()}
        if payload.get("save_slow_state") or runtime_context.get("threads_save_slow_state"):
            state_path = save_threads_slow_state(
                scan_report,
                state_path=payload.get("slow_state_path") or runtime_context.get("threads_slow_state_path") or Path(__file__).resolve().parents[2] / "data" / "threads_profile_cache" / "slow_state.json",
                batch_size=int(payload.get("max_accounts") if payload.get("max_accounts") is not None else runtime_context.get("max_accounts") or scan_report.get("account_count") or 0),
                accounts_total=runtime_context.get("threads_accounts_total") or payload.get("accounts_total"),
                note=payload.get("slow_state_note") or runtime_context.get("threads_slow_state_note"),
            )
            scan_report["slow_state_path"] = str(state_path)
        return {
            "agent": "stock-research-agent",
            "mode": mode,
            "summary": scan_report["summary"],
            "symbols": [item["symbol"] for item in scan_report.get("symbol_clusters", [])[:8]],
            "focus": scan_report["focus_lines"],
            "next_actions": scan_report["next_actions"],
            "features": list(dict.fromkeys([*runtime_context.get("features", []), "threads_view_scan", "threads_persona_mining"])),
            "data": {"threads_view_scan": scan_report},
        }



    if mode == "social_search":
        summary, focus, next_actions = build_social_search_payload(request_text, symbols, search_func=social_search_func)
        return {
            "agent": "stock-research-agent",
            "mode": mode,
            "summary": summary,
            "symbols": symbols,
            "focus": focus,
            "next_actions": next_actions,
            "features": runtime_context.get("features", []),
        }



    return None
