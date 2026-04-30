import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
START_SCRIPT = ROOT / "scripts" / "start_tradingview_webhook.sh"


class TradingViewWebhookStartScriptTest(unittest.TestCase):
    def test_sources_env_file_crlf_safely(self):
        script = START_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("sed 's/\\r$//'", script)
        self.assertNotIn('source "$ENV_FILE"', script)

    def test_passes_notify_command_and_timeout_to_server(self):
        script = START_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("TRADINGVIEW_WEBHOOK_NOTIFY_COMMAND", script)
        self.assertIn("TRADINGVIEW_WEBHOOK_NOTIFY_TIMEOUT", script)
        self.assertIn("--notify-command", script)
        self.assertIn("--notify-timeout", script)


if __name__ == "__main__":
    unittest.main()
