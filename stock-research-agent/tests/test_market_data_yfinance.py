import sys
import types
import unittest
from unittest.mock import patch

from src.market_data import fetch_price_history, fetch_price_snapshot


class _FakeCloseSeries:
    def __init__(self, values):
        self._values = values

    def dropna(self):
        return self

    def tolist(self):
        return self._values


class _FakeHistory:
    def __init__(self, values):
        self._values = values

    def __getitem__(self, key):
        if key != "Close":
            raise KeyError(key)
        return _FakeCloseSeries(self._values)


class _FakeTicker:
    def __init__(self, symbol):
        self.symbol = symbol
        self.fast_info = {
            "last_price": 44.25,
            "previous_close": 42.5,
            "exchange": "NMS",
        }

    def history(self, period="6mo", interval="1d", auto_adjust=False):
        return _FakeHistory([float(i) for i in range(1, 46)])


class MarketDataYfinanceFallbackTest(unittest.TestCase):
    def test_price_snapshot_uses_optional_yfinance_when_raw_yahoo_chart_fails(self) -> None:
        fake_yfinance = types.SimpleNamespace(Ticker=_FakeTicker)
        with patch.dict(sys.modules, {"yfinance": fake_yfinance}):
            with patch("src.market_data._fetch_json", return_value=None):
                snapshot = fetch_price_snapshot("IREN")

        self.assertEqual(snapshot["symbol"], "IREN")
        self.assertEqual(snapshot["price"], 44.25)
        self.assertEqual(snapshot["pct_change"], 4.12)
        self.assertEqual(snapshot["source"], "yfinance")
        self.assertIn("optional yfinance fallback", snapshot["note"])

    def test_price_history_uses_optional_yfinance_when_raw_yahoo_chart_fails(self) -> None:
        fake_yfinance = types.SimpleNamespace(Ticker=_FakeTicker)
        with patch.dict(sys.modules, {"yfinance": fake_yfinance}):
            with patch("src.market_data._fetch_json", return_value=None):
                history = fetch_price_history("IREN")

        self.assertEqual(len(history), 45)
        self.assertEqual(history[-1], 45.0)


if __name__ == "__main__":
    unittest.main()
