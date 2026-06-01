from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


Rating = Literal["Buy", "Overweight", "Hold", "Underweight", "Sell"]
TradeAction = Literal["Buy", "Hold", "Sell"]
RiskDecision = Literal["approve", "downsize", "defer", "reject"]
Confidence = Literal["low", "medium", "high"]

RATING_SCALE: tuple[Rating, ...] = ("Buy", "Overweight", "Hold", "Underweight", "Sell")
TRADE_ACTIONS: tuple[TradeAction, ...] = ("Buy", "Hold", "Sell")
RISK_DECISIONS: tuple[RiskDecision, ...] = ("approve", "downsize", "defer", "reject")
CONFIDENCE_LEVELS: tuple[Confidence, ...] = ("low", "medium", "high")


def _clean_symbol(value: Any) -> str:
    return str(value or "").strip().upper()


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "y", "on"}


def _clean_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = [item.strip() for item in value.split("|")]
        return [item for item in parts if item]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _drop_empty(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if value is not None and value != "" and value != [] and value != {}
    }


_RATING_ALIASES: dict[str, Rating] = {
    "buy": "Buy",
    "strong buy": "Buy",
    "overweight": "Overweight",
    "outperform": "Overweight",
    "hold": "Hold",
    "neutral": "Hold",
    "underweight": "Underweight",
    "underperform": "Underweight",
    "sell": "Sell",
}


def normalize_rating(value: Any, default: Rating = "Hold") -> Rating:
    text = str(value or "").strip()
    if text in RATING_SCALE:
        return text  # type: ignore[return-value]
    lowered = text.lower().replace("_", " ").replace("-", " ")
    return _RATING_ALIASES.get(lowered, default)


_ACTION_ALIASES: dict[str, TradeAction] = {
    "buy": "Buy",
    "add": "Buy",
    "long": "Buy",
    "hold": "Hold",
    "wait": "Hold",
    "watch": "Hold",
    "sell": "Sell",
    "trim": "Sell",
    "short": "Sell",
}


def normalize_trade_action(value: Any, default: TradeAction = "Hold") -> TradeAction:
    text = str(value or "").strip()
    if text in TRADE_ACTIONS:
        return text  # type: ignore[return-value]
    lowered = text.lower().replace("_", " ").replace("-", " ")
    return _ACTION_ALIASES.get(lowered, default)


def normalize_risk_decision(value: Any, default: RiskDecision = "defer") -> RiskDecision:
    text = str(value or "").strip().lower().replace("_", "-")
    aliases: dict[str, RiskDecision] = {
        "approve": "approve",
        "pass": "approve",
        "ok": "approve",
        "downsize": "downsize",
        "reduce": "downsize",
        "trim": "downsize",
        "defer": "defer",
        "wait": "defer",
        "hold": "defer",
        "reject": "reject",
        "block": "reject",
    }
    return aliases.get(text, default)


def normalize_confidence(value: Any, default: Confidence = "medium") -> Confidence:
    text = str(value or "").strip().lower()
    if text in CONFIDENCE_LEVELS:
        return text  # type: ignore[return-value]
    return default


@dataclass(frozen=True)
class ThemeLeaderCandidate:
    symbol: str
    company: str = ""
    theme: str = ""
    price: float | None = None
    pct_change: float | None = None
    trading_value: float | None = None
    volume_vs_previous_pct: float | None = None
    trading_value_vs_previous_pct: float | None = None
    theme_anchor: bool = False
    rule_score: float | None = None
    news: str = ""
    issue: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "ThemeLeaderCandidate":
        return cls(
            symbol=_clean_symbol(payload.get("symbol") or payload.get("ticker")),
            company=_clean_text(payload.get("company") or payload.get("name")),
            theme=_clean_text(payload.get("theme") or payload.get("theme_key")),
            price=_as_float(payload.get("price")),
            pct_change=_as_float(payload.get("pct_change") or payload.get("change_pct")),
            trading_value=_as_float(payload.get("trading_value") or payload.get("dollar_volume")),
            volume_vs_previous_pct=_as_float(payload.get("volume_vs_previous_pct")),
            trading_value_vs_previous_pct=_as_float(payload.get("trading_value_vs_previous_pct")),
            theme_anchor=_as_bool(payload.get("theme_anchor")),
            rule_score=_as_float(payload.get("rule_score") or payload.get("leader_score")),
            news=_clean_text(payload.get("news")),
            issue=_clean_text(payload.get("issue") or payload.get("catalyst")),
            metadata=dict(payload.get("metadata") or {}),
        )

    def to_prompt_dict(self) -> dict[str, Any]:
        return _drop_empty(
            {
                "symbol": self.symbol,
                "company": self.company,
                "theme": self.theme,
                "price": self.price,
                "pct_change": self.pct_change,
                "trading_value": self.trading_value,
                "volume_vs_previous_pct": self.volume_vs_previous_pct,
                "trading_value_vs_previous_pct": self.trading_value_vs_previous_pct,
                "theme_anchor": self.theme_anchor,
                "rule_score": self.rule_score,
                "news": self.news,
                "issue": self.issue,
                "metadata": self.metadata,
            }
        )


