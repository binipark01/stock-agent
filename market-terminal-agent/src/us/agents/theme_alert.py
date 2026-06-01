from __future__ import annotations

from typing import Any, Iterable

from .memory import USAgentMemoryEntry, USAgentMemoryLog
from .schemas import ThemeDecision, ThemeLeaderCandidate, ThemeLeaderDecision, normalize_rating
from .state import USAgentState


def _sector_report(response: dict[str, Any]) -> dict[str, Any]:
    data = response.get("data") if isinstance(response.get("data"), dict) else {}
    report = data.get("sector_strength") if isinstance(data.get("sector_strength"), dict) else {}
    return report if isinstance(report, dict) else {}


def _row_key(row: dict[str, Any]) -> str:
    return str(row.get("key") or row.get("name") or row.get("label") or "").strip()


def _iter_unique_theme_rows(report: dict[str, Any]) -> Iterable[dict[str, Any]]:
    seen: set[str] = set()
    for group_key in ("theme_baskets", "strong_themes", "weak_themes"):
        rows = report.get(group_key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            key = _row_key(row)
            if not key or key in seen:
                continue
            seen.add(key)
            yield row


def _candidate_from_row_item(
    item: dict[str, Any],
    *,
    theme_key: str,
    theme_news: str = "",
    symbol_issues: dict[str, str] | None = None,
) -> ThemeLeaderCandidate:
    symbol_issues = symbol_issues or {}
    basis = item.get("leader_score_basis") if isinstance(item.get("leader_score_basis"), dict) else {}
    symbol = str(item.get("symbol") or item.get("ticker") or "").strip().upper()
    enriched = {
        **item,
        "theme": theme_key,
        "theme_anchor": bool(basis.get("theme_leader_rank")),
        "news": item.get("news") or theme_news,
        "issue": item.get("issue") or symbol_issues.get(symbol, ""),
    }
    return ThemeLeaderCandidate.from_mapping(enriched)


def state_from_sector_strength_response(
    response: dict[str, Any],
    *,
    request: str = "",
    memory_context: list[dict[str, Any]] | None = None,
) -> USAgentState:
    """Convert the existing macro-style sector response into agent state."""

    report = _sector_report(response)
    state = USAgentState(mode="theme_alert", request=request, memory_context=memory_context or [])
    state.market_snapshot = {
        "summary": response.get("summary"),
        "focus": response.get("focus") if isinstance(response.get("focus"), list) else [],
        "mode": response.get("mode"),
    }
    state.sector_snapshot = {
        "strong_theme_count": len(report.get("strong_themes") or []),
        "weak_theme_count": len(report.get("weak_themes") or []),
        "llm_leader_rerank": report.get("llm_leader_rerank"),
    }

    theme_news_lookup = report.get("theme_news") if isinstance(report.get("theme_news"), dict) else {}
    symbol_issues = report.get("symbol_issues") if isinstance(report.get("symbol_issues"), dict) else {}

    for row in _iter_unique_theme_rows(report):
        key = _row_key(row)
        candidate_rows = row.get("leader_candidates")
        if not isinstance(candidate_rows, list) or not candidate_rows:
            candidate_rows = row.get("leaders") if isinstance(row.get("leaders"), list) else []
        theme_news = str(theme_news_lookup.get(key) or theme_news_lookup.get(row.get("name")) or "").strip()
        candidates = [
            _candidate_from_row_item(item, theme_key=key, theme_news=theme_news, symbol_issues=symbol_issues)
            for item in candidate_rows
            if isinstance(item, dict) and (item.get("symbol") or item.get("ticker"))
        ]
        state.add_theme_candidates(key, candidates)

    return state


def theme_decisions_from_sector_strength_response(response: dict[str, Any]) -> list[ThemeDecision]:
    """Build structured theme decisions from the current strong/weak theme rows."""

    report = _sector_report(response)
    theme_news_lookup = report.get("theme_news") if isinstance(report.get("theme_news"), dict) else {}
    symbol_issues = report.get("symbol_issues") if isinstance(report.get("symbol_issues"), dict) else {}
    decisions: list[ThemeDecision] = []

    for group_key, default_strength in (("strong_themes", "strong"), ("weak_themes", "weak")):
        rows = report.get(group_key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            key = _row_key(row)
            if not key:
                continue
            leaders: list[ThemeLeaderDecision] = []
            for item in row.get("leaders") or []:
                if not isinstance(item, dict):
                    continue
                symbol = str(item.get("symbol") or item.get("ticker") or "").strip().upper()
                if not symbol:
                    continue
                leaders.append(
                    ThemeLeaderDecision(
                        symbol=symbol,
                        company=str(item.get("company") or item.get("name") or "").strip(),
                        role="theme_leader",
                        reason=str(item.get("reason") or item.get("leader_reason") or "").strip(),
                        catalysts=[
                            value
                            for value in (
                                str(item.get("news") or "").strip(),
                                str(item.get("issue") or symbol_issues.get(symbol, "")).strip(),
                            )
                            if value
                        ],
                    )
                )
            rerank = row.get("llm_leader_rerank") if isinstance(row.get("llm_leader_rerank"), dict) else {}
            theme_news = str(theme_news_lookup.get(key) or theme_news_lookup.get(row.get("name")) or "").strip()
            decisions.append(
                ThemeDecision(
                    key=key,
                    label=str(row.get("name") or key).strip(),
                    strength=str(row.get("status") or default_strength),
                    leaders=leaders,
                    thesis=str(rerank.get("reason") or theme_news or "").strip(),
                    news=[theme_news] if theme_news else [],
                )
            )
    return decisions


def memory_entries_from_theme_decisions(
    state: USAgentState,
    decisions: list[ThemeDecision],
    *,
    rating: str = "Hold",
    confidence: str = "medium",
) -> list[USAgentMemoryEntry]:
    entries: list[USAgentMemoryEntry] = []
    normalized_rating = normalize_rating(rating)
    for decision in decisions:
        if not decision.leaders:
            continue
        entries.append(
            USAgentMemoryEntry(
                run_id=state.run_id,
                mode=state.mode,
                theme=decision.label or decision.key,
                leaders=[leader.symbol for leader in decision.leaders],
                thesis=decision.thesis,
                rating=normalized_rating,
                confidence=confidence,
                extra={
                    "strength": decision.strength,
                    "news": decision.news,
                    "risks": decision.risks,
                },
            )
        )
    return entries


def record_theme_decisions(
    memory: USAgentMemoryLog,
    state: USAgentState,
    decisions: list[ThemeDecision],
    *,
    rating: str = "Hold",
    confidence: str = "medium",
) -> list[dict[str, Any]]:
    return [
        memory.append(entry)
        for entry in memory_entries_from_theme_decisions(
            state,
            decisions,
            rating=rating,
            confidence=confidence,
        )
    ]
