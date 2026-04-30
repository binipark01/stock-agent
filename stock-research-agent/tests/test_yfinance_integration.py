import json
import sys
import types
import unittest
from unittest.mock import patch


class _MiniFrame:
    def __init__(self, rows=None):
        self._rows = rows or []
        self.empty = not bool(self._rows)

    def head(self, limit):
        return _MiniFrame(self._rows[:limit])

    def reset_index(self):
        return self

    def to_dict(self, orient="records"):
        return self._rows if orient == "records" else {idx: row for idx, row in enumerate(self._rows)}


class _MiniOptionChain:
    calls = _MiniFrame([{"strike": 50.0, "openInterest": 200, "volume": 100, "lastPrice": 1.5}])
    puts = _MiniFrame([{"strike": 45.0, "openInterest": 100, "volume": 50, "lastPrice": 1.1}])


class _MiniTicker:
    def __init__(self, symbol):
        self.symbol = symbol
        self.fast_info = {"last_price": 101.0, "previous_close": 100.0, "currency": "USD", "exchange": "NMS"}
        self.info = {"longName": "Nvidia Corp", "sector": "Technology", "marketCap": 3000000000000, "forwardPE": 33.0}
        self.options = ("2026-05-15",)
        self.news = [{"title": "NVDA option volume jumps", "publisher": "Yahoo", "link": "https://example.com/nvda"}]
        self.calendar = {"Earnings Date": ["2026-05-20"]}
        self.major_holders = _MiniFrame([])
        self.institutional_holders = _MiniFrame([])
        self.recommendations = _MiniFrame([{"period": "0m", "buy": 10, "hold": 2}])

    def option_chain(self, expiration):
        return _MiniOptionChain()


class YfinanceIntegrationTest(unittest.TestCase):
    def test_cli_mode_returns_yfinance_pack_focus_lines(self):
        fake_yfinance = types.SimpleNamespace(Ticker=_MiniTicker)
        with patch.dict(sys.modules, {"yfinance": fake_yfinance}):
            from src.main import build_response

            payload = build_response(json.dumps({"mode": "yfinance_pack", "symbols": ["NVDA"], "request": "NVDA yfinance 싹 가져와"}, ensure_ascii=False))

        self.assertEqual(payload["mode"], "yfinance_pack")
        self.assertEqual(payload["symbols"], ["NVDA"])
        self.assertTrue(any(line.startswith("YF Quote: NVDA 101") for line in payload["focus"]))
        self.assertTrue(any("YF Options" in line for line in payload["focus"]))
        self.assertTrue(any("YF Fundamentals" in line for line in payload["focus"]))
        self.assertTrue(any("YF News" in line for line in payload["focus"]))

    def test_brief_request_can_surface_yfinance_lines_when_requested(self):
        fake_yfinance = types.SimpleNamespace(Ticker=_MiniTicker)
        with patch.dict(sys.modules, {"yfinance": fake_yfinance}):
            from src.main import build_response

            payload = build_response(json.dumps({"mode": "brief", "symbols": ["NVDA"], "request": "NVDA 브리핑 yfinance 옵션도"}, ensure_ascii=False))

        self.assertEqual(payload["mode"], "brief")
        self.assertTrue(any(line.startswith("YF Quote: NVDA") for line in payload["focus"]))
        self.assertTrue(any("YF Options" in line for line in payload["focus"]))

    def test_tradingview_webhook_message_includes_yfinance_lines(self):
        fake_yfinance = types.SimpleNamespace(Ticker=_MiniTicker)
        with patch.dict(sys.modules, {"yfinance": fake_yfinance}):
            from src.tradingview_webhook import build_tradingview_webhook_response

            response = build_tradingview_webhook_response(
                {"symbol": "NASDAQ:NVDA", "price": "101", "interval": "5", "alert": "돌파"},
                agent_runner=lambda *args, **kwargs: {"summary": "stub", "focus": [], "next_actions": []},
                quote_fetcher=lambda symbol: {"symbol": symbol, "price": 101.2, "source": "test quote"},
            )

        self.assertEqual(response["symbol"], "NVDA")
        self.assertTrue(any(line.startswith("YF Quote: NVDA") for line in response["message_lines"]))
        self.assertTrue(any("YF Options" in line for line in response["message_lines"]))


if __name__ == "__main__":
    unittest.main()
