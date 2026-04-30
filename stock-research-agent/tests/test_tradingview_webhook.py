import unittest

from src.tradingview_webhook import (
    build_tradingview_webhook_response,
    normalize_tradingview_symbol,
    parse_tradingview_payload,
    verify_webhook_secret,
)


class TradingViewWebhookTest(unittest.TestCase):
    def test_normalizes_exchange_prefixed_symbol(self) -> None:
        self.assertEqual(normalize_tradingview_symbol("NASDAQ:IREN"), "IREN")
        self.assertEqual(normalize_tradingview_symbol("NYSE:BMNR"), "BMNR")

    def test_builds_stock_agent_request_from_tradingview_alert(self) -> None:
        captured = {}

        def fake_agent_runner(request: str, runtime_context=None, explicit_mode=None):
            captured["request"] = request
            captured["runtime_context"] = runtime_context
            captured["explicit_mode"] = explicit_mode
            return {
                "agent": "stock-research-agent",
                "mode": "brief",
                "summary": "IREN 알림 기준 체크포인트를 정리했습니다.",
                "symbols": ["IREN"],
                "focus": ["현재가: 44.01", "옵션: 46.5 회복 여부"],
                "next_actions": ["44 지지 확인"],
            }

        def fake_quote_fetcher(symbol: str):
            return {
                "source": "CNBC quote",
                "price": 44.02,
                "timestamp": "2026-04-28T11:36:50-04:00",
                "change_pct": -8.98,
            }

        result = build_tradingview_webhook_response(
            {
                "symbol": "NASDAQ:IREN",
                "price": "44.01",
                "time": "2026-04-28T11:36:46-04:00",
                "interval": "5",
                "alert": "IREN 44 이탈",
            },
            agent_runner=fake_agent_runner,
            quote_fetcher=fake_quote_fetcher,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["symbol"], "IREN")
        self.assertEqual(result["trigger"]["price"], 44.01)
        self.assertEqual(captured["explicit_mode"], "brief")
        self.assertIn('"symbols": ["IREN"]', captured["request"])
        self.assertTrue(result["message_lines"][0].startswith("TradingView alert: IREN @ 44.01"))
        self.assertEqual(result["live_quote"]["price"], 44.02)
        self.assertTrue(any("현재가: 44.02" in line and "CNBC quote" in line for line in result["message_lines"]))
        self.assertTrue(any("옵션" in line for line in result["message_lines"]))

    def test_verify_webhook_secret_accepts_header_query_and_bearer(self) -> None:
        self.assertTrue(verify_webhook_secret({"X-TradingView-Secret": "abc"}, {}, "abc"))
        self.assertTrue(verify_webhook_secret({}, {"secret": ["abc"]}, "abc"))
        self.assertTrue(verify_webhook_secret({"Authorization": "Bearer abc"}, {}, "abc"))
        self.assertFalse(verify_webhook_secret({"X-TradingView-Secret": "wrong"}, {}, "abc"))
    def test_parses_plain_text_tradingview_body(self) -> None:
        payload = parse_tradingview_payload("Alert on NASDAQ:IREN price 44.01 crossing down")
        self.assertEqual(payload["symbol"], "NASDAQ:IREN")
        self.assertEqual(payload["price"], "44.01")
        self.assertEqual(payload["raw_message"], "Alert on NASDAQ:IREN price 44.01 crossing down")

    def test_accepts_empty_tradingview_body(self) -> None:
        payload = parse_tradingview_payload("")
        self.assertEqual(payload["symbol"], "UNKNOWN")
        self.assertEqual(payload["alert"], "TradingView alert")
        self.assertEqual(payload["raw_message"], "")


if __name__ == "__main__":
    unittest.main()