@dataclass(frozen=True)
class ThemeLeaderDecision:
    symbol: str
    company: str = ""
    role: str = ""
    confidence: Confidence = "medium"
    reason: str = ""
    catalysts: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    score: float | None = None

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "ThemeLeaderDecision":
        return cls(
            symbol=_clean_symbol(payload.get("symbol") or payload.get("ticker")),
            company=_clean_text(payload.get("company") or payload.get("name")),
            role=_clean_text(payload.get("role") or payload.get("theme_role")),
            confidence=normalize_confidence(payload.get("confidence")),
            reason=_clean_text(payload.get("reason") or payload.get("leader_reason")),
            catalysts=_clean_string_list(payload.get("catalysts") or payload.get("news")),
            risks=_clean_string_list(payload.get("risks")),
            score=_as_float(payload.get("score")),
        )

    def to_prompt_dict(self) -> dict[str, Any]:
        return _drop_empty(
            {
                "symbol": self.symbol,
                "company": self.company,
                "role": self.role,
                "confidence": self.confidence,
                "reason": self.reason,
                "catalysts": self.catalysts,
                "risks": self.risks,
                "score": self.score,
            }
        )


@dataclass(frozen=True)
class ThemeDecision:
    key: str
    label: str = ""
    strength: str = "neutral"
    leaders: list[ThemeLeaderDecision] = field(default_factory=list)
    secondary_symbols: list[str] = field(default_factory=list)
    thesis: str = ""
    news: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "ThemeDecision":
        leaders: list[ThemeLeaderDecision] = []
        raw_leaders = payload.get("leaders") or []
        if isinstance(raw_leaders, list):
            for item in raw_leaders:
                if isinstance(item, dict):
                    leaders.append(ThemeLeaderDecision.from_mapping(item))
                else:
                    leaders.append(ThemeLeaderDecision(symbol=_clean_symbol(item)))
        return cls(
            key=_clean_text(payload.get("key") or payload.get("theme") or payload.get("label")),
            label=_clean_text(payload.get("label") or payload.get("theme")),
            strength=_clean_text(payload.get("strength") or "neutral"),
            leaders=leaders,
            secondary_symbols=[_clean_symbol(item) for item in _clean_string_list(payload.get("secondary_symbols"))],
            thesis=_clean_text(payload.get("thesis") or payload.get("reason")),
            news=_clean_string_list(payload.get("news") or payload.get("key_news")),
            risks=_clean_string_list(payload.get("risks") or payload.get("risk_notes")),
        )

    def to_prompt_dict(self) -> dict[str, Any]:
        return _drop_empty(
            {
                "key": self.key,
                "label": self.label,
                "strength": self.strength,
                "leaders": [leader.to_prompt_dict() for leader in self.leaders],
                "secondary_symbols": self.secondary_symbols,
                "thesis": self.thesis,
                "news": self.news,
                "risks": self.risks,
            }
        )


@dataclass(frozen=True)
class ResearchPlan:
    rating: Rating = "Hold"
    rationale: str = ""
    strategic_actions: list[str] = field(default_factory=list)
    confidence: Confidence = "medium"

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "ResearchPlan":
        return cls(
            rating=normalize_rating(payload.get("rating") or payload.get("recommendation")),
            rationale=_clean_text(payload.get("rationale") or payload.get("reasoning")),
            strategic_actions=_clean_string_list(payload.get("strategic_actions") or payload.get("actions")),
            confidence=normalize_confidence(payload.get("confidence")),
        )


@dataclass(frozen=True)
class TradePlan:
    action: TradeAction = "Hold"
    reasoning: str = ""
    entry_zone: str = ""
    invalidation: str = ""
    sizing_guide: str = ""

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "TradePlan":
        return cls(
            action=normalize_trade_action(payload.get("action")),
            reasoning=_clean_text(payload.get("reasoning") or payload.get("rationale")),
            entry_zone=_clean_text(payload.get("entry_zone") or payload.get("entry_price")),
            invalidation=_clean_text(payload.get("invalidation") or payload.get("stop_loss")),
            sizing_guide=_clean_text(payload.get("sizing_guide") or payload.get("position_sizing")),
        )


@dataclass(frozen=True)
class PortfolioRiskReview:
    decision: RiskDecision = "defer"
    risk_notes: list[str] = field(default_factory=list)
    final_summary: str = ""

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "PortfolioRiskReview":
        return cls(
            decision=normalize_risk_decision(payload.get("decision")),
            risk_notes=_clean_string_list(payload.get("risk_notes") or payload.get("risks")),
            final_summary=_clean_text(payload.get("final_summary") or payload.get("summary")),
        )


def render_theme_decision_for_discord(decision: ThemeDecision) -> str:
    label = decision.label or decision.key
    lines = [f"**{label}**", f"- 강도: {decision.strength}"]
    if decision.leaders:
        leaders = ", ".join(leader.symbol for leader in decision.leaders if leader.symbol)
        lines.append(f"- 대장주: {leaders}")
    if decision.thesis:
        lines.append(f"- 판단: {decision.thesis}")
    for leader in decision.leaders:
        if not leader.symbol:
            continue
        detail_parts = []
        if leader.reason:
            detail_parts.append(leader.reason)
        if leader.catalysts:
            detail_parts.append("촉매: " + " / ".join(leader.catalysts))
        if leader.risks:
            detail_parts.append("리스크: " + " / ".join(leader.risks))
        if detail_parts:
            lines.append(f"  - {leader.symbol}: {'; '.join(detail_parts)}")
    if decision.news:
        lines.append("- 뉴스: " + " / ".join(decision.news))
    if decision.risks:
        lines.append("- 리스크: " + " / ".join(decision.risks))
    return "\n".join(lines)
