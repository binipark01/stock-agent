import json
from pathlib import Path


PROMPT_ROOT = Path(__file__).resolve().parents[1] / "prompts" / "us_agents"
EXPECTED_AGENTS = {
    "theme_leader_reranker",
    "market_regime_analyst",
    "technical_signal_analyst",
    "news_catalyst_analyst",
    "bull_researcher",
    "bear_researcher",
    "research_manager",
    "trade_plan_builder",
    "portfolio_risk_manager",
    "quant_signal_guard",
}


def _render_for_json_validation(text: str) -> str:
    return (
        text.replace("{{REQUEST_PAYLOAD_JSON}}", "{}")
        .replace("{{MIN_LEADERS}}", "3")
        .replace("{{MAX_LEADERS}}", "5")
    )


def test_us_agent_prompt_files_are_present_and_split() -> None:
    agents = {path.name for path in PROMPT_ROOT.iterdir() if path.is_dir()}
    assert EXPECTED_AGENTS.issubset(agents)
    for agent in EXPECTED_AGENTS:
        system = PROMPT_ROOT / agent / "system.md"
        user = PROMPT_ROOT / agent / "user.md"
        assert system.exists(), agent
        assert user.exists(), agent
        assert system.read_text(encoding="utf-8").strip()
        assert user.read_text(encoding="utf-8").strip()


def test_us_agent_user_prompts_render_to_json_contracts() -> None:
    for agent in EXPECTED_AGENTS:
        user = (PROMPT_ROOT / agent / "user.md").read_text(encoding="utf-8")
        payload = json.loads(_render_for_json_validation(user))
        assert payload["agent"] == agent
        assert payload["task"]
        assert isinstance(payload["rules"], list) and payload["rules"]
        assert isinstance(payload["return_schema"], dict)
        assert payload["input"] == {}


def test_us_agent_prompts_do_not_contain_local_secret_names() -> None:
    forbidden = ("DISCORD_BOT_TOKEN", "TELEGRAM_BOT_TOKEN", "Authorization", "Bearer ")
    for path in PROMPT_ROOT.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{token} leaked in {path}"
