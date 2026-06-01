from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def decision_signature(theme: str, leaders: list[str], thesis: str = "") -> str:
    source = json.dumps(
        {
            "theme": str(theme or "").strip().lower(),
            "leaders": [str(item or "").strip().upper() for item in leaders],
            "thesis": str(thesis or "").strip(),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class USAgentMemoryEntry:
    theme: str
    leaders: list[str]
    thesis: str = ""
    rating: str = "Hold"
    confidence: str = "medium"
    run_id: str = ""
    mode: str = "us_agent"
    timestamp: str = field(default_factory=_now_iso)
    source: str = "us_market_agent"
    outcome: str = "pending"
    extra: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        leaders = [str(item or "").strip().upper() for item in self.leaders if str(item or "").strip()]
        return {
            "timestamp": self.timestamp,
            "run_id": self.run_id,
            "mode": self.mode,
            "source": self.source,
            "theme": self.theme,
            "leaders": leaders,
            "thesis": self.thesis,
            "rating": self.rating,
            "confidence": self.confidence,
            "outcome": self.outcome,
            "signature": decision_signature(self.theme, leaders, self.thesis),
            "extra": self.extra,
        }

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> "USAgentMemoryEntry":
        leaders = payload.get("leaders") if isinstance(payload.get("leaders"), list) else []
        return cls(
            timestamp=str(payload.get("timestamp") or _now_iso()),
            run_id=str(payload.get("run_id") or ""),
            mode=str(payload.get("mode") or "us_agent"),
            source=str(payload.get("source") or "us_market_agent"),
            theme=str(payload.get("theme") or ""),
            leaders=[str(item).strip().upper() for item in leaders if str(item).strip()],
            thesis=str(payload.get("thesis") or ""),
            rating=str(payload.get("rating") or "Hold"),
            confidence=str(payload.get("confidence") or "medium"),
            outcome=str(payload.get("outcome") or "pending"),
            extra=dict(payload.get("extra") or {}),
        )


class USAgentMemoryLog:
    """Append-only JSONL memory for US market agent decisions."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, entry: USAgentMemoryEntry) -> dict[str, Any]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = entry.to_json()
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        return payload

    def load(self, *, limit: int | None = None) -> list[USAgentMemoryEntry]:
        if not self.path.exists():
            return []
        entries: list[USAgentMemoryEntry] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                entries.append(USAgentMemoryEntry.from_json(payload))
        if limit is not None and limit >= 0:
            return entries[-limit:]
        return entries

    def recent_for_theme(self, theme: str, *, limit: int = 5) -> list[dict[str, Any]]:
        normalized = str(theme or "").strip().lower()
        matches = [entry for entry in self.load() if entry.theme.strip().lower() == normalized]
        return [entry.to_json() for entry in matches[-max(0, limit) :]]

    def build_context(self, *, theme: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
        if theme:
            return self.recent_for_theme(theme, limit=limit)
        return [entry.to_json() for entry in self.load(limit=limit)]
