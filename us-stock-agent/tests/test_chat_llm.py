import unittest
import tempfile
from pathlib import Path

from src.chat_llm import LLMResult, build_llm_chat_response, resolve_omx_model, resolve_settings, should_use_llm_chat


class ChatLlmTest(unittest.TestCase):
    def test_short_general_chat_uses_llm_chat(self):
        self.assertTrue(should_use_llm_chat("야"))
        self.assertTrue(should_use_llm_chat("안녕"))

    def test_stock_like_request_does_not_use_llm_chat(self):
        self.assertFalse(should_use_llm_chat("NVDA 체크해줘"))
        self.assertFalse(should_use_llm_chat("오늘 미국장 체크포인트 정리해줘"))
        self.assertFalse(should_use_llm_chat("나스닥 뭐 봐야 해?"))

    def test_chat_response_uses_llm_result(self):
        def fake_llm(prompt, cwd=None, env=None):
            self.assertIn("user: 야", prompt)
            self.assertIsNone(env)
            return LLMResult(ok=True, provider="codex", text="어, 말해봐.", command="codex exec", model="test-model")

        response = build_llm_chat_response("야", history=[{"role": "user", "content": "야"}], llm_func=fake_llm)

        self.assertEqual(response["mode"], "chat")
        self.assertEqual(response["summary"], "어, 말해봐.")
        self.assertIn("omx_codex", response["features"])
        self.assertIn("reasoning_effort", response)

    def test_codex_settings_follow_omx_model_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / "config.toml").write_text(
                'model = "from-codex-config"\nmodel_provider = "cheapRouter"\nmodel_reasoning_effort = "high"\n',
                encoding="utf-8",
            )
            env = {
                "CODEX_HOME": str(home),
                "OMX_DEFAULT_FRONTIER_MODEL": "",
                "OMX_DEFAULT_STANDARD_MODEL": "",
                "OMX_DEFAULT_SPARK_MODEL": "",
                "OMX_SPARK_MODEL": "",
            }

            self.assertEqual(resolve_omx_model(env), ("from-codex-config", "config.toml model"))
            settings = resolve_settings(env)
            self.assertEqual(settings.provider, "codex")
            self.assertEqual(settings.model, "from-codex-config")
            self.assertEqual(settings.model_provider, "cheapRouter")
            self.assertEqual(settings.reasoning_effort, "high")

    def test_model_class_and_override_are_resolved_like_omx(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".omx-config.json").write_text(
                '{"env":{"OMX_DEFAULT_FRONTIER_MODEL":"frontier-model","OMX_DEFAULT_STANDARD_MODEL":"standard-model"},'
                '"models":{"team_low_complexity":"spark-model"}}',
                encoding="utf-8",
            )
            base_env = {"CODEX_HOME": str(home)}

            self.assertEqual(resolve_settings({**base_env, "US_STOCK_AGENT_LLM_MODEL_CLASS": "standard"}).model, "standard-model")
            self.assertEqual(
                resolve_settings(
                    {
                        **base_env,
                        "US_STOCK_AGENT_LLM_MODEL_CLASS": "spark",
                        "DISCORD_AGENT_LLM_MODEL_CLASS": "standard",
                    }
                ).model,
                "spark-model",
            )
            self.assertEqual(
                resolve_settings(
                    {
                        **base_env,
                        "US_STOCK_AGENT_LLM_MODEL_CLASS": "spark",
                        "US_STOCK_AGENT_LLM_MODEL": "manual-model",
                    }
                ).model,
                "manual-model",
            )

    def test_per_request_reasoning_effort_overrides_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / "config.toml").write_text(
                'model = "from-codex-config"\nmodel_reasoning_effort = "high"\n',
                encoding="utf-8",
            )
            settings = resolve_settings(
                {
                    "CODEX_HOME": str(home),
                    "US_STOCK_AGENT_LLM_REASONING_EFFORT": "low",
                }
            )

            self.assertEqual(settings.reasoning_effort, "low")


if __name__ == "__main__":
    unittest.main()
