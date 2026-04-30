import importlib.util
import io
import shlex
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "scripts" / "tradingview_webhook_server.py"
SPEC = importlib.util.spec_from_file_location("tradingview_webhook_server", SERVER_PATH)
server = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(server)


class TradingViewWebhookServerNotifyTest(unittest.TestCase):
    def test_run_notify_command_returns_sanitized_success_summary(self):
        command = " ".join([
            shlex.quote(sys.executable),
            "-c",
            shlex.quote('import json; print(json.dumps({"status":"sent","ok":True,"message_id":777,"chat":{"id":"secret"},"text":"secret body"}))'),
        ])

        result = server.run_notify_command(command, {"message": "hello"}, timeout_seconds=5)

        self.assertEqual(result["notify_status"], "sent")
        self.assertEqual(result["telegram_message_id"], 777)
        self.assertNotIn("secret", str(result))
        self.assertNotIn("secret body", str(result))

    def test_run_notify_command_reports_nonzero_exit(self):
        command = " ".join([
            shlex.quote(sys.executable),
            "-c",
            shlex.quote('import sys; print("boom", file=sys.stderr); raise SystemExit(2)'),
        ])

        result = server.run_notify_command(command, {"message": "hello"}, timeout_seconds=5)

        self.assertEqual(result["notify_status"], "error")
        self.assertIn("notify command exited 2", result["notify_error"])

    def test_request_logging_redacts_query_secret(self):
        handler = server.TradingViewWebhookHandler.__new__(server.TradingViewWebhookHandler)
        handler.address_string = lambda: "127.0.0.1"
        stdout = io.StringIO()

        with patch("sys.stdout", stdout):
            handler.log_message('"%s" %s %s', "POST /webhook/tradingview?secret=very-secret-value HTTP/1.1", "200", "-")

        output = stdout.getvalue()
        self.assertIn("secret=***", output)
        self.assertNotIn("very-secret-value", output)

    def test_parse_notify_timeout_seconds_accepts_valid_positive_int(self):
        self.assertEqual(server.parse_notify_timeout_seconds("90"), 90)

    def test_parse_notify_timeout_seconds_falls_back_on_invalid_values(self):
        self.assertEqual(server.parse_notify_timeout_seconds("bad", default=30), 30)
        self.assertEqual(server.parse_notify_timeout_seconds("0", default=30), 30)


if __name__ == "__main__":
    unittest.main()
