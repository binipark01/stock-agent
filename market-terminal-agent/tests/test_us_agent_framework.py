from __future__ import annotations

from src.us.agents import (
    PipelineStep,
    ThemeLeaderCandidate,
    USAgentMemoryEntry,
    USAgentMemoryLog,
    USAgentPipeline,
    USAgentState,
    memory_entries_from_theme_decisions,
    normalize_rating,
    parse_agent_json,
    state_from_sector_strength_response,
    theme_decisions_from_sector_strength_response,
    run_bounded_investment_debate,
)
from src.us.agents.json_contract import AgentJsonError
from src.us.agents.schemas import ThemeDecision, ThemeLeaderDecision, render_theme_decision_for_discord


def test_agent_json_parser_recovers_fenced_and_wrapped_json() -> None:
    parsed = parse_agent_json(
        """
        결과입니다.
        ```json
        {"agent":"research_manager","rating":"Overweight","rationale":"news and volume"}
        ```
        """,
        expected_agent="research_manager",
    )
    assert parsed["rating"] == "Overweight"

    wrapped = parse_agent_json('prefix {"agent":"x","value":{"nested":true}} suffix', expected_agent="x")
    assert wrapped["value"]["nested"] is True


def test_agent_json_parser_rejects_wrong_agent() -> None:
    try:
        parse_agent_json('{"agent":"bear_researcher"}', expected_agent="bull_researcher")
    except AgentJsonError as exc:
        assert "unexpected agent" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("wrong agent name should fail")


def test_schema_normalization_and_prompt_payload() -> None:
    assert normalize_rating("outperform") == "Overweight"
    candidate = ThemeLeaderCandidate.from_mapping(
        {
            "symbol": "nvda",
            "company": "NVIDIA",
            "price": "120.5",
            "pct_change": "3.2",
            "trading_value": 1000000,
            "theme_anchor": "true",
        }
    )
    assert candidate.symbol == "NVDA"
    assert candidate.theme_anchor is True
    payload = candidate.to_prompt_dict()
    assert payload["price"] == 120.5
    assert "news" not in payload


def test_state_prompt_payload_groups_theme_candidates() -> None:
    state = USAgentState(mode="theme_alert", request="AI leaders")
    state.add_theme_candidates(
        "ai_infra",
        [
            ThemeLeaderCandidate(symbol="NVDA", pct_change=3.1),
            ThemeLeaderCandidate(symbol="AVGO", pct_change=2.0),
        ],
    )
    payload = state.to_prompt_payload()
    assert payload["theme_candidates"]["ai_infra"][0]["symbol"] == "NVDA"
    assert payload["mode"] == "theme_alert"


def test_memory_log_appends_and_filters_recent_theme(tmp_path) -> None:
    memory = USAgentMemoryLog(tmp_path / "us_memory.jsonl")
    memory.append(USAgentMemoryEntry(theme="AI", leaders=["nvda"], thesis="data center demand"))
    memory.append(USAgentMemoryEntry(theme="Energy", leaders=["xom"], thesis="oil"))
    memory.append(USAgentMemoryEntry(theme="AI", leaders=["avgo"], thesis="networking"))

    recent_ai = memory.recent_for_theme("ai", limit=2)
    assert [entry["leaders"][0] for entry in recent_ai] == ["NVDA", "AVGO"]
    assert recent_ai[0]["signature"] != recent_ai[1]["signature"]


def test_bounded_debate_records_bull_bear_then_manager() -> None:
    state = USAgentState(mode="theme_alert")

    def bull(agent_state, history):
        return {"case": "NVDA has theme leadership", "seen": len(history)}

    def bear(agent_state, history):
        return {"case": "move may be crowded", "seen": len(history)}

    def manager(agent_state, history):
        return {"rating": "Overweight", "turns": len(history)}

    debate = run_bounded_investment_debate(
        state,
        bull_agent=bull,
        bear_agent=bear,
        manager_agent=manager,
        rounds=2,
    )
    assert [turn["speaker"] for turn in debate["history"]] == ["bull", "bear", "bull", "bear"]
    assert debate["manager"]["turns"] == 4
    assert state.intermediate["investment_debate"] == debate


def test_pipeline_runs_named_steps() -> None:
    state = USAgentState(mode="theme_alert")

    def mark_market(agent_state):
        agent_state.market_snapshot["regime"] = "risk_on"
        return agent_state

    result = USAgentPipeline([PipelineStep("market", mark_market)]).run(state)
    assert result.completed_steps == ["market"]
    assert result.state.market_snapshot["regime"] == "risk_on"
    assert result.errors == []


def test_discord_renderer_uses_theme_decision_contract() -> None:
    decision = ThemeDecision(
        key="semis",
        label="반도체",
        strength="strong",
        leaders=[
            ThemeLeaderDecision(
                symbol="NVDA",
                reason="AI accelerator demand",
                catalysts=["earnings revision"],
                risks=["valuation"],
            )
        ],
        thesis="AI capex theme remains bid",
    )
    rendered = render_theme_decision_for_discord(decision)
    assert "**반도체**" in rendered
    assert "- 대장주: NVDA" in rendered
    assert "AI accelerator demand" in rendered


def test_theme_alert_adapter_builds_state_from_sector_response() -> None:
    response = {
        "mode": "sector_strength",
        "summary": "sector summary",
        "focus": ["market line"],
        "data": {
            "sector_strength": {
                "theme_baskets": [
                    {
                        "key": "semiconductors",
                        "name": "반도체",
                        "leader_candidates": [
                            {
                                "symbol": "NVDA",
                                "price": 120,
                                "pct_change": 3.1,
                                "leader_score_basis": {"theme_leader_rank": 100.0},
                            }
                        ],
                    }
                ],
                "strong_themes": [],
                "weak_themes": [],
                "theme_news": {"semiconductors": "AI data center demand"},
                "symbol_issues": {"NVDA": "earnings revision"},
            }
        },
    }
    state = state_from_sector_strength_response(response, request="theme alert")
    payload = state.to_prompt_payload()
    candidate = payload["theme_candidates"]["semiconductors"][0]
    assert candidate["symbol"] == "NVDA"
    assert candidate["theme_anchor"] is True
    assert candidate["news"] == "AI data center demand"
    assert candidate["issue"] == "earnings revision"


def test_theme_alert_adapter_builds_decisions_and_memory_entries() -> None:
    response = {
        "mode": "sector_strength",
        "data": {
            "sector_strength": {
                "strong_themes": [
                    {
                        "key": "ai_infra",
                        "name": "AI 인프라",
                        "leaders": [{"symbol": "NVDA"}, {"symbol": "AVGO"}],
                        "llm_leader_rerank": {"reason": "대표성과 거래대금이 같이 확인됨"},
                    }
                ],
                "weak_themes": [],
            }
        },
    }
    decisions = theme_decisions_from_sector_strength_response(response)
    assert decisions[0].label == "AI 인프라"
    assert [leader.symbol for leader in decisions[0].leaders] == ["NVDA", "AVGO"]

    state = USAgentState(mode="theme_alert")
    entries = memory_entries_from_theme_decisions(state, decisions, rating="Overweight")
    assert entries[0].theme == "AI 인프라"
    assert entries[0].leaders == ["NVDA", "AVGO"]
    assert entries[0].rating == "Overweight"
