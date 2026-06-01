from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .schemas import ThemeLeaderCandidate


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class USAgentState:
    """Shared state passed through the US market agent pipeline."""

    mode: str
    request: str = ""
    run_id: str = field(default_factory=lambda: uuid4().hex)
    created_at: str = field(default_factory=utc_now_iso)
    symbols: list[str] = field(default_factory=list)
    market_snapshot: dict[str, Any] = field(default_factory=dict)
    sector_snapshot: dict[str, Any] = field(default_factory=dict)
    theme_candidates: dict[str, list[ThemeLeaderCandidate]] = field(default_factory=dict)
    news_items: list[dict[str, Any]] = field(default_factory=list)
    technical_snapshots: dict[str, dict[str, Any]] = field(default_factory=dict)
    memory_context: list[dict[str, Any]] = field(default_factory=list)
    intermediate: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def add_warning(self, message: str) -> None:
        message = str(message or "").strip()
        if message:
            self.warnings.append(message)

    def set_output(self, key: str, value: Any) -> None:
        self.outputs[key] = value

    def add_theme_candidates(self, theme: str, candidates: list[ThemeLeaderCandidate]) -> None:
        key = str(theme or "").strip()
        if not key:
            self.add_warning("theme candidate batch skipped because theme key was empty")
            return
        self.theme_candidates[key] = candidates

    def to_prompt_payload(self, *, max_candidates_per_theme: int = 8) -> dict[str, Any]:
        theme_payload: dict[str, list[dict[str, Any]]] = {}
        for theme, candidates in self.theme_candidates.items():
            theme_payload[theme] = [
                candidate.to_prompt_dict() for candidate in candidates[: max(1, max_candidates_per_theme)]
            ]
        return {
            "run_id": self.run_id,
            "created_at": self.created_at,
            "mode": self.mode,
            "request": self.request,
            "symbols": self.symbols,
            "market_snapshot": self.market_snapshot,
            "sector_snapshot": self.sector_snapshot,
            "theme_candidates": theme_payload,
            "news_items": self.news_items,
            "technical_snapshots": self.technical_snapshots,
            "memory_context": self.memory_context,
            "intermediate": self.intermediate,
            "outputs": self.outputs,
            "warnings": self.warnings,
        }
