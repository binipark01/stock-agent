from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .state import USAgentState


AgentStep = Callable[[USAgentState], USAgentState]
DebateAgent = Callable[[USAgentState, list[dict[str, Any]]], dict[str, Any]]
ManagerAgent = Callable[[USAgentState, list[dict[str, Any]]], dict[str, Any]]


@dataclass(frozen=True)
class PipelineStep:
    name: str
    run: AgentStep


@dataclass
class PipelineResult:
    state: USAgentState
    completed_steps: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class USAgentPipeline:
    """Minimal state-passing pipeline for the US market agent."""

    def __init__(self, steps: list[PipelineStep]) -> None:
        self.steps = steps

    def run(self, state: USAgentState) -> PipelineResult:
        result = PipelineResult(state=state)
        for step in self.steps:
            try:
                state = step.run(state)
            except Exception as exc:  # pragma: no cover - caller decides recovery policy
                message = f"{step.name}: {type(exc).__name__}: {exc}"
                state.add_warning(message)
                result.errors.append(message)
                break
            result.completed_steps.append(step.name)
            result.state = state
        return result


def run_bounded_investment_debate(
    state: USAgentState,
    *,
    bull_agent: DebateAgent,
    bear_agent: DebateAgent,
    manager_agent: ManagerAgent,
    rounds: int = 1,
) -> dict[str, Any]:
    """Run a finite Bull/Bear debate and return the manager synthesis."""

    safe_rounds = max(1, int(rounds))
    history: list[dict[str, Any]] = []
    for round_index in range(safe_rounds):
        bull_payload = dict(bull_agent(state, history) or {})
        bull_payload.setdefault("speaker", "bull")
        bull_payload.setdefault("round", round_index + 1)
        history.append(bull_payload)

        bear_payload = dict(bear_agent(state, history) or {})
        bear_payload.setdefault("speaker", "bear")
        bear_payload.setdefault("round", round_index + 1)
        history.append(bear_payload)

    manager_payload = dict(manager_agent(state, history) or {})
    debate_payload = {
        "rounds": safe_rounds,
        "history": history,
        "manager": manager_payload,
    }
    state.intermediate["investment_debate"] = debate_payload
    return debate_payload
