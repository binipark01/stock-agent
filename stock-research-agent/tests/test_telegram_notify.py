import io
import json
import os
import unittest
from unittest.mock import patch
from urllib import error


class TelegramNotifyTest(unittest.TestCase):
    def test_build_telegram_payload_uses_webhook_message_and_chat_id(self):
        from src.telegram_notify import build_telegram_payload

        response = {
            "symbol": "NVDA",
            "message": "TradingView alert: NVDA @ 123.45\nYF Options: near 2026-04-29 / call OI 10 / put OI 5",
        }

        payload = build_telegram_payload(response, chat_id="12345")

        self.assertEqual(payload["chat_id"], "12345")
        self.assertIn("TradingView alert: NVDA @ 123.45", payload["text"])
        self.assertIn("YF Options", payload["text"])
        self.assertTrue(payload["disable_web_page_preview"])

    def test_build_telegram_payload_includes_optional_thread_id(self):
        from src.telegram_notify import build_telegram_payload

        payload = build_telegram_payload({"message": "hello"}, chat_id="12345", thread_id="99")

        self.assertEqual(payload["message_thread_id"], 99)

    def test_build_telegram_payload_truncates_for_telegram_limit(self):
        from src.telegram_notify import build_telegram_payload, TELEGRAM_TEXT_LIMIT

        response = {"message": "A" * (TELEGRAM_TEXT_LIMIT + 1000)}

        payload = build_telegram_payload(response, chat_id="12345")

        self.assertLessEqual(len(payload["text"]), TELEGRAM_TEXT_LIMIT)
        self.assertIn("[truncated]", payload["text"])

    def test_load_config_requires_token_and_chat_id_unless_dry_run(self):
        from src.telegram_notify import load_telegram_config

        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                load_telegram_config()

        with patch.dict(os.environ, {"TELEGRAM_NOTIFY_DRY_RUN": "1"}, clear=True):
            config = load_telegram_config()

        self.assertTrue(config.dry_run)

    def test_load_config_uses_first_allowed_user_as_chat_id_fallback(self):
        from src.telegram_notify import load_telegram_config

        env = {"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_ALLOWED_USERS": "111,222"}

        with patch.dict(os.environ, env, clear=True):
            config = load_telegram_config()

        self.assertEqual(config.chat_id, "111")

    def test_load_config_reads_optional_env_file_with_crlf(self):
        from pathlib import Path
        import tempfile

        from src.telegram_notify import load_telegram_config

        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / "hermes.env"
            env_path.write_text("TELEGRAM_BOT_TOKEN=file-token\r\nTELEGRAM_ALLOWED_USERS=333\r\n", encoding="utf-8")
            with patch.dict(os.environ, {"TELEGRAM_ENV_FILE": str(env_path)}, clear=True):
                config = load_telegram_config()

        self.assertEqual(config.bot_token, "file-token")
        self.assertEqual(config.chat_id, "333")

    def test_send_telegram_message_supports_dry_run_without_network(self):
        from src.telegram_notify import TelegramConfig, send_telegram_message

        config = TelegramConfig(bot_token="", chat_id="12345", dry_run=True)
        payload = {"chat_id": "12345", "text": "hello", "disable_web_page_preview": True}

        result = send_telegram_message(payload, config)

        self.assertEqual(result["status"], "dry_run")
        self.assertEqual(result["payload"]["text"], "hello")

    def test_main_reads_webhook_json_from_stdin_and_dry_runs(self):
        from src.telegram_notify import main

        stdin_payload = json.dumps({"symbol": "NVDA", "message": "TradingView alert: NVDA"})
        env = {"TELEGRAM_NOTIFY_DRY_RUN": "1", "TELEGRAM_CHAT_ID": "12345"}

        with patch.dict(os.environ, env, clear=True):
            exit_code = main(stdin_text=stdin_payload)

        self.assertEqual(exit_code, 0)

    def test_dry_run_stdout_redacts_chat_and_thread_ids(self):
        from src.telegram_notify import main

        stdin_payload = json.dumps({"symbol": "NVDA", "message": "TradingView alert: NVDA"})
        env = {
            "TELEGRAM_NOTIFY_DRY_RUN": "1",
            "TELEGRAM_CHAT_ID": "secret-chat-id",
            "TELEGRAM_THREAD_ID": "4242",
        }
        stdout = io.StringIO()

        with patch.dict(os.environ, env, clear=True), patch("sys.stdout", stdout):
            exit_code = main(stdin_text=stdin_payload)

        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn('"status": "dry_run"', output)
        self.assertIn('"chat_id": "***"', output)
        self.assertIn('"message_thread_id": "***"', output)
        self.assertNotIn("secret-chat-id", output)
        self.assertNotIn("4242", output)

    def test_send_telegram_message_uses_fallback_ip_after_primary_urlerror(self):
        from src.telegram_notify import TelegramConfig, send_telegram_message

        config = TelegramConfig(bot_token="token", chat_id="12345", fallback_ips=("149.154.167.220",))
        payload = {"chat_id": "12345", "text": "hello", "disable_web_page_preview": True}

        with patch("src.telegram_notify.request.urlopen", side_effect=error.URLError("network unreachable")), \
             patch("src.telegram_notify._post_telegram_via_fallback_ip", return_value={"ok": True, "result": {"message_id": 7}}) as fallback:
            result = send_telegram_message(payload, config)

        self.assertTrue(result["ok"])
        fallback.assert_called_once()
        self.assertEqual(fallback.call_args.args[0], "149.154.167.220")

    def test_send_telegram_message_can_prefer_fallback_ip_before_primary(self):
        from src.telegram_notify import TelegramConfig, send_telegram_message

        config = TelegramConfig(
            bot_token="token",
            chat_id="12345",
            fallback_ips=("149.154.166.110",),
            prefer_fallback_ips=True,
        )
        payload = {"chat_id": "12345", "text": "hello", "disable_web_page_preview": True}

        with patch("src.telegram_notify.request.urlopen") as primary, \
             patch("src.telegram_notify._post_telegram_via_fallback_ip", return_value={"ok": True, "result": {"message_id": 9}}) as fallback:
            result = send_telegram_message(payload, config)

        self.assertTrue(result["ok"])
        primary.assert_not_called()
        fallback.assert_called_once()
        self.assertEqual(fallback.call_args.args[0], "149.154.166.110")

    def test_load_config_can_prefer_fallback_ips(self):
        from src.telegram_notify import load_telegram_config

        env = {
            "TELEGRAM_BOT_TOKEN": "token",
            "TELEGRAM_CHAT_ID": "12345",
            "TELEGRAM_PREFER_FALLBACK_IPS": "1",
        }

        with patch.dict(os.environ, env, clear=True):
            config = load_telegram_config()

        self.assertTrue(config.prefer_fallback_ips)

    def test_main_prints_sanitized_send_result_without_chat_details(self):
        from src.telegram_notify import main

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps({
                    "ok": True,
                    "result": {
                        "message_id": 777,
                        "chat": {"id": "secret-chat-id", "first_name": "secret-name"},
                        "text": "secret message body",
                    },
                }).encode("utf-8")

        stdin_payload = json.dumps({"symbol": "NVDA", "message": "TradingView alert: NVDA"})
        env = {"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "secret-chat-id"}
        stdout = io.StringIO()

        with patch.dict(os.environ, env, clear=True), patch("src.telegram_notify.request.urlopen", return_value=FakeResponse()), patch("sys.stdout", stdout):
            exit_code = main(stdin_text=stdin_payload)

        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn('"status": "sent"', output)
        self.assertIn('"message_id": 777', output)
        self.assertNotIn("secret-chat-id", output)
        self.assertNotIn("secret-name", output)
        self.assertNotIn("secret message body", output)


if __name__ == "__main__":
    unittest.main()
