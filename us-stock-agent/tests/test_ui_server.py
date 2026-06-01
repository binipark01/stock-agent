import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "scripts" / "ui_server.py"
SPEC = importlib.util.spec_from_file_location("ui_server", SERVER_PATH)
server = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(server)


class UiServerTest(unittest.TestCase):
    def test_build_api_response_calls_agent_with_json_payload(self):
        calls = {}

        def fake_agent(request, runtime_context=None, explicit_mode=None):
            calls["request"] = request
            calls["runtime_context"] = runtime_context
            calls["explicit_mode"] = explicit_mode
            return {"agent": "us-stock-agent", "mode": explicit_mode, "summary": "ok"}

        result = server.build_api_response(
            {
                "request": "NVDA 체크",
                "mode": "technical_snapshot",
                "symbols": "nvda, tsla",
                "portfolio": "pltr",
            },
            agent_runner=fake_agent,
        )

        self.assertTrue(result["ok"])
        self.assertIn('"symbols": ["NVDA", "TSLA"]', calls["request"])
        self.assertEqual(calls["runtime_context"]["portfolio"], ["PLTR"])
        self.assertEqual(calls["explicit_mode"], "technical_snapshot")

    def test_auto_mode_passes_no_explicit_mode(self):
        calls = {}

        def fake_agent(request, runtime_context=None, explicit_mode=None):
            calls["explicit_mode"] = explicit_mode
            return {"agent": "us-stock-agent", "mode": "symbol_review", "summary": "ok"}

        server.build_api_response({"request": "NVDA", "mode": "auto"}, agent_runner=fake_agent)

        self.assertIsNone(calls["explicit_mode"])

    def test_general_chat_routes_to_llm_runner(self):
        calls = {}

        def fake_agent(*args, **kwargs):
            raise AssertionError("stock agent should not handle general chat")

        def fake_chat(request_text, history=None, env=None):
            calls["request_text"] = request_text
            calls["history"] = history
            calls["env"] = env
            return {"agent": "llm", "mode": "chat", "summary": "응, 말해봐."}

        result = server.build_api_response(
            {"request": "야", "history": [{"role": "user", "content": "야"}]},
            agent_runner=fake_agent,
            chat_runner=fake_chat,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["response"]["mode"], "chat")
        self.assertEqual(calls["request_text"], "야")
        self.assertEqual(calls["history"], [{"role": "user", "content": "야"}])
        self.assertEqual(calls["env"], {})

    def test_general_chat_passes_model_overrides(self):
        calls = {}

        def fake_chat(request_text, history=None, env=None):
            calls["env"] = env
            return {"agent": "llm", "mode": "chat", "summary": "ok"}

        result = server.build_api_response(
            {
                "request": "야",
                "llm_model": "gpt-5.4-mini",
                "llm_model_class": "spark",
            },
            agent_runner=lambda *_, **__: {},
            chat_runner=fake_chat,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(calls["env"]["US_STOCK_AGENT_LLM_MODEL"], "gpt-5.4-mini")
        self.assertEqual(calls["env"]["US_STOCK_AGENT_LLM_MODEL_CLASS"], "spark")

    def test_rejects_invalid_llm_model_class(self):
        with self.assertRaises(ValueError):
            server.build_api_response(
                {"request": "야", "llm_model_class": "expensive"},
                agent_runner=lambda *_, **__: {},
                chat_runner=lambda *_, **__: {},
            )

    def test_stock_request_still_uses_stock_agent(self):
        calls = {}

        def fake_agent(request, runtime_context=None, explicit_mode=None):
            calls["request"] = request
            return {"agent": "us-stock-agent", "mode": "symbol_review", "summary": "ok"}

        def fake_chat(*args, **kwargs):
            raise AssertionError("LLM chat should not handle stock requests")

        result = server.build_api_response(
            {"request": "NVDA 체크해줘"},
            agent_runner=fake_agent,
            chat_runner=fake_chat,
        )

        self.assertTrue(result["ok"])
        self.assertIn("NVDA 체크해줘", calls["request"])

    def test_rejects_unknown_mode(self):
        with self.assertRaises(ValueError):
            server.build_api_response({"request": "NVDA", "mode": "unknown"}, agent_runner=lambda *_, **__: {})

    def test_static_path_serves_index_only_inside_ui_dir(self):
        index_path = server._static_path("/")

        self.assertEqual(index_path, ROOT / "ui" / "index.html")
        self.assertIsNone(server._static_path("/../README.md"))


if __name__ == "__main__":
    unittest.main()
